"""All-annotations view -- cross-book search, filter, and paginated list."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from models.annotation import Annotation
from models.book import Book
from services.share_formatter import APP_PUBLIC_URL
from services.share_links import build_bluesky_share_url

_PAGE_SIZE = 25


def render_annotations(books: list[Book]) -> None:
    # Flatten and sort by timestamp
    _sentinel = datetime(1970, 1, 1)
    all_annotations: list[tuple[Annotation, str, str]] = sorted(
        [(ann, book.title, book.author or "") for book in books for ann in book.annotations],
        key=lambda pair: pair[0].created_at or _sentinel,
    )

    total_hl = sum(1 for a, _, _a in all_annotations if a.kind == "highlight")
    total_notes = sum(1 for a, _, _a in all_annotations if a.kind == "note")

    st.markdown("## Annotations")
    st.caption(
        f"{len(all_annotations)} total  /  {total_hl} highlights  /  {total_notes} notes"
    )

    if not all_annotations:
        st.info("No annotations loaded yet.")
        return

    # ── Filters ──────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([3, 1, 1])
    with fc1:
        query = st.text_input(
            "Search",
            placeholder="Search annotation text...",
            key="ann_search",
            label_visibility="collapsed",
        )
    with fc2:
        kind_filter = st.selectbox(
            "Type",
            options=["All", "Highlights", "Notes"],
            key="ann_kind",
            label_visibility="collapsed",
        )
    with fc3:
        book_titles = sorted({b.title for b in books})
        book_filter = st.selectbox(
            "Book",
            options=["All books"] + book_titles,
            key="ann_book",
            label_visibility="collapsed",
        )

    filtered = _apply_filters(all_annotations, query, kind_filter, book_filter)

    if query.strip() or kind_filter != "All" or book_filter != "All books":
        st.caption(f"Showing {len(filtered)} of {len(all_annotations)} annotation(s)")
    st.markdown("")

    # ── Pagination ───────────────────────────────────────────────
    page_key = "ann_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    total_pages = max(1, (len(filtered) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(st.session_state[page_key], total_pages - 1)
    page_items = filtered[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]

    # ── Annotation cards ─────────────────────────────────────────
    for ann, book_title, book_author in page_items:
        with st.container(border=True):
            badge_class = {
                "highlight": "kn-badge-highlight",
                "note": "kn-badge-note",
            }.get(ann.kind, "kn-badge-other")
            badge_label = {"highlight": "Highlight", "note": "Note"}.get(
                ann.kind, "Annotation"
            )

            meta_html = f'<span class="kn-badge {badge_class}">{badge_label}</span>'
            meta_html += f" <strong>{book_title}</strong>"
            if ann.chapter:
                meta_html += f' <span style="color:#888;">{ann.chapter}</span>'
            st.markdown(meta_html, unsafe_allow_html=True)

            if ann.kind == "highlight":
                st.markdown(f"> {ann.text}")
            else:
                st.markdown(ann.text)

            date_col, share_col = st.columns([4, 1])
            with date_col:
                if ann.created_at:
                    st.caption(ann.created_at.strftime("%b %d, %Y"))
            with share_col:
                post = _bluesky_annotation_text(ann, book_title, book_author)
                url = build_bluesky_share_url(post)
                st.link_button(
                    "🦋",
                    url=url,
                    help="Share on Bluesky",
                )

    # ── Pagination controls ──────────────────────────────────────
    if total_pages > 1:
        st.markdown("")
        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.button("Previous", disabled=page == 0, key="ann_prev"):
                st.session_state[page_key] = page - 1
                st.rerun()
        with p2:
            st.markdown(
                f'<div style="text-align:center; padding-top:0.4rem; font-size:0.85rem; color:#888;">'
                f"Page {page + 1} of {total_pages}</div>",
                unsafe_allow_html=True,
            )
        with p3:
            if st.button("Next", disabled=page >= total_pages - 1, key="ann_next"):
                st.session_state[page_key] = page + 1
                st.rerun()

    _community = "Kindle & Kobo" if st.session_state.get("data_source") == "kindle" else "Kobo"
    st.markdown(
        f'<div class="kn-footer">Made with love for the {_community} community.</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════
# Helpers
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


def _bluesky_annotation_text(ann: Annotation, book_title: str, book_author: str) -> str:
    """Build a Bluesky post from an annotation."""
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
