"""Vocabulary view -- display words looked up on the Kobo."""
from __future__ import annotations

from collections import Counter
from datetime import datetime

import streamlit as st

from models.book import Book
from models.vocabulary import WordLookup


def render_vocabulary(
    word_lookups: list[WordLookup],
    books: list[Book],
) -> None:
    st.markdown("## Vocabulary")
    st.caption(f"{len(word_lookups)} words looked up across your library")

    if not word_lookups:
        st.info("No dictionary lookups recorded. Words you look up on your Kobo will appear here.")
        return

    # ── Stats row ────────────────────────────────────────────────
    unique_words = len({wl.word.lower() for wl in word_lookups})
    books_with_lookups = len({wl.book_id for wl in word_lookups})
    languages = {wl.language for wl in word_lookups if wl.language}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Lookups", len(word_lookups))
    c2.metric("Unique Words", unique_words)
    c3.metric("Books", books_with_lookups)
    c4.metric("Languages", len(languages) if languages else "--")

    st.markdown("")

    # ── Filters ──────────────────────────────────────────────────
    book_titles = sorted({wl.book_title or wl.book_id for wl in word_lookups})
    col_filter1, col_filter2 = st.columns([2, 1])

    with col_filter1:
        search = st.text_input("Search words", placeholder="Type to filter...", key="vocab_search")

    with col_filter2:
        book_filter = st.selectbox(
            "Filter by book",
            ["All books"] + book_titles,
            key="vocab_book_filter",
        )

    # Apply filters
    filtered = word_lookups
    if search:
        search_lower = search.lower()
        filtered = [wl for wl in filtered if search_lower in wl.word.lower()]
    if book_filter != "All books":
        filtered = [wl for wl in filtered if (wl.book_title or wl.book_id) == book_filter]

    # ── Word list ────────────────────────────────────────────────
    sorted_lookups = sorted(
        filtered,
        key=lambda wl: wl.looked_up_at or datetime.min,
        reverse=True,
    )

    st.markdown(f"**{len(sorted_lookups)}** words" + (f" matching \"{search}\"" if search else ""))

    if not sorted_lookups:
        st.caption("No words match the current filters.")
        return

    # Display as a clean table
    rows: list[dict[str, str]] = []
    for wl in sorted_lookups:
        rows.append({
            "Word": wl.word,
            "Book": wl.book_title or wl.book_id[:30],
            "Language": wl.language or "--",
            "Date": wl.looked_up_at.strftime("%Y-%m-%d %H:%M") if wl.looked_up_at else "--",
        })

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Word": st.column_config.TextColumn(width="medium"),
            "Book": st.column_config.TextColumn(width="large"),
            "Language": st.column_config.TextColumn(width="small"),
            "Date": st.column_config.TextColumn(width="medium"),
        },
    )

    # ── Words by book breakdown ──────────────────────────────────
    st.markdown("---")
    st.markdown("### Words by Book")

    book_word_counts: Counter[str] = Counter()
    book_words: dict[str, list[str]] = {}
    for wl in word_lookups:
        title = wl.book_title or wl.book_id[:30]
        book_word_counts[title] += 1
        book_words.setdefault(title, []).append(wl.word)

    for title, count in book_word_counts.most_common():
        with st.expander(f"{title} ({count} word{'s' if count != 1 else ''})"):
            words = sorted(set(book_words[title]), key=str.lower)
            word_tags = " ".join(
                f'<span style="display:inline-block; background:#1e293b; border:1px solid #334155; '
                f'border-radius:4px; padding:0.2rem 0.6rem; margin:0.15rem; font-size:0.85rem; '
                f'color:#e2e8f0;">{word}</span>'
                for word in words
            )
            st.markdown(word_tags, unsafe_allow_html=True)

    # ── Footer ───────────────────────────────────────────────────
    st.markdown(
        '<div style="text-align:center; padding:2rem 0 1rem; font-size:0.75rem; color:#64748b;">'
        'Made with love for the Kobo community.'
        '</div>',
        unsafe_allow_html=True,
    )
