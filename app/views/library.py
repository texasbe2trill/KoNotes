"""Library view -- book collection with filtering, sorting, and drill-down."""
from __future__ import annotations

from typing import Callable

import streamlit as st

from app.components.book_cover import render_book_cover
from app.components.ui import render_empty_state, render_page_header
from models.book import Book
from services.stats import compute_stats


def render_library(books: list[Book], navigate: Callable[..., None], data_source: str = "kobo") -> None:
    stats = compute_stats(books)
    is_kindle = data_source == "kindle"

    meta = [
        f"{stats.total_books} books",
        f"{stats.total_highlights} highlights",
        f"{stats.total_notes} notes",
    ]
    if not is_kindle:
        meta += [
            f"{stats.books_in_progress} in progress",
            f"{stats.books_completed} completed",
        ]

    render_page_header(
        "Library",
        subtitle="Browse your collection — search by title or author, filter by status, and drill into any book.",
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

    # ── Filters + sort bar ───────────────────────────────────────
    all_authors = sorted({b.author for b in books if b.author})

    if is_kindle:
        fc1, fc2, fc3 = st.columns([3, 1.2, 1.2])
        status_filter = "All"  # no progress data for Kindle
        sort_options = ["Most Highlights", "Most Recent Annotation", "Title A-Z", "Author A-Z"]
    else:
        fc1, fc2, fc3, fc4 = st.columns([3, 1.2, 1.2, 1.2])
        sort_options = ["Most Highlights", "Recently Read", "Title A-Z", "Author A-Z"]

    with fc1:
        query = st.text_input(
            "Search",
            placeholder="Search by title or author...",
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

    if not filtered:
        st.info("No books match your search.")
        return

    if query.strip() or author_filter != "All authors" or status_filter != "All":
        st.caption(f"Showing {len(filtered)} of {len(books)} book(s)")

    st.markdown("")

    # ── Book cards ───────────────────────────────────────────────
    for book in filtered:
        h_count = sum(1 for a in book.annotations if a.kind == "highlight")
        n_count = sum(1 for a in book.annotations if a.kind == "note")
        pct = book.read_percent

        with st.container(border=True):
            col_cover, col_info, col_progress, col_stats, col_action = st.columns(
                [0.6, 3.0, 1.9, 1.9, 0.8]
            )

            with col_cover:
                render_book_cover(book, size="small")

            with col_info:
                title_line = f"**{book.title}**"
                if book.series:
                    title_line += f"  *({book.series})*"
                st.markdown(title_line)

                meta_parts: list[str] = []
                if book.author:
                    meta_parts.append(book.author)
                if book.shelves:
                    meta_parts.append(", ".join(book.shelves[:2]))
                if meta_parts:
                    st.caption(" / ".join(meta_parts))

            with col_progress:
                if pct is not None:
                    fill_class = "complete" if pct >= 100 else ""
                    label = "Finished" if pct >= 100 else f"{pct:.0f}% read"
                    st.markdown(
                        f'<div style="padding-top:0.4rem;">'
                        f'<div class="kn-progress-bar">'
                        f'<div class="kn-progress-fill {fill_class}" style="width:{min(pct, 100):.0f}%;"></div>'
                        f'</div>'
                        f'<div style="font-size:0.72rem; color:#888; margin-top:3px;">{label}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("")

            with col_stats:
                badge_html = (
                    f'<div style="padding-top:0.3rem;">'
                    f'<span class="kn-badge kn-badge-highlight">{h_count} highlights</span> '
                    f'<span class="kn-badge kn-badge-note">{n_count} notes</span>'
                    f'</div>'
                )
                st.markdown(badge_html, unsafe_allow_html=True)

            with col_action:
                if st.button("Open", key=f"open_{book.id}", width="stretch"):
                    navigate("book_detail", book.id)
                    st.rerun()

    # ── Footer ───────────────────────────────────────────────────
    _community = "Kindle & Kobo" if is_kindle else "Kobo"
    st.markdown(
        f'<div class="kn-footer">Made with love for the {_community} community.</div>',
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
