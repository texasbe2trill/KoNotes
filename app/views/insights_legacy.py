"""AI Insights view -- theme detection, highlight clustering, similarity search, summaries."""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import streamlit as st

from models.book import Book

if TYPE_CHECKING:
    from models.insight import BookSummary, HighlightSimilarity, ThemeCluster

# Color palette
_BLUE = "#3b82f6"
_GREEN = "#22c55e"
_AMBER = "#f59e0b"
_PURPLE = "#a855f7"
_ROSE = "#f43f5e"
_CYAN = "#06b6d4"
_TEAL = "#14b8a6"
_INDIGO = "#6366f1"
_COLORS = [_BLUE, _GREEN, _AMBER, _PURPLE, _ROSE, _CYAN, _TEAL, _INDIGO]


def _ai_available() -> bool:
    """Check if AI dependencies (numpy, sklearn, sentence-transformers) are available."""
    try:
        import numpy  # noqa: F401
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


def _get_provider():
    """Return the local embedding provider, or None."""
    from services.embeddings import get_provider
    try:
        return get_provider()
    except ImportError as exc:
        st.error(str(exc))
        return None


def _format_time(seconds: int) -> str:
    """Format seconds to human-readable time."""
    if seconds < 3600:
        return f"{seconds // 60}m"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def _pill(text: str, color: str) -> str:
    """Return an HTML pill/badge."""
    return (
        f'<span style="display:inline-block; font-size:0.7rem; padding:0.15rem 0.55rem; '
        f'border-radius:20px; border:1px solid {color}; color:{color}; '
        f'background:rgba(255,255,255,0.02); margin:0.15rem 0.1rem;">{text}</span>'
    )


def render_insights(books: list[Book]) -> None:
    """Render the AI Insights page."""
    st.markdown("## AI Insights")

    if not _ai_available():
        st.warning(
            "AI features require additional dependencies. "
            "Install with: `pip install '.[ai]'`"
        )
        _render_reading_insights(books)
        return

    # ── Reading insights (always available) ──────────────────
    _render_reading_insights(books)

    st.divider()

    # ── Theme detection + clustering + summaries ─────────────
    highlights = [
        a for book in books for a in book.annotations
        if a.kind == "highlight" and a.text.strip()
    ]

    if len(highlights) < 3:
        st.info("Need at least 3 highlights to run AI analysis.")
        return

    st.markdown(
        f'<div style="font-size:0.85rem; color:#94a3b8; margin-bottom:1rem;">'
        f'{len(highlights)} highlights across {len(books)} books available for analysis</div>',
        unsafe_allow_html=True,
    )

    col_a, col_b, col_c = st.columns(3)
    run_themes = col_a.button("Detect themes", type="primary", width="stretch")
    run_cluster = col_b.button("Cluster ideas", width="stretch")
    run_summary = col_c.button("Generate summaries", width="stretch")

    # ── Theme detection ──────────────────────────────────────
    if run_themes:
        provider_inst = _get_provider()
        if provider_inst is None:
            return
        from services.insights import detect_themes

        with st.spinner("Detecting themes..."):
            all_themes: list[ThemeCluster] = []
            for book in books:
                book_highlights = [
                    a for a in book.annotations
                    if a.kind == "highlight" and a.text.strip()
                ]
                if len(book_highlights) >= 3:
                    themes = detect_themes(book, provider_inst)
                    all_themes.extend(themes)
            st.session_state["ai_themes"] = all_themes

    if "ai_themes" in st.session_state and st.session_state["ai_themes"]:
        _render_themes(st.session_state["ai_themes"])

    # ── Cross-book clustering ────────────────────────────────
    if run_cluster:
        provider_inst = _get_provider()
        if provider_inst is None:
            return
        from services.insights import cluster_highlights_across_books

        with st.spinner("Clustering highlights across books..."):
            clusters = cluster_highlights_across_books(books, provider_inst)
            st.session_state["ai_clusters"] = clusters

    if "ai_clusters" in st.session_state and st.session_state["ai_clusters"]:
        _render_clusters(st.session_state["ai_clusters"])

    # ── Summaries ────────────────────────────────────────────
    if run_summary:
        from services.summaries import generate_summary

        with st.spinner("Generating summaries..."):
            summaries: list[BookSummary] = []
            for book in books:
                if book.annotations:
                    themes = st.session_state.get("ai_themes", [])
                    book_themes = [t for t in themes if book.title in t.book_titles]
                    s = generate_summary(book, themes=book_themes)
                    summaries.append(s)
            st.session_state["ai_summaries"] = summaries

    if "ai_summaries" in st.session_state and st.session_state["ai_summaries"]:
        _render_summaries(st.session_state["ai_summaries"], books)

    st.divider()

    # ── Similarity search ────────────────────────────────────
    _render_similarity_search(books)

    # ── Footer ───────────────────────────────────────────────
    st.markdown(
        '<div class="kn-footer">Made with love for the Kobo community.</div>',
        unsafe_allow_html=True,
    )


