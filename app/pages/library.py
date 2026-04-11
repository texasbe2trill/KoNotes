"""Library view — book list with stats, search, and drill-down navigation."""
from __future__ import annotations

from typing import Callable

import streamlit as st

from models.book import Book
from services.stats import compute_stats


def render_library(books: list[Book], navigate: Callable[..., None]) -> None:
    st.markdown("## 📚 Library")

    stats = compute_stats(books)

    # --- Stats row ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Books", stats.total_books)
    c2.metric("Annotations", stats.total_annotations)
    c3.metric("Highlights", stats.total_highlights)
    c4.metric("Notes", stats.total_notes)

    st.divider()

    # --- Search / filter ---
    query = st.text_input(
        "Search by title or author",
        placeholder="e.g. Dune, Frank Herbert",
        key="lib_search",
    )
    filtered = _filter_books(books, query)

    if not filtered:
        st.info("No books match your search.")
        return

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
                st.markdown(f"#### {book.title}")
                subtitle_parts: list[str] = []
                if book.author:
                    subtitle_parts.append(book.author)
                subtitle_parts.append(f"Source: {book.source}")
                st.caption(" · ".join(subtitle_parts))
            with top_right:
                if st.button("Open →", key=f"open_{book.id}", use_container_width=True):
                    navigate("book_detail", book.id)
                    st.rerun()

            tag_cols = st.columns(4)
            tag_cols[0].markdown(f"**{total}** annotations")
            tag_cols[1].markdown(f"🟡 {h_count} highlights")
            tag_cols[2].markdown(f"🔵 {n_count} notes")
            if total > 0:
                tag_cols[3].progress(h_count / total, text=f"{h_count / total:.0%} highlighted")
            else:
                tag_cols[3].markdown("—")

    # --- Most highlighted ---
    if len(books) > 1:
        st.divider()
        st.markdown("### Most highlighted books")
        for title, count in stats.books_by_highlight_count[:5]:
            if count > 0:
                st.markdown(f"- **{title}** — {count} highlight(s)")


def _filter_books(books: list[Book], query: str) -> list[Book]:
    if not query.strip():
        return books
    q = query.lower()
    return [
        b for b in books
        if q in b.title.lower() or (b.author and q in b.author.lower())
    ]
