"""Vocabulary view -- display words looked up on the Kobo."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

from models.book import Book
from models.vocabulary import WordLookup

# Chart styling constants (consistent with charts.py palette)
_CYAN = "#06b6d4"
_BG_TRANSPARENT = "rgba(0,0,0,0)"
_GRID_SUBTLE = "rgba(148,163,184,0.08)"
_TEXT_MUTED = "#64748b"
_TEXT_DEFAULT = "#94a3b8"


def _dark_chart_layout(height: int = 260, **overrides: dict) -> dict:
    """Shared layout for dark-themed Plotly charts."""
    defaults = dict(
        height=height,
        margin=dict(l=0, r=10, t=10, b=30),
        paper_bgcolor=_BG_TRANSPARENT,
        plot_bgcolor=_BG_TRANSPARENT,
        font=dict(color=_TEXT_DEFAULT, size=12),
    )
    defaults.update(overrides)
    return defaults


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

    # Build frequency map for the Frequency column
    word_freq: Counter[str] = Counter(wl.word.lower() for wl in word_lookups)

    # Display as a clean table
    rows: list[dict[str, str | int]] = []
    for wl in sorted_lookups:
        rows.append({
            "Word": wl.word,
            "Book": wl.book_title or wl.book_id[:30],
            "Language": wl.language or "--",
            "Frequency": word_freq[wl.word.lower()],
        })

    st.dataframe(
        rows,
        hide_index=True,
        column_config={
            "Word": st.column_config.TextColumn(width="medium"),
            "Book": st.column_config.TextColumn(width="large"),
            "Language": st.column_config.TextColumn(width="small"),
            "Frequency": st.column_config.NumberColumn(width="small", format="%d"),
        },
    )

    # ── Lookup Activity Timeline ────────────────────────────────
    dated_lookups = [wl for wl in word_lookups if wl.looked_up_at]
    if dated_lookups:
        st.markdown("---")
        st.markdown('<div class="kn-section-header">Lookup Activity</div>', unsafe_allow_html=True)
        weekly: dict[str, int] = defaultdict(int)
        for wl in dated_lookups:
            week_start = wl.looked_up_at - timedelta(days=wl.looked_up_at.weekday())  # type: ignore[operator]
            weekly[week_start.strftime("%Y-%m-%d")] += 1
        weeks = sorted(weekly.keys())
        counts = [weekly[w] for w in weeks]
        labels = [datetime.strptime(w, "%Y-%m-%d").strftime("%b %d") for w in weeks]
        fig_timeline = go.Figure(
            data=[go.Scatter(
                x=labels, y=counts,
                mode="lines",
                fill="tozeroy",
                line=dict(color=_CYAN, width=2.5, shape="spline"),
                fillcolor="rgba(6,182,212,0.1)",
                hovertemplate="%{x}<br>%{y} lookups<extra></extra>",
            )],
        )
        fig_timeline.update_layout(
            **_dark_chart_layout(height=240),
            xaxis=dict(gridcolor=_BG_TRANSPARENT, tickangle=-45),
            yaxis=dict(gridcolor=_GRID_SUBTLE, title="Lookups",
                       title_font=dict(size=11, color=_TEXT_MUTED)),
        )
        st.plotly_chart(fig_timeline, config={"displayModeBar": False}, theme=None)

    # ── Footer ───────────────────────────────────────────────────
    st.markdown(
        '<div class="kn-footer">Made with love for the Kobo community.</div>',
        unsafe_allow_html=True,
    )
