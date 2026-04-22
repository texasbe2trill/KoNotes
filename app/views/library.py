"""Library view -- book collection with filtering, sorting, and drill-down."""
from __future__ import annotations

import html as _html
from typing import Callable

import streamlit as st

from app.components.book_cover import cover_html_fragment
from app.components.ui import render_empty_state, render_page_header
from models.book import Book
from services.stats import compute_stats

_GRID_COLS = 3
_PAGE_SIZE_OPTIONS = (12, 24, 48)
_DEFAULT_PAGE_SIZE = 12


def render_library(
    books: list[Book],
    navigate: Callable[..., None],
    data_source: str = "kobo",
) -> None:
    stats = compute_stats(books)
    is_kindle = data_source == "kindle"

    meta = [
        f"{stats.total_books} books",
        f"{stats.total_highlights:,} highlights",
        f"{stats.total_notes:,} notes",
    ]
    if not is_kindle:
        meta += [
            f"{stats.books_in_progress} in progress",
            f"{stats.books_completed} completed",
        ]

    render_page_header(
        "Library",
        subtitle="Browse your collection — search, filter, and drill into any book.",
        eyebrow="Your Books",
        meta=meta,
    )

    if not books:
        render_empty_state(
            "Your library is empty",
            body="Upload a KoboReader.sqlite or Kindle My Clippings.txt file from the sidebar to see your books here.",
            icon="📚",
        )
        return

    # ── Filter / sort bar ────────────────────────────────────────
    all_authors = sorted({b.author for b in books if b.author})
    status_filter = "All"

    if is_kindle:
        fc1, fc2, fc3 = st.columns([3, 1.4, 1.4])
        sort_options = ["Most Highlights", "Most Recent Annotation", "Title A-Z", "Author A-Z"]
    else:
        fc1, fc2, fc3, fc4 = st.columns([3, 1.2, 1.2, 1.4])
        sort_options = ["Most Highlights", "Recently Read", "Title A-Z", "Author A-Z"]

    with fc1:
        query = st.text_input(
            "Search",
            placeholder="Search by title or author…",
            key="lib_search",
            label_visibility="collapsed",
        )
    with fc2:
        author_filter = st.selectbox(
            "Author",
            options=["All authors"] + all_authors,
            key="lib_author",
            label_visibility="collapsed",
        )
    if not is_kindle:
        with fc3:
            status_filter = st.selectbox(
                "Status",
                options=["All", "In Progress", "Completed", "Not Started"],
                key="lib_status",
                label_visibility="collapsed",
            )
        sort_col = fc4
    else:
        sort_col = fc3

    with sort_col:
        sort_by = st.selectbox(
            "Sort",
            options=sort_options,
            key="lib_sort",
            label_visibility="collapsed",
        )

    filtered = _filter_books(books, query, author_filter, status_filter)
    filtered = _sort_books(filtered, sort_by)

    # ── Active-filter chips + count summary ──────────────────────
    has_filters = (
        bool(query.strip())
        or author_filter != "All authors"
        or status_filter != "All"
        or sort_by != sort_options[0]
    )
    active: list[tuple[str, str]] = []
    if query.strip():
        active.append(("Search", query.strip()))
    if author_filter != "All authors":
        active.append(("Author", author_filter))
    if not is_kindle and status_filter != "All":
        active.append(("Status", status_filter))
    if sort_by != sort_options[0]:
        active.append(("Sort", sort_by))

    chip_html = "".join(
        f'<span class="kn-lib-filter-chip">'
        f'<span class="kn-lib-filter-chip__lbl">{_html.escape(lbl)}</span>'
        f'<span class="kn-lib-filter-chip__val">{_html.escape(val)}</span></span>'
        for lbl, val in active
    )
    st.markdown(
        '<div class="kn-lib-summary">'
        '<div class="kn-lib-summary__count">'
        f'<strong>{len(filtered):,}</strong>'
        f'<span class="kn-lib-summary__total"> of {len(books):,} books</span>'
        '</div>'
        + (f'<div class="kn-lib-filter-chips">{chip_html}</div>' if chip_html else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    if has_filters and not filtered:
        render_empty_state(
            "No books match your filters",
            body="Try clearing the search, picking a different author, or resetting the status filter.",
            icon="🔍",
        )
        _render_footer(is_kindle)
        return

    # ── Pagination state ─────────────────────────────────────────
    page_size = st.session_state.get("lib_page_size", _DEFAULT_PAGE_SIZE)
    if page_size not in _PAGE_SIZE_OPTIONS:
        page_size = _DEFAULT_PAGE_SIZE

    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    if "lib_page" not in st.session_state:
        st.session_state["lib_page"] = 0
    if st.session_state["lib_page"] >= total_pages:
        st.session_state["lib_page"] = 0
    page = st.session_state["lib_page"]
    page_items = filtered[page * page_size : (page + 1) * page_size]

    # ── Grid ─────────────────────────────────────────────────────
    st.markdown('<div class="kn-lib-grid-wrap">', unsafe_allow_html=True)
    for row_start in range(0, len(page_items), _GRID_COLS):
        row = page_items[row_start : row_start + _GRID_COLS]
        cols = st.columns(_GRID_COLS, gap="small")
        for col, book in zip(cols, row):
            with col:
                st.markdown(_card_html(book, is_kindle), unsafe_allow_html=True)
                if st.button(
                    "Open →",
                    key=f"lib_open_{book.id}",
                    use_container_width=True,
                ):
                    navigate("book_detail", book.id)
                    st.rerun()
        # Pad trailing empty cells so the last row keeps grid alignment
        for col in cols[len(row):]:
            with col:
                st.markdown(
                    '<div class="kn-lib-card kn-lib-card--ghost"></div>',
                    unsafe_allow_html=True,
                )
    st.markdown("</div>", unsafe_allow_html=True)

    _render_pagination(page=page, total_pages=total_pages, page_size=page_size)
    _render_footer(is_kindle)


# ═════════════════════════════════════════════════════════════════
# Card / pagination rendering
# ═════════════════════════════════════════════════════════════════


def _card_html(book: Book, is_kindle: bool) -> str:
    h_count = sum(1 for a in book.annotations if a.kind == "highlight")
    n_count = sum(1 for a in book.annotations if a.kind == "note")
    pct = book.read_percent

    cover = cover_html_fragment(book, css_class="kn-lib-card__cover")

    title = _html.escape(book.title)
    series = (
        f'<div class="kn-lib-card__series">{_html.escape(book.series)}</div>'
        if book.series
        else ""
    )
    author = (
        f'<div class="kn-lib-card__author">{_html.escape(book.author)}</div>'
        if book.author
        else '<div class="kn-lib-card__author kn-lib-card__author--muted">Unknown author</div>'
    )

    if pct is not None and not is_kindle:
        if pct >= 100:
            status_label = "Finished"
            status_cls = "kn-lib-card__status--done"
        elif pct > 0:
            status_label = f"{pct:.0f}% read"
            status_cls = "kn-lib-card__status--reading"
        else:
            status_label = "Not started"
            status_cls = "kn-lib-card__status--unstarted"
        fill_pct = max(0.0, min(pct, 100))
        progress_html = (
            f'<div class="kn-lib-card__progress">'
            f'<div class="kn-lib-card__bar"><div class="kn-lib-card__fill" style="width:{fill_pct:.0f}%;"></div></div>'
            f'<div class="kn-lib-card__status {status_cls}">{_html.escape(status_label)}</div>'
            f'</div>'
        )
    else:
        progress_html = ""

    chips = (
        '<div class="kn-lib-card__chips">'
        f'<span class="kn-lib-card__chip kn-lib-card__chip--hl">'
        f'<strong>{h_count}</strong> highlights</span>'
        f'<span class="kn-lib-card__chip kn-lib-card__chip--note">'
        f'<strong>{n_count}</strong> notes</span>'
        '</div>'
    )

    shelves_html = ""
    if book.shelves:
        shelf_chips = "".join(
            f'<span class="kn-lib-card__shelf">{_html.escape(s)}</span>'
            for s in book.shelves[:2]
        )
        more = len(book.shelves) - 2
        if more > 0:
            shelf_chips += f'<span class="kn-lib-card__shelf kn-lib-card__shelf--more">+{more}</span>'
        shelves_html = f'<div class="kn-lib-card__shelves">{shelf_chips}</div>'

    return (
        '<article class="kn-lib-card">'
        f'<div class="kn-lib-card__cover-slot">{cover}</div>'
        '<div class="kn-lib-card__body">'
        f'<div class="kn-lib-card__title" title="{title}">{title}</div>'
        f'{series}'
        f'{author}'
        f'{progress_html}'
        f'{chips}'
        f'{shelves_html}'
        '</div>'
        '</article>'
    )


def _render_pagination(*, page: int, total_pages: int, page_size: int) -> None:
    st.markdown('<div class="kn-lib-pager">', unsafe_allow_html=True)
    p1, p2, p3, p4, p5 = st.columns([1, 1, 2, 1, 1.2])
    with p1:
        if st.button(
            "← Prev",
            disabled=page == 0,
            key="lib_prev",
            use_container_width=True,
        ):
            st.session_state["lib_page"] = max(0, page - 1)
            st.rerun()
    with p2:
        if st.button(
            "Next →",
            disabled=page >= total_pages - 1,
            key="lib_next",
            use_container_width=True,
        ):
            st.session_state["lib_page"] = min(total_pages - 1, page + 1)
            st.rerun()
    with p3:
        st.markdown(
            f'<div class="kn-lib-pager__label">Page <strong>{page + 1}</strong> of {total_pages}</div>',
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
                key="lib_jump",
                label_visibility="collapsed",
            )
            if int(jump) - 1 != page:
                st.session_state["lib_page"] = int(jump) - 1
                st.rerun()
    with p5:
        new_size = st.selectbox(
            "Per page",
            options=_PAGE_SIZE_OPTIONS,
            index=_PAGE_SIZE_OPTIONS.index(page_size),
            key="lib_page_size_select",
            label_visibility="collapsed",
            format_func=lambda n: f"{n} / page",
        )
        if new_size != page_size:
            st.session_state["lib_page_size"] = new_size
            st.session_state["lib_page"] = 0
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_footer(is_kindle: bool) -> None:
    community = "Kindle & Kobo" if is_kindle else "Kobo"
    st.markdown(
        f'<div class="kn-footer">Made with love for the {community} community.</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════


def _filter_books(
    books: list[Book],
    query: str,
    author_filter: str = "All authors",
    status_filter: str = "All",
) -> list[Book]:
    result = books
    if query.strip():
        q = query.lower()
        result = [
            b for b in result
            if q in b.title.lower() or (b.author and q in b.author.lower())
        ]
    if author_filter != "All authors":
        result = [b for b in result if b.author == author_filter]
    if status_filter == "In Progress":
        result = [b for b in result if b.read_percent is not None and 0 < b.read_percent < 100]
    elif status_filter == "Completed":
        result = [b for b in result if b.read_percent is not None and b.read_percent >= 100]
    elif status_filter == "Not Started":
        result = [b for b in result if b.read_percent is None or b.read_percent == 0]
    return result


def _sort_books(books: list[Book], sort_by: str) -> list[Book]:
    if sort_by == "Most Highlights":
        return sorted(
            books,
            key=lambda b: sum(1 for a in b.annotations if a.kind == "highlight"),
            reverse=True,
        )
    if sort_by == "Recently Read":
        from datetime import datetime

        _min = datetime.min
        return sorted(
            books,
            key=lambda b: b.date_last_read or _min,
            reverse=True,
        )
    if sort_by == "Most Recent Annotation":
        from datetime import datetime

        _min = datetime.min
        return sorted(
            books,
            key=lambda b: max(
                (a.created_at for a in b.annotations if a.created_at),
                default=_min,
            ),
            reverse=True,
        )
    if sort_by == "Title A-Z":
        return sorted(books, key=lambda b: b.title.lower())
    if sort_by == "Author A-Z":
        return sorted(books, key=lambda b: (b.author or "").lower())
    return books