def _render_reading_insights(books: list[Book]) -> None:
    """Show reading insights with rich stats and visualization."""
    from services.insights import compute_reading_insights

    insights = compute_reading_insights(books)

    st.markdown(
        '<div class="kn-section-header">Reading Insights</div>',
        unsafe_allow_html=True,
    )

    # Primary metrics row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Books annotated", insights["books_with_annotations"])
    c2.metric("Total highlights", insights["total_highlights"])
    c3.metric("Total notes", insights["total_notes"])
    c4.metric("Avg HL / Book", insights["avg_highlights_per_book"])

    # Extended metrics
    total_reading_sec = sum(b.time_spent_reading or 0 for b in books)
    total_words = sum(b.word_count or 0 for b in books)
    rated = [b for b in books if b.rating and b.rating > 0]

    extras: list[tuple[str, str]] = []
    if total_reading_sec > 0:
        extras.append(("Total reading time", _format_time(total_reading_sec)))
    if total_words > 0:
        extras.append(("Words read", f"{total_words:,}"))
    if rated:
        avg_r = sum(b.rating or 0 for b in rated) / len(rated)
        extras.append(("Avg rating", f"{avg_r:.1f} / 5"))
    unique_chapters = len({a.chapter for b in books for a in b.annotations if a.chapter})
    if unique_chapters:
        extras.append(("Unique chapters", str(unique_chapters)))

    if extras:
        cols = st.columns(len(extras))
        for col, (label, val) in zip(cols, extras):
            col.metric(label, val)

    # Top highlighted authors as a styled ranked list
    if insights["top_highlighted_authors"]:
        st.markdown(
            '<div class="kn-section-header">Most Highlighted Authors</div>',
            unsafe_allow_html=True,
        )
        max_hl = insights["top_highlighted_authors"][0][1] if insights["top_highlighted_authors"] else 1
        items_html = ""
        for i, (author, count) in enumerate(insights["top_highlighted_authors"][:8], 1):
            bar_pct = (count / max_hl) * 100 if max_hl else 0
            color = _COLORS[(i - 1) % len(_COLORS)]
            items_html += (
                f'<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.5rem;">'
                f'<span style="font-size:0.8rem; color:#64748b; min-width:1.2rem; text-align:right;">{i}</span>'
                f'<div style="flex:1;">'
                f'<div style="display:flex; justify-content:space-between; margin-bottom:0.2rem;">'
                f'<span style="font-size:0.85rem;">{author}</span>'
                f'<span style="font-size:0.75rem; color:{color}; font-weight:600;">'
                f'{count} highlight{"s" if count != 1 else ""}</span></div>'
                f'<div style="height:6px; background:rgba(255,255,255,0.04); border-radius:3px; overflow:hidden;">'
                f'<div style="height:100%; width:{bar_pct:.0f}%; background:{color}; border-radius:3px;"></div>'
                f'</div></div></div>'
            )
        st.markdown(items_html, unsafe_allow_html=True)

    # Per-book annotation breakdown
    annotated_books = [b for b in books if b.annotations]
    if len(annotated_books) > 1:
        st.markdown(
            '<div class="kn-section-header">Annotations per Book</div>',
            unsafe_allow_html=True,
        )
        sorted_ab = sorted(annotated_books, key=lambda b: len(b.annotations), reverse=True)
        max_ann = len(sorted_ab[0].annotations) if sorted_ab else 1
        chart_html = ""
        for i, b in enumerate(sorted_ab[:10]):
            hl = sum(1 for a in b.annotations if a.kind == "highlight")
            nt = len(b.annotations) - hl
            hl_pct = (hl / max_ann) * 100
            nt_pct = (nt / max_ann) * 100
            short = b.title[:25] + "..." if len(b.title) > 25 else b.title
            chart_html += (
                f'<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.4rem;">'
                f'<span style="font-size:0.75rem; color:#94a3b8; min-width:140px; text-align:right; '
                f'overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="{b.title}">{short}</span>'
                f'<div style="flex:1; height:20px; background:rgba(255,255,255,0.04); border-radius:5px; '
                f'overflow:hidden; display:flex;">'
                f'<div style="width:{hl_pct:.0f}%; background:{_BLUE}; height:100%;"></div>'
                f'<div style="width:{nt_pct:.0f}%; background:{_AMBER}; height:100%;"></div>'
                f'</div>'
                f'<span style="font-size:0.7rem; color:#64748b; min-width:3rem;">{hl}h {nt}n</span>'
                f'</div>'
            )
        legend = (
            f'<div style="display:flex; gap:1rem; margin-top:0.5rem; font-size:0.7rem; color:#94a3b8;">'
            f'<span style="display:flex; align-items:center; gap:0.3rem;">'
            f'<span style="width:8px; height:8px; border-radius:50%; background:{_BLUE};"></span>Highlights</span>'
            f'<span style="display:flex; align-items:center; gap:0.3rem;">'
            f'<span style="width:8px; height:8px; border-radius:50%; background:{_AMBER};"></span>Notes</span>'
            f'</div>'
        )
        st.markdown(chart_html + legend, unsafe_allow_html=True)


