"""Per-book detail view -- annotations, chapter insights, and export."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Callable

import plotly.graph_objects as go
import streamlit as st

from app.charts import AMBER, BLUE, BLUE_GRADIENT, GRAY, PALETTE, figure, styled_axis
from models.annotation import Annotation
from models.book import Book
from services.export_json import export_book_json
from services.export_markdown import export_book_markdown
from services.export_text import export_book_text

_PAGE_SIZE = 20


def render_book_detail(book: Book, navigate: Callable[..., None]) -> None:
    # ── Back nav ─────────────────────────────────────────────────
    if st.button("Back to Library", key="bd_back"):
        navigate("library")
        st.rerun()

    # ── Header ───────────────────────────────────────────────────
    st.markdown(f"## {book.title}")
    if book.subtitle:
        st.caption(book.subtitle)

    meta_parts: list[str] = []
    if book.author:
        meta_parts.append(f"by **{book.author}**")
    if book.series:
        meta_parts.append(f"Series: {book.series}")
    if book.publisher:
        meta_parts.append(book.publisher)
    if book.language:
        meta_parts.append(book.language.upper())
    if meta_parts:
        st.markdown(" / ".join(meta_parts))

    h_count = sum(1 for a in book.annotations if a.kind == "highlight")
    n_count = sum(1 for a in book.annotations if a.kind == "note")

    # ── Stats row ────────────────────────────────────────────────
    stat_cols = st.columns(6)
    stat_cols[0].metric("Highlights", h_count)
    stat_cols[1].metric("Notes", n_count)
    if book.read_percent is not None:
        stat_cols[2].metric("Progress", f"{book.read_percent:.0f}%")
    else:
        stat_cols[2].metric("Total", len(book.annotations))
    if book.time_spent_reading and book.time_spent_reading > 0:
        hours = book.time_spent_reading / 3600
        stat_cols[3].metric("Reading Time", f"{hours:.1f}h" if hours >= 1 else f"{book.time_spent_reading // 60}m")
    elif book.date_last_read:
        stat_cols[3].metric("Last Read", book.date_last_read.strftime("%b %d, %Y"))
    else:
        stat_cols[3].metric("Source", book.source.replace("_", " ").title())
    if book.rating and 1 <= book.rating <= 5:
        stars = "* " * book.rating
        stat_cols[4].metric("Rating", stars.strip())
    elif book.page_turns and book.page_turns > 0:
        stat_cols[4].metric("Page Turns", f"{book.page_turns:,}")
    else:
        stat_cols[4].metric("Chapters", len({a.chapter for a in book.annotations if a.chapter}))
    if book.word_count and book.word_count > 0:
        stat_cols[5].metric("Words", f"{book.word_count:,}")
    else:
        stat_cols[5].metric("Annotations", len(book.annotations))

    # ── Badges: shelves + ISBN ───────────────────────────────────
    badge_parts: list[str] = []
    if book.shelves:
        for shelf in book.shelves:
            badge_parts.append(f'<span class="kn-badge-shelf">{shelf}</span>')
    if book.isbn:
        badge_parts.append(
            f'<span style="font-size:0.78rem; color:#888;">ISBN: {book.isbn}</span>'
        )
    if badge_parts:
        st.markdown(" ".join(badge_parts), unsafe_allow_html=True)

    # ── Export buttons ───────────────────────────────────────────
    st.markdown("")
    e1, e2, e3, e4 = st.columns([1, 1, 1, 3])
    e1.download_button(
        label="Markdown",
        data=export_book_markdown(book).encode("utf-8"),
        file_name=f"{_safe_filename(book.title)}_konotes.md",
        mime="text/markdown",
        width="stretch",
    )
    e2.download_button(
        label="JSON",
        data=export_book_json(book).encode("utf-8"),
        file_name=f"{_safe_filename(book.title)}_konotes.json",
        mime="application/json",
        width="stretch",
    )
    e3.download_button(
        label="Plain Text",
        data=export_book_text(book).encode("utf-8"),
        file_name=f"{_safe_filename(book.title)}_konotes.txt",
        mime="text/plain",
        width="stretch",
    )

    # ── Book-level charts ────────────────────────────────────────
    _render_book_charts(book)

    st.divider()

    # ── Filters ──────────────────────────────────────────────────
    fc1, fc2 = st.columns([3, 1])
    with fc1:
        search = st.text_input(
            "Search annotations",
            placeholder="Search text...",
            key=f"bd_search_{book.id}",
            label_visibility="collapsed",
        )
    with fc2:
        kind_filter = st.selectbox(
            "Type",
            options=["All", "Highlights", "Notes"],
            key=f"bd_filter_{book.id}",
            label_visibility="collapsed",
        )

    _sentinel = datetime(1970, 1, 1)
    sorted_anns = sorted(book.annotations, key=lambda a: a.created_at or _sentinel)
    filtered = _apply_filters(sorted_anns, kind_filter, search)

    if not filtered:
        st.info("No annotations match the current filter.")
        return

    st.caption(f"{len(filtered)} annotation(s)")

    # ── Pagination ───────────────────────────────────────────────
    page_key = f"bd_page_{book.id}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    total_pages = max(1, (len(filtered) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(st.session_state[page_key], total_pages - 1)
    page_items = filtered[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]

    # ── Annotation cards ─────────────────────────────────────────
    current_chapter: str | None = None
    for ann in page_items:
        if ann.chapter and ann.chapter != current_chapter:
            current_chapter = ann.chapter
            st.markdown(
                f'<div class="kn-chapter">{current_chapter}</div>',
                unsafe_allow_html=True,
            )

        with st.container(border=True):
            badge_class = {
                "highlight": "kn-badge-highlight",
                "note": "kn-badge-note",
            }.get(ann.kind, "kn-badge-other")
            badge_label = {"highlight": "Highlight", "note": "Note"}.get(
                ann.kind, "Annotation"
            )

            meta_html = f'<span class="kn-badge {badge_class}">{badge_label}</span>'
            if ann.location:
                meta_html += f' <span style="font-size:0.78rem; color:#888;">Loc: {ann.location}</span>'
            if ann.created_at:
                meta_html += f' <span style="font-size:0.78rem; color:#888;">{ann.created_at.strftime("%b %d, %Y")}</span>'
            st.markdown(meta_html, unsafe_allow_html=True)

            if ann.kind == "highlight":
                st.markdown(f"> {ann.text}")
            else:
                st.markdown(ann.text)

    # ── Pagination controls ──────────────────────────────────────
    if total_pages > 1:
        st.markdown("")
        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.button("Previous", disabled=page == 0, key=f"bd_prev_{book.id}"):
                st.session_state[page_key] = page - 1
                st.rerun()
        with p2:
            st.markdown(
                f'<div style="text-align:center; padding-top:0.4rem; font-size:0.85rem; color:#888;">'
                f"Page {page + 1} of {total_pages}</div>",
                unsafe_allow_html=True,
            )
        with p3:
            if st.button("Next", disabled=page >= total_pages - 1, key=f"bd_next_{book.id}"):
                st.session_state[page_key] = page + 1
                st.rerun()

    _community = "Kindle & Kobo" if st.session_state.get("data_source") == "kindle" else "Kobo"
    st.markdown(
        f'<div class="kn-footer">Made with love for the {_community} community.</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════
# Book-level charts
# ═════════════════════════════════════════════════════════════════


def _render_book_charts(book: Book) -> None:
    """Annotation timeline + chapter distribution for this book."""
    annotations = book.annotations
    if not annotations:
        return

    col_left, col_right = st.columns(2, gap="large")

    # -- Annotation timeline (when annotations were created) --
    dated_anns = [a for a in annotations if a.created_at]
    if len(dated_anns) >= 2:
        with col_left:
            st.markdown(
                '<div class="kn-section-header">Annotation Timeline</div>',
                unsafe_allow_html=True,
            )

            day_counter: Counter[str] = Counter()
            for a in dated_anns:
                day_counter[a.created_at.strftime("%Y-%m-%d")] += 1

            days_sorted = sorted(day_counter.keys())
            x_labels = [
                datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d in days_sorted
            ]
            y_values = [day_counter[d] for d in days_sorted]

            fig = figure(
                data=[
                    go.Bar(
                        x=x_labels,
                        y=y_values,
                        marker=dict(
                            color=y_values,
                            colorscale=BLUE_GRADIENT,
                            cornerradius=3,
                            line=dict(width=0),
                        ),
                        hovertemplate="%{x}<br>%{y} annotations<extra></extra>",
                    )
                ],
                height=220,
                xaxis=styled_axis(show_grid=False, tickangle=-45),
                yaxis=styled_axis(title="Annotations"),
                margin=dict(l=0, r=5, t=10, b=40),
            )
            st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)

    # -- Chapter distribution (which chapters have the most annotations) --
    chapters = [a.chapter for a in annotations if a.chapter]
    if chapters:
        chapter_counter = Counter(chapters)
        top_chapters = chapter_counter.most_common(10)

        with col_right:
            st.markdown(
                '<div class="kn-section-header">Top Chapters</div>',
                unsafe_allow_html=True,
            )

            ch_names = [
                (c[:28] + "..." if len(c) > 28 else c) for c, _ in top_chapters
            ]
            ch_counts = [c for _, c in top_chapters]

            # Reverse for horizontal bar top-to-bottom
            ch_names.reverse()
            ch_counts.reverse()

            fig = figure(
                data=[
                    go.Bar(
                        x=ch_counts,
                        y=ch_names,
                        orientation="h",
                        marker=dict(
                            color=AMBER,
                            cornerradius=3,
                            line=dict(width=0),
                        ),
                        hovertemplate="%{y}<br>%{x} annotations<extra></extra>",
                    )
                ],
                height=220,
                xaxis=styled_axis(title="Annotations"),
                yaxis=styled_axis(show_grid=False),
                margin=dict(l=0, r=5, t=10, b=40),
            )
            st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


# ═════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════


def _apply_filters(
    annotations: list[Annotation], kind_filter: str, search: str
) -> list[Annotation]:
    result = annotations
    if kind_filter == "Highlights":
        result = [a for a in result if a.kind == "highlight"]
    elif kind_filter == "Notes":
        result = [a for a in result if a.kind == "note"]
    if search.strip():
        q = search.lower()
        result = [a for a in result if q in a.text.lower()]
    return result


def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:60]
