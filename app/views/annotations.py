"""All-annotations view -- cross-book search, filter, and paginated grid."""
from __future__ import annotations

import html as _html
from datetime import datetime

import streamlit as st

from app.components.ui import render_empty_state, render_page_header
from models.annotation import Annotation
from models.book import Book
from services.share_formatter import APP_PUBLIC_URL
from services.share_links import build_bluesky_share_url

_PAGE_SIZE_OPTIONS = (24, 48, 96)
_DEFAULT_PAGE_SIZE = 24

_SORT_OPTIONS = (
    "Newest first",
    "Oldest first",
    "Book A → Z",
    "Longest first",
)

_KIND_OPTIONS = ("All", "Highlights", "Notes")


def render_annotations(books: list[Book]) -> None:
    sentinel = datetime(1970, 1, 1)
    all_annotations: list[tuple[Annotation, str, str]] = [
        (ann, book.title, book.author or "")
        for book in books
        for ann in book.annotations
    ]

    total_hl = sum(1 for a, _, _a in all_annotations if a.kind == "highlight")
    total_notes = sum(1 for a, _, _a in all_annotations if a.kind == "note")
    books_with_ann = sum(1 for b in books if b.annotations)

    render_page_header(
        "Annotations",
        subtitle="Search and revisit every highlight and note across your library.",
        eyebrow="Cross-Book Search",
        meta=[
            f"{len(all_annotations):,} total",
            f"{total_hl:,} highlights",
            f"{total_notes:,} notes",
            f"{books_with_ann} books",
        ],
    )

    if not all_annotations:
        render_empty_state(
            "No annotations yet",
            body="Highlights and notes from your Kobo or Kindle will appear here once you load your data.",
            icon="✍️",
        )
        return

    # ── Filter bar ───────────────────────────────────────────────
    st.markdown('<div class="kn-ann-toolbar">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns([3, 1, 1.4, 1.1])
    with fc1:
        query = st.text_input(
            "Search",
            placeholder="Search annotation text…",
            key="ann_search",
            label_visibility="collapsed",
        )
    with fc2:
        kind_filter = st.selectbox(
            "Type",
            options=_KIND_OPTIONS,
            key="ann_kind",
            label_visibility="collapsed",
        )
    with fc3:
        book_titles = sorted({b.title for b in books if b.annotations})
        book_filter = st.selectbox(
            "Book",
            options=["All books"] + book_titles,
            key="ann_book",
            label_visibility="collapsed",
        )
    with fc4:
        sort_choice = st.selectbox(
            "Sort",
            options=_SORT_OPTIONS,
            key="ann_sort",
            label_visibility="collapsed",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = _apply_filters(all_annotations, query, kind_filter, book_filter)
    filtered = _apply_sort(filtered, sort_choice, sentinel)

    # ── Result summary + active-filter chips ─────────────────────
    has_filters = (
        bool(query.strip())
        or kind_filter != "All"
        or book_filter != "All books"
        or sort_choice != _SORT_OPTIONS[0]
    )

    active: list[tuple[str, str]] = []
    if query.strip():
        active.append(("Search", query.strip()))
    if kind_filter != "All":
        active.append(("Type", kind_filter))
    if book_filter != "All books":
        active.append(("Book", book_filter))
    if sort_choice != _SORT_OPTIONS[0]:
        active.append(("Sort", sort_choice))

    chip_html = "".join(
        f'<span class="kn-ann-filter-chip"><span class="kn-ann-filter-chip__lbl">{_html.escape(lbl)}</span>'
        f'<span class="kn-ann-filter-chip__val">{_html.escape(val)}</span></span>'
        for lbl, val in active
    )

    summary_html = (
        '<div class="kn-ann-summary">'
        '<div class="kn-ann-summary__count">'
        f'<strong>{len(filtered):,}</strong>'
        f'<span class="kn-ann-summary__total"> of {len(all_annotations):,} annotations</span>'
        '</div>'
        + (f'<div class="kn-ann-filter-chips">{chip_html}</div>' if chip_html else "")
        + "</div>"
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    if has_filters and not filtered:
        render_empty_state(
            "No matching annotations",
            body="Try a different search term, clear the type filter, or pick a different book.",
            icon="🔍",
        )
        _render_footer()
        return

    # ── Pagination state ─────────────────────────────────────────
    page_size = st.session_state.get("ann_page_size", _DEFAULT_PAGE_SIZE)
    if page_size not in _PAGE_SIZE_OPTIONS:
        page_size = _DEFAULT_PAGE_SIZE

    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    page_key = "ann_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0
    if st.session_state[page_key] >= total_pages:
        st.session_state[page_key] = 0
    page = st.session_state[page_key]
    page_items = filtered[page * page_size : (page + 1) * page_size]

    # ── Annotation grid ──────────────────────────────────────────
    cards_html = "".join(_card_html(ann, title, author) for ann, title, author in page_items)
    st.markdown(
        f'<div class="kn-ann-grid">{cards_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Pagination controls ──────────────────────────────────────
    _render_pagination(page=page, total_pages=total_pages, page_size=page_size)

    _render_footer()


# ═════════════════════════════════════════════════════════════════
# Rendering helpers
# ═════════════════════════════════════════════════════════════════


def _card_html(ann: Annotation, book_title: str, book_author: str) -> str:
    is_highlight = ann.kind == "highlight"
    is_note = ann.kind == "note"
    badge_cls = (
        "kn-ann-card__badge--highlight"
        if is_highlight
        else "kn-ann-card__badge--note"
        if is_note
        else "kn-ann-card__badge--other"
    )
    badge_label = "Highlight" if is_highlight else "Note" if is_note else "Annotation"

    chapter = (
        f'<span class="kn-ann-card__chapter" title="{_html.escape(ann.chapter)}">'
        f'{_html.escape(ann.chapter)}</span>'
        if ann.chapter
        else ""
    )
    date_str = ann.created_at.strftime("%b %d, %Y") if ann.created_at else ""
    date_html = (
        f'<span class="kn-ann-card__date">{_html.escape(date_str)}</span>' if date_str else ""
    )

    body_cls = "kn-ann-card__body"
    if is_highlight:
        body_cls += " kn-ann-card__body--quote"

    text = _html.escape(ann.text or "").replace("\n", "<br>")

    bsky_url = build_bluesky_share_url(_bluesky_annotation_text(ann, book_title, book_author))
    bsky_btn = (
        f'<a class="kn-ann-card__share" href="{_html.escape(bsky_url)}" '
        'target="_blank" rel="noopener noreferrer" title="Share on Bluesky" '
        'aria-label="Share on Bluesky">🦋</a>'
    )

    book_html = (
        f'<span class="kn-ann-card__book" title="{_html.escape(book_title)}">'
        f"{_html.escape(book_title)}</span>"
    )

    foot_inner = chapter + date_html
    foot = f'<footer class="kn-ann-card__foot">{foot_inner}</footer>' if foot_inner else ""

    return (
        '<article class="kn-ann-card">'
        '<header class="kn-ann-card__head">'
        f'<span class="kn-ann-card__badge {badge_cls}">{badge_label}</span>'
        f"{book_html}"
        f"{bsky_btn}"
        "</header>"
        f'<div class="{body_cls}">{text}</div>'
        f"{foot}"
        "</article>"
    )


def _render_pagination(*, page: int, total_pages: int, page_size: int) -> None:
    st.markdown('<div class="kn-ann-pager">', unsafe_allow_html=True)
    p1, p2, p3, p4, p5 = st.columns([1, 1, 2, 1, 1.2])
    with p1:
        if st.button(
            "← Prev",
            disabled=page == 0,
            key="ann_prev",
            use_container_width=True,
        ):
            st.session_state["ann_page"] = max(0, page - 1)
            st.rerun()
    with p2:
        if st.button(
            "Next →",
            disabled=page >= total_pages - 1,
            key="ann_next",
            use_container_width=True,
        ):
            st.session_state["ann_page"] = min(total_pages - 1, page + 1)
            st.rerun()
    with p3:
        st.markdown(
            f'<div class="kn-ann-pager__label">Page <strong>{page + 1}</strong> of {total_pages}</div>',
            unsafe_allow_html=True,
        )
    with p4:
        if total_pages > 1:
            jump = st.number_input(
                "Jump",
                min_value=1,
                max_value=total_pages,
                value=page + 1,
                step=1,
                key="ann_jump",
                label_visibility="collapsed",
            )
            if int(jump) - 1 != page:
                st.session_state["ann_page"] = int(jump) - 1
                st.rerun()
    with p5:
        new_size = st.selectbox(
            "Per page",
            options=_PAGE_SIZE_OPTIONS,
            index=_PAGE_SIZE_OPTIONS.index(page_size),
            key="ann_page_size_select",
            label_visibility="collapsed",
            format_func=lambda n: f"{n} / page",
        )
        if new_size != page_size:
            st.session_state["ann_page_size"] = new_size
            st.session_state["ann_page"] = 0
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_footer() -> None:
    community = "Kindle & Kobo" if st.session_state.get("data_source") == "kindle" else "Kobo"
    st.markdown(
        f'<div class="kn-footer">Made with love for the {community} community.</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════
# Filtering / sorting
# ═════════════════════════════════════════════════════════════════


def _apply_filters(
    items: list[tuple[Annotation, str, str]],
    query: str,
    kind_filter: str,
    book_filter: str,
) -> list[tuple[Annotation, str, str]]:
    result = items
    if book_filter != "All books":
        result = [(a, t, au) for a, t, au in result if t == book_filter]
    if kind_filter == "Highlights":
        result = [(a, t, au) for a, t, au in result if a.kind == "highlight"]
    elif kind_filter == "Notes":
        result = [(a, t, au) for a, t, au in result if a.kind == "note"]
    if query.strip():
        q = query.lower()
        result = [(a, t, au) for a, t, au in result if q in a.text.lower()]
    return result


def _apply_sort(
    items: list[tuple[Annotation, str, str]],
    sort_choice: str,
    sentinel: datetime,
) -> list[tuple[Annotation, str, str]]:
    if sort_choice == "Oldest first":
        return sorted(items, key=lambda p: p[0].created_at or sentinel)
    if sort_choice == "Book A → Z":
        return sorted(
            items,
            key=lambda p: (
                p[1].lower(),
                -(p[0].created_at or sentinel).timestamp(),
            ),
        )
    if sort_choice == "Longest first":
        return sorted(items, key=lambda p: len(p[0].text or ""), reverse=True)
    return sorted(items, key=lambda p: p[0].created_at or sentinel, reverse=True)


def _bluesky_annotation_text(ann: Annotation, book_title: str, book_author: str) -> str:
    quote = ann.text
    if ann.kind == "highlight":
        line1 = f"\u201c{quote}\u201d"
    else:
        line1 = quote
    source = f"Annotation from: \u201c{book_title}\u201d"
    if book_author:
        source += f" -- {book_author}"
    footer = f"Discover your reading insights with #KoNotes #booksky {APP_PUBLIC_URL}"
    return f"{line1}\n\n{source}\n\n{footer}"
