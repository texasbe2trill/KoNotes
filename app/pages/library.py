"""Library view — book list with stats, search, and drill-down navigation."""
from __future__ import annotations

from typing import Callable

import streamlit as st

from models.book import Book
from services.stats import compute_stats


def render_library(books: list[Book], navigate: Callable[..., None]) -> None:
    st.markdown("## Library")

    stats = compute_stats(books)

    # --- Stats row ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Books", stats.total_books)
    c2.metric("Annotations", stats.total_annotations)
    c3.metric("Highlights", stats.total_highlights)
    c4.metric("Notes", stats.total_notes)

    # --- Reading insights (inline, not buried in expander) ---
    in_progress = [b for b in books if b.read_percent is not None and b.read_percent < 100]
    recently_read = sorted(
        [b for b in books if b.date_last_read is not None],
        key=lambda b: b.date_last_read,
        reverse=True,
    )[:5]
    all_shelves = sorted({s for b in books for s in b.shelves})

    if in_progress or recently_read or all_shelves:
        st.markdown("")
        tabs = []
        tab_labels = []
        if recently_read:
            tab_labels.append("Recently Read")
        if in_progress:
            tab_labels.append("In Progress")
        if all_shelves:
            tab_labels.append("Shelves")

        if tab_labels:
            tab_objects = st.tabs(tab_labels)
            idx = 0
            if recently_read:
                with tab_objects[idx]:
                    for b in recently_read:
                        col_t, col_d = st.columns([4, 1])
                        col_t.markdown(f"**{b.title}**" + (f" — {b.author}" if b.author else ""))
                        col_d.caption(b.date_last_read.strftime("%b %d, %Y"))
                idx += 1
            if in_progress:
                with tab_objects[idx]:
                    for b in in_progress:
                        pct = b.read_percent or 0
                        col_t, col_p = st.columns([3, 2])
                        col_t.markdown(f"**{b.title}**")
                        col_p.progress(pct / 100, text=f"{pct:.0f}%")
                idx += 1
            if all_shelves:
                with tab_objects[idx]:
                    # Show shelves as pills
                    shelf_html = " ".join(
                        f'<span style="display:inline-block; padding:0.2rem 0.6rem; '
                        f'border-radius:12px; background:rgba(74,158,255,0.1); '
                        f'color:#4a9eff; font-size:0.82rem; margin:0.15rem 0.1rem;">{s}</span>'
                        for s in all_shelves
                    )
                    st.markdown(shelf_html, unsafe_allow_html=True)

    st.divider()

    # --- Search / filter ---
    query = st.text_input(
        "Search by title or author",
        placeholder="e.g. Nexus, Harari",
        key="lib_search",
        label_visibility="collapsed",
    )
    filtered = _filter_books(books, query)

    if not filtered:
        st.info("No books match your search.")
        return

    if query.strip():
        st.caption(f"Showing {len(filtered)} of {len(books)} book(s)")
    st.markdown("")

    # --- Book cards ---
    for book in filtered:
        h_count = sum(1 for a in book.annotations if a.kind == "highlight")
        n_count = sum(1 for a in book.annotations if a.kind == "note")
        total = len(book.annotations)

        with st.container(border=True):
            top_left, top_right = st.columns([5, 1])
            with top_left:
                st.markdown(f"**{book.title}**")
                meta_parts: list[str] = []
                if book.author:
                    meta_parts.append(book.author)
                if book.read_percent is not None:
                    meta_parts.append(f"{book.read_percent:.0f}% read")
                if book.shelves:
                    meta_parts.append(", ".join(book.shelves))
                if meta_parts:
                    st.caption(" · ".join(meta_parts))
            with top_right:
                if st.button("Open", key=f"open_{book.id}", use_container_width=True):
                    navigate("book_detail", book.id)
                    st.rerun()

            # Annotation summary as badge-style HTML
            badge_html = (
                f'<span class="kn-badge kn-badge-highlight">{h_count} highlights</span> '
                f'<span class="kn-badge kn-badge-note">{n_count} notes</span>'
            )
            if total > 0:
                badge_html += (
                    f' <span style="font-size:0.78rem; color:#888; margin-left:0.5rem;">'
                    f'{total} total</span>'
                )
            st.markdown(badge_html, unsafe_allow_html=True)

    # --- Footer ---
    st.markdown(
        '<div class="kn-footer">Made with love for the Kobo community.</div>',
        unsafe_allow_html=True,
    )


def _filter_books(books: list[Book], query: str) -> list[Book]:
    if not query.strip():
        return books
    q = query.lower()
    return [
        b for b in books
        if q in b.title.lower() or (b.author and q in b.author.lower())
    ]