def _render_themes(themes: list[ThemeCluster]) -> None:
    """Render detected themes as styled cards."""
    st.markdown(
        '<div class="kn-section-header">Themes</div>',
        unsafe_allow_html=True,
    )

    for i, theme in enumerate(themes):
        color = _COLORS[i % len(_COLORS)]
        books_pills = "".join(_pill(t, color) for t in theme.book_titles[:4])
        st.markdown(
            f'<div style="border-left:3px solid {color}; padding:0.75rem 1.2rem; '
            f'margin-bottom:0.75rem; background:rgba(255,255,255,0.02); border-radius:0 8px 8px 0;">'
            f'<div style="display:flex; justify-content:space-between; align-items:baseline;">'
            f'<span style="font-weight:600; font-size:0.95rem;">{theme.label}</span>'
            f'<span style="font-size:0.7rem; color:{color}; font-weight:600;">'
            f'{theme.size} highlight{"s" if theme.size != 1 else ""}</span></div>'
            f'<div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; line-height:1.6; '
            f'font-style:italic;">"{theme.representative_text}"</div>'
            f'<div style="margin-top:0.4rem;">{books_pills}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_clusters(clusters: list[ThemeCluster]) -> None:
    """Render cross-book highlight clusters as cards."""
    st.markdown(
        '<div class="kn-section-header">Recurring Ideas Across Books</div>',
        unsafe_allow_html=True,
    )

    for i, cluster in enumerate(clusters):
        color = _COLORS[i % len(_COLORS)]
        cross = len(cluster.book_titles) > 1
        badge = (
            f'<span style="font-size:0.65rem; padding:0.1rem 0.4rem; border-radius:4px; '
            f'background:rgba(34,197,94,0.15); color:{_GREEN}; font-weight:700; margin-left:0.5rem;">'
            f'CROSS-BOOK</span>'
            if cross else ""
        )
        books_pills = "".join(_pill(t, _PURPLE) for t in cluster.book_titles[:4])
        st.markdown(
            f'<div style="border-left:3px solid {color}; padding:0.75rem 1.2rem; '
            f'margin-bottom:0.75rem; background:rgba(255,255,255,0.02); border-radius:0 8px 8px 0;">'
            f'<div style="display:flex; align-items:baseline;">'
            f'<span style="font-weight:600; font-size:0.95rem;">{cluster.label}</span>'
            f'{badge}'
            f'<span style="margin-left:auto; font-size:0.7rem; color:{color}; font-weight:600;">'
            f'{cluster.size} highlight{"s" if cluster.size != 1 else ""}</span></div>'
            f'<div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; line-height:1.6; '
            f'font-style:italic;">"{cluster.representative_text}"</div>'
            f'<div style="margin-top:0.4rem;">{books_pills}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_summaries(summaries: list[BookSummary], books: list[Book]) -> None:
    """Render book summaries as rich cards."""
    st.markdown(
        '<div class="kn-section-header">Book Summaries</div>',
        unsafe_allow_html=True,
    )

    book_map = {b.title: b for b in books}

    for i, s in enumerate(summaries):
        color = _COLORS[i % len(_COLORS)]
        book = book_map.get(s.book_title)

        # Build stat pills for the book
        pills_html = ""
        pills_html += _pill(f"{s.highlight_count} highlight{'s' if s.highlight_count != 1 else ''}", _BLUE)
        if book:
            note_count = sum(1 for a in book.annotations if a.kind == "note")
            if note_count:
                pills_html += _pill(f"{note_count} note{'s' if note_count != 1 else ''}", _AMBER)
            if book.time_spent_reading and book.time_spent_reading > 0:
                pills_html += _pill(_format_time(book.time_spent_reading), _CYAN)
            if book.rating and book.rating > 0:
                stars = "★" * book.rating + "☆" * (5 - book.rating)
                pills_html += _pill(stars, _GREEN)

        theme_pills = ""
        if s.themes:
            theme_pills = "".join(_pill(t, _PURPLE) for t in s.themes[:5])

        # Format the summary text with paragraph breaks
        paragraphs = s.summary.split("\n\n") if "\n\n" in s.summary else [s.summary]
        formatted = "".join(
            f'<p style="margin:0 0 0.5rem; line-height:1.7; font-size:0.9rem; color:#cbd5e1;">{p.strip()}</p>'
            for p in paragraphs if p.strip()
        )

        author = f' <span style="color:#94a3b8; font-weight:400;">by {book.author}</span>' if book and book.author else ""

        theme_section = f'<div style="margin-top:0.5rem;">{theme_pills}</div>' if theme_pills else ""

        st.markdown(
            f'<div style="border:1px solid #334155; border-radius:12px; padding:1.25rem; '
            f'margin-bottom:1rem; background:rgba(255,255,255,0.01);">'
            f'<div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:0.5rem;">'
            f'<span style="font-weight:700; font-size:1rem; color:{color};">{s.book_title}{author}</span>'
            f'</div>'
            f'<div style="margin-bottom:0.75rem;">{pills_html}</div>'
            f'{formatted}'
            f'{theme_section}'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_similarity_search(books: list[Book]) -> None:
    """Similarity search input and results."""
    st.markdown(
        '<div class="kn-section-header">Similarity Search</div>',
        unsafe_allow_html=True,
    )
    st.caption("Find highlights that echo a given idea across your library.")

    query = st.text_input(
        "Search query",
        placeholder="Paste a highlight or type an idea...",
        key="sim_search_query",
    )

    if query and st.button("Find similar", key="sim_search_btn"):
        provider_inst = _get_provider()
        if provider_inst is None:
            return
        from services.insights import find_similar_highlights

        with st.spinner("Searching..."):
            results = find_similar_highlights(query, books, provider_inst)
            st.session_state["sim_results"] = results

    if "sim_results" in st.session_state:
        results: list[HighlightSimilarity] = st.session_state["sim_results"]
        if not results:
            st.info("No similar highlights found above the similarity threshold.")
        else:
            for i, r in enumerate(results):
                score_pct = f"{r.score * 100:.0f}%"
                # Color-coded score bar
                score_color = _GREEN if r.score >= 0.7 else _AMBER if r.score >= 0.5 else _BLUE
                bar_w = r.score * 100
                st.markdown(
                    f'<div style="border-left:3px solid {score_color}; padding:0.75rem 1.2rem; '
                    f'margin-bottom:0.6rem; background:rgba(255,255,255,0.02); border-radius:0 8px 8px 0;">'
                    f'<div style="line-height:1.7; font-size:0.9rem;">"{r.match_text}"</div>'
                    f'<div style="display:flex; align-items:center; gap:0.75rem; margin-top:0.4rem;">'
                    f'<span style="font-size:0.75rem; color:#94a3b8;">{r.match_book}</span>'
                    f'<div style="flex:1; max-width:100px; height:4px; background:rgba(255,255,255,0.06); '
                    f'border-radius:2px; overflow:hidden;">'
                    f'<div style="height:100%; width:{bar_w:.0f}%; background:{score_color}; '
                    f'border-radius:2px;"></div></div>'
                    f'<span style="font-size:0.7rem; color:{score_color}; font-weight:600;">'
                    f'{score_pct}</span></div></div>',
                    unsafe_allow_html=True,
                )
