"""AI Insights view -- Insight Feed, evidence-backed reading intelligence.

Preserves all existing AI analysis (theme detection, clustering, similarity
search, summaries) while wrapping output in a structured Insight Feed.
"""
from __future__ import annotations

import html as html_mod
from typing import TYPE_CHECKING

import streamlit as st

from models.book import Book
from models.insight import INSIGHT_CATEGORIES, EvidenceItem, InsightCard

if TYPE_CHECKING:
    from models.insight import BookSummary, HighlightSimilarity, ThemeCluster

# ---------------------------------------------------------------------------
# Color palette (shared with other views)
# ---------------------------------------------------------------------------
_BLUE = "#3b82f6"
_GREEN = "#22c55e"
_AMBER = "#f59e0b"
_PURPLE = "#a855f7"
_ROSE = "#f43f5e"
_CYAN = "#06b6d4"
_TEAL = "#14b8a6"
_INDIGO = "#6366f1"
_COLORS = [_BLUE, _GREEN, _AMBER, _PURPLE, _ROSE, _CYAN, _TEAL, _INDIGO]

_CATEGORY_COLORS: dict[str, str] = {
    "Library Overview": _BLUE,
    "Most Engaged Books": _GREEN,
    "Highlight Behavior": _AMBER,
    "Reading Patterns": _INDIGO,
    "Books in Progress": _CYAN,
    "Vocabulary Activity": _TEAL,
    "Reading Momentum": _GREEN,
    "Forgotten Insights": _ROSE,
    "Deep Reading Signals": _PURPLE,
    "Cross-Book Themes": _PURPLE,
    "Book Summary": _BLUE,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ai_available() -> bool:
    try:
        import numpy  # noqa: F401
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


def _get_provider():
    from services.embeddings import get_provider
    try:
        return get_provider("local")
    except ImportError as exc:
        st.error(str(exc))
        return None


def _format_time(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60}m"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m}m" if m else f"{h}h"


def _pill(text: str, color: str) -> str:
    return (
        f'<span style="display:inline-block; font-size:0.68rem; padding:0.12rem 0.5rem; '
        f'border-radius:20px; border:1px solid {color}; color:{color}; '
        f'background:rgba(255,255,255,0.02); margin:0.1rem 0.05rem; white-space:nowrap;">'
        f'{html_mod.escape(text)}</span>'
    )


def _category_pill(category: str) -> str:
    color = _CATEGORY_COLORS.get(category, _BLUE)
    return (
        f'<span style="display:inline-block; font-size:0.62rem; padding:0.1rem 0.45rem; '
        f'border-radius:4px; background:rgba({_hex_to_rgb(color)},0.12); color:{color}; '
        f'font-weight:600; text-transform:uppercase; letter-spacing:0.04em;">'
        f'{html_mod.escape(category)}</span>'
    )


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip('#')
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"


def _priority_indicator(score: float) -> str:
    if score >= 0.7:
        color, label = _GREEN, "HIGH"
    elif score >= 0.45:
        color, label = _AMBER, "MEDIUM"
    else:
        color, label = "#64748b", "LOW"
    return (
        f'<span style="font-size:0.58rem; font-weight:700; color:{color}; '
        f'letter-spacing:0.05em;">{label}</span>'
    )


# ---------------------------------------------------------------------------
# CSS injection for insight-specific styles
# ---------------------------------------------------------------------------


def _inject_insight_css() -> None:
    st.markdown("""<style>
/* Insight card container */
.kn-insight-card {
    border: 1px solid rgba(150,150,150,0.12);
    border-radius: 12px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.75rem;
    background: rgba(255,255,255,0.01);
    transition: border-color 0.15s, box-shadow 0.15s;
}
.kn-insight-card:hover {
    border-color: rgba(59,130,246,0.2);
    box-shadow: 0 2px 12px rgba(59,130,246,0.04);
}
/* Card header */
.kn-ic-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.35rem;
    gap: 0.5rem;
}
.kn-ic-title {
    font-weight: 700;
    font-size: 0.95rem;
    line-height: 1.35;
    flex: 1;
}
/* Summary text */
.kn-ic-summary {
    font-size: 0.88rem;
    line-height: 1.65;
    color: #94a3b8;
    margin-bottom: 0.5rem;
}
/* Evidence block */
.kn-evidence {
    border-top: 1px solid rgba(150,150,150,0.08);
    padding-top: 0.6rem;
    margin-top: 0.5rem;
}
.kn-evidence-title {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b;
    margin-bottom: 0.35rem;
}
.kn-evidence-item {
    display: flex;
    justify-content: space-between;
    padding: 0.2rem 0;
    font-size: 0.82rem;
    border-bottom: 1px solid rgba(150,150,150,0.04);
}
.kn-evidence-item:last-child { border-bottom: none; }
.kn-evidence-label { color: #94a3b8; }
.kn-evidence-value { font-weight: 500; color: #cbd5e1; }
/* Recommendation */
.kn-rec {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.6rem 0.8rem;
    border-radius: 8px;
    background: rgba(59,130,246,0.04);
    border: 1px solid rgba(59,130,246,0.1);
    font-size: 0.82rem;
    color: #94a3b8;
    margin-top: 0.5rem;
    line-height: 1.55;
}
.kn-rec-label {
    font-weight: 700;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #3b82f6;
    flex-shrink: 0;
    margin-top: 1px;
}
/* Takeaway bar */
.kn-takeaway-bar {
    border: 1px solid rgba(139,92,246,0.15);
    border-radius: 12px;
    padding: 1rem 1.3rem;
    background: rgba(139,92,246,0.03);
    margin-bottom: 1.25rem;
}
.kn-takeaway-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #a855f7;
    margin-bottom: 0.55rem;
}
.kn-takeaway-item {
    font-size: 0.85rem;
    color: #cbd5e1;
    padding: 0.25rem 0;
    line-height: 1.55;
    border-bottom: 1px solid rgba(150,150,150,0.05);
}
.kn-takeaway-item:last-child { border-bottom: none; }
.kn-takeaway-num {
    display: inline-block;
    width: 18px;
    height: 18px;
    line-height: 18px;
    border-radius: 50%;
    background: rgba(168,85,247,0.15);
    color: #a855f7;
    text-align: center;
    font-size: 0.62rem;
    font-weight: 700;
    margin-right: 0.5rem;
}
/* Expander tweaks */
.kn-insights-page details {
    border: none !important;
}
.kn-insights-page summary {
    font-weight: 600;
}
/* ---- AI Analysis section ---- */
.kn-ai-header {
    margin-bottom: 0.75rem;
}
.kn-ai-title {
    font-size: 1.15rem;
    font-weight: 800;
    letter-spacing: -0.01em;
}
.kn-ai-subtitle {
    font-size: 0.82rem;
    color: #64748b;
    margin-top: 0.1rem;
}
/* Book group in themes tab */
.kn-ai-book-group {
    margin-top: 1.1rem;
    margin-bottom: 0.6rem;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid rgba(150,150,150,0.08);
}
.kn-ai-book-group:first-child {
    margin-top: 0;
}
.kn-ai-book-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: #e2e8f0;
}
.kn-ai-book-meta {
    font-size: 0.72rem;
    color: #64748b;
    margin-top: 0.1rem;
}
/* Theme card */
.kn-theme-card {
    border-left: 3px solid #3b82f6;
    padding: 0.65rem 1rem;
    margin-bottom: 0.5rem;
    background: rgba(255,255,255,0.015);
    border-radius: 0 8px 8px 0;
    transition: background 0.15s;
}
.kn-theme-card:hover {
    background: rgba(255,255,255,0.035);
}
.kn-theme-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
}
.kn-theme-label {
    font-weight: 700;
    font-size: 0.87rem;
}
.kn-theme-quote {
    font-size: 0.82rem;
    color: #94a3b8;
    line-height: 1.6;
    font-style: italic;
}
/* Connection card */
.kn-connection-card {
    border: 1px solid rgba(168,85,247,0.15);
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.6rem;
    background: rgba(168,85,247,0.02);
    transition: border-color 0.15s;
}
.kn-connection-card:hover {
    border-color: rgba(168,85,247,0.3);
}
.kn-connection-card.kn-single {
    border-color: rgba(150,150,150,0.1);
    background: rgba(255,255,255,0.01);
}
.kn-connection-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.35rem;
    flex-wrap: wrap;
    gap: 0.3rem;
}
.kn-connection-label {
    font-weight: 700;
    font-size: 0.88rem;
    color: #a855f7;
}
.kn-connection-badge {
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    background: rgba(168,85,247,0.12);
    color: #a855f7;
}
.kn-connection-quote {
    font-size: 0.82rem;
    color: #94a3b8;
    line-height: 1.6;
    font-style: italic;
    margin-bottom: 0.4rem;
}
.kn-connection-books {
    margin-top: 0.35rem;
}
/* Summary card */
.kn-summary-card {
    border: 1px solid rgba(150,150,150,0.1);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
    background: rgba(255,255,255,0.015);
    transition: border-color 0.15s;
}
.kn-summary-card:hover {
    border-color: rgba(59,130,246,0.2);
}
.kn-summary-title {
    font-size: 0.95rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
}
.kn-summary-author {
    font-weight: 400;
    font-size: 0.82rem;
    color: #64748b;
    margin-left: 0.25rem;
}
.kn-summary-stats {
    margin-bottom: 0.55rem;
}
.kn-summary-body {
    font-size: 0.85rem;
    line-height: 1.7;
    color: #cbd5e1;
}
.kn-summary-body p {
    margin: 0 0 0.4rem;
}
.kn-summary-themes {
    margin-top: 0.5rem;
    padding-top: 0.4rem;
    border-top: 1px solid rgba(150,150,150,0.06);
}
/* AI empty state */
.kn-ai-empty {
    text-align: center;
    padding: 2rem 1rem;
    color: #64748b;
    font-size: 0.85rem;
    line-height: 1.6;
}
/* Search result */
.kn-search-result {
    border-left: 3px solid #3b82f6;
    padding: 0.65rem 1rem;
    margin-bottom: 0.5rem;
    background: rgba(255,255,255,0.02);
    border-radius: 0 8px 8px 0;
    transition: background 0.15s;
}
.kn-search-result:hover {
    background: rgba(255,255,255,0.035);
}
.kn-search-quote {
    line-height: 1.65;
    font-size: 0.88rem;
    color: #e2e8f0;
}
.kn-search-meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 0.35rem;
}
.kn-search-book {
    font-size: 0.75rem;
    color: #94a3b8;
}
.kn-search-bar-bg {
    flex: 1;
    max-width: 100px;
    height: 4px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    overflow: hidden;
}
.kn-search-bar-fill {
    height: 100%;
    border-radius: 2px;
}
.kn-search-score {
    font-size: 0.7rem;
    font-weight: 600;
}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Card rendering
# ---------------------------------------------------------------------------


def _render_card(card: InsightCard, key_suffix: str = "") -> None:
    """Render a single InsightCard with collapsible detail."""
    color = _CATEGORY_COLORS.get(card.category, _BLUE)

    # Card header outside expander -- scannable preview
    header_html = (
        f'<div class="kn-insight-card">'
        f'<div class="kn-ic-header">'
        f'<div>{_category_pill(card.category)} '
        f'{_priority_indicator(card.priority_score)}</div>'
        f'</div>'
        f'<div class="kn-ic-title" style="color:{color};">'
        f'{html_mod.escape(card.title)}</div>'
        f'<div class="kn-ic-summary">{html_mod.escape(card.summary)}</div>'
    )

    # Related books pills
    if card.related_books:
        pills = "".join(_pill(b, color) for b in card.related_books[:5])
        header_html += f'<div style="margin-top:0.25rem;">{pills}</div>'

    header_html += '</div>'
    st.markdown(header_html, unsafe_allow_html=True)

    # Collapsible detail
    has_detail = card.body or card.evidence or card.recommendation
    if has_detail:
        with st.expander("View details", expanded=False):
            if card.body:
                # Render body with paragraph formatting
                paragraphs = card.body.split('\n\n') if '\n\n' in card.body else [card.body]
                for p in paragraphs:
                    if p.strip():
                        st.markdown(
                            f'<p style="font-size:0.88rem; line-height:1.7; color:#cbd5e1; margin:0 0 0.5rem;">'
                            f'{html_mod.escape(p.strip())}</p>',
                            unsafe_allow_html=True,
                        )

            if card.evidence:
                ev_html = '<div class="kn-evidence">'
                ev_html += '<div class="kn-evidence-title">Supporting Evidence</div>'
                for ev in card.evidence:
                    ev_html += (
                        f'<div class="kn-evidence-item">'
                        f'<span class="kn-evidence-label">{html_mod.escape(ev.label)}</span>'
                        f'<span class="kn-evidence-value">{html_mod.escape(ev.value)}</span>'
                        f'</div>'
                    )
                ev_html += '</div>'
                st.markdown(ev_html, unsafe_allow_html=True)

            if card.recommendation:
                st.markdown(
                    f'<div class="kn-rec">'
                    f'<span class="kn-rec-label">Next Step</span>'
                    f'{html_mod.escape(card.recommendation)}'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Takeaway summary bar
# ---------------------------------------------------------------------------


def _render_takeaway_bar(takeaways: list[str]) -> None:
    if not takeaways:
        return
    items_html = ""
    for i, t in enumerate(takeaways, 1):
        items_html += (
            f'<div class="kn-takeaway-item">'
            f'<span class="kn-takeaway-num">{i}</span>'
            f'{html_mod.escape(t)}'
            f'</div>'
        )
    st.markdown(
        f'<div class="kn-takeaway-bar">'
        f'<div class="kn-takeaway-title">Reading Intelligence Summary</div>'
        f'{items_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Filters sidebar
# ---------------------------------------------------------------------------


def _render_filters(
    books: list[Book],
    available_categories: list[str],
) -> dict:
    """Render filter controls and return the filter state."""
    with st.expander("Filters", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            selected_cats = st.multiselect(
                "Categories",
                available_categories,
                default=[],
                key="insight_cat_filter",
            )
        with col2:
            book_titles = ["All books"] + sorted(b.title for b in books if b.annotations)
            selected_book = st.selectbox(
                "Book",
                book_titles,
                key="insight_book_filter",
            )

        col3, col4 = st.columns(2)
        with col3:
            min_priority = st.select_slider(
                "Minimum priority",
                options=["All", "Low+", "Medium+", "High"],
                value="All",
                key="insight_priority_filter",
            )
        with col4:
            actionable_only = st.checkbox("Actionable only", key="insight_actionable_filter")

    priority_map = {"All": 0.0, "Low+": 0.2, "Medium+": 0.45, "High": 0.7}

    return {
        "categories": selected_cats or None,
        "book_filter": None if selected_book == "All books" else selected_book,
        "min_priority": priority_map.get(min_priority, 0.0),
        "actionable_only": actionable_only,
    }


# ---------------------------------------------------------------------------
# Export controls
# ---------------------------------------------------------------------------


def _render_export(cards: list[InsightCard]) -> None:
    """Render export buttons for the insight feed."""
    if not cards:
        return

    from services.insight_export import export_insights_markdown, export_insights_text

    with st.expander("Export Insights", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            md = export_insights_markdown(cards)
            st.download_button(
                "Download Markdown",
                data=md,
                file_name="konotes-insights.md",
                mime="text/markdown",
                key="dl_insights_md",
            )
        with col2:
            txt = export_insights_text(cards)
            st.download_button(
                "Download Plain Text",
                data=txt,
                file_name="konotes-insights.txt",
                mime="text/plain",
                key="dl_insights_txt",
            )


# ---------------------------------------------------------------------------
# AI Analysis rendering
# ---------------------------------------------------------------------------


def _render_themes(themes: list[ThemeCluster]) -> None:
    """Render detected themes, grouped by book with rich theme cards."""
    if not themes:
        st.markdown(
            '<div class="kn-ai-empty">'
            '<div style="font-weight:600; margin-bottom:0.25rem;">No themes detected yet</div>'
            'Click <strong>Run Full Analysis</strong> or <strong>Themes</strong> above '
            'to discover semantic themes in your highlights.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Group themes by book
    book_themes: dict[str, list[ThemeCluster]] = {}
    for theme in themes:
        book_title = theme.book_titles[0] if theme.book_titles else "Unknown"
        book_themes.setdefault(book_title, []).append(theme)

    for book_title, theme_list in book_themes.items():
        total_hl = sum(t.size for t in theme_list)
        st.markdown(
            f'<div class="kn-ai-book-group">'
            f'<div class="kn-ai-book-title">{html_mod.escape(book_title)}</div>'
            f'<div class="kn-ai-book-meta">'
            f'{len(theme_list)} theme{"s" if len(theme_list) != 1 else ""} '
            f'&middot; {total_hl} highlights</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        for i, theme in enumerate(theme_list):
            color = _COLORS[i % len(_COLORS)]
            rep = html_mod.escape(theme.representative_text)
            if len(theme.representative_text) > 220:
                rep = html_mod.escape(theme.representative_text[:220].rsplit(" ", 1)[0]) + "..."
            st.markdown(
                f'<div class="kn-theme-card" style="border-left-color:{color};">'
                f'<div class="kn-theme-header">'
                f'<span class="kn-theme-label" style="color:{color};">'
                f'{html_mod.escape(theme.label)}</span>'
                f'{_pill(f"{theme.size} highlights", color)}'
                f'</div>'
                f'<div class="kn-theme-quote">&ldquo;{rep}&rdquo;</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_connection_card(
    cluster: ThemeCluster, idx: int, *, is_cross: bool,
) -> None:
    """Render a single connection / cluster card."""
    color = _PURPLE if is_cross else _COLORS[idx % len(_COLORS)]
    card_cls = "kn-connection-card" if is_cross else "kn-connection-card kn-single"
    badge = '<span class="kn-connection-badge">CROSS-BOOK</span>' if is_cross else ""
    books_pills = "".join(_pill(t, _PURPLE) for t in cluster.book_titles[:5])
    rep = html_mod.escape(cluster.representative_text)
    if len(cluster.representative_text) > 220:
        rep = html_mod.escape(cluster.representative_text[:220].rsplit(" ", 1)[0]) + "..."
    st.markdown(
        f'<div class="{card_cls}">'
        f'<div class="kn-connection-header">'
        f'<span class="kn-connection-label" style="color:{color};">'
        f'{html_mod.escape(cluster.label)}</span>'
        f'<div>{_pill(f"{cluster.size} highlights", color)} {badge}</div>'
        f'</div>'
        f'<div class="kn-connection-quote">&ldquo;{rep}&rdquo;</div>'
        f'<div class="kn-connection-books">{books_pills}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_clusters(clusters: list[ThemeCluster]) -> None:
    """Render cross-book clusters as connection cards."""
    if not clusters:
        st.markdown(
            '<div class="kn-ai-empty">'
            '<div style="font-weight:600; margin-bottom:0.25rem;">No connections found yet</div>'
            'Click <strong>Run Full Analysis</strong> or <strong>Connections</strong> above '
            'to find recurring ideas across your books.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    cross_book = [c for c in clusters if len(c.book_titles) > 1]
    single_book = [c for c in clusters if len(c.book_titles) <= 1]

    if cross_book:
        st.markdown(
            f'<div style="font-size:0.78rem; color:{_PURPLE}; font-weight:600; '
            f'margin-bottom:0.6rem;">'
            f'{len(cross_book)} idea{"s" if len(cross_book) != 1 else ""} '
            f'shared across multiple books</div>',
            unsafe_allow_html=True,
        )
        for i, c in enumerate(cross_book):
            _render_connection_card(c, i, is_cross=True)

    if single_book:
        with st.expander(
            f"{len(single_book)} single-book cluster{'s' if len(single_book) != 1 else ''}",
            expanded=False,
        ):
            for i, c in enumerate(single_book):
                _render_connection_card(c, i, is_cross=False)


def _render_summaries(summaries: list[BookSummary], books: list[Book]) -> None:
    """Render book summaries as rich cards with stats and themes."""
    if not summaries:
        st.markdown(
            '<div class="kn-ai-empty">'
            '<div style="font-weight:600; margin-bottom:0.25rem;">No summaries generated yet</div>'
            'Click <strong>Run Full Analysis</strong> or <strong>Summaries</strong> above '
            'to generate reading summaries for each book.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    book_map = {b.title: b for b in books}

    for i, s in enumerate(summaries):
        color = _COLORS[i % len(_COLORS)]
        book = book_map.get(s.book_title)

        # Build stat pills
        stats: list[str] = [
            f"{s.highlight_count} highlight{'s' if s.highlight_count != 1 else ''}"
        ]
        if book:
            note_count = sum(1 for a in book.annotations if a.kind == "note")
            if note_count:
                stats.append(f"{note_count} note{'s' if note_count != 1 else ''}")
            if book.time_spent_reading and book.time_spent_reading > 0:
                stats.append(_format_time(book.time_spent_reading))
            if book.read_percent is not None:
                stats.append(f"{book.read_percent:.0f}% read")
            if book.rating and book.rating > 0:
                stats.append(f"Rated {book.rating}/5")

        stats_pills = "".join(_pill(st_text, color) for st_text in stats)
        theme_pills = "".join(_pill(t, _PURPLE) for t in s.themes[:5]) if s.themes else ""

        author = f" by {html_mod.escape(book.author)}" if book and book.author else ""

        # Summary text
        paragraphs = s.summary.split("\n\n") if "\n\n" in s.summary else [s.summary]
        body_html = ""
        for p in paragraphs:
            if p.strip():
                body_html += f"<p>{html_mod.escape(p.strip())}</p>"

        themes_block = (
            f'<div class="kn-summary-themes">{theme_pills}</div>' if theme_pills else ""
        )

        st.markdown(
            f'<div class="kn-summary-card">'
            f'<div class="kn-summary-title" style="color:{color};">'
            f'{html_mod.escape(s.book_title)}'
            f'<span class="kn-summary-author">{author}</span></div>'
            f'<div class="kn-summary-stats">{stats_pills}</div>'
            f'<div class="kn-summary-body">{body_html}</div>'
            f'{themes_block}'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_similarity_search(books: list[Book]) -> None:
    """Render the semantic similarity search interface."""
    st.markdown(
        '<div style="font-size:0.82rem; color:#64748b; margin-bottom:0.75rem;">'
        'Paste a highlight or type an idea to find similar passages across your library.'
        '</div>',
        unsafe_allow_html=True,
    )
    query = st.text_input(
        "Search query",
        placeholder="Paste a highlight or type an idea...",
        key="sim_search_query",
    )
    if query and st.button("Find similar highlights", key="sim_search_btn", width="stretch"):
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
            st.markdown(
                f'<div style="font-size:0.72rem; color:#64748b; margin-bottom:0.5rem;">'
                f'{len(results)} match{"es" if len(results) != 1 else ""} found</div>',
                unsafe_allow_html=True,
            )
            for r in results:
                score_pct = f"{r.score * 100:.0f}%"
                score_color = _GREEN if r.score >= 0.7 else _AMBER if r.score >= 0.5 else _BLUE
                bar_w = r.score * 100
                st.markdown(
                    f'<div class="kn-search-result" style="border-left-color:{score_color};">'
                    f'<div class="kn-search-quote">&ldquo;{html_mod.escape(r.match_text)}&rdquo;</div>'
                    f'<div class="kn-search-meta">'
                    f'<span class="kn-search-book">{html_mod.escape(r.match_book)}</span>'
                    f'<div class="kn-search-bar-bg">'
                    f'<div class="kn-search-bar-fill" style="width:{bar_w:.0f}%; '
                    f'background:{score_color};"></div></div>'
                    f'<span class="kn-search-score" style="color:{score_color};">'
                    f'{score_pct}</span></div></div>',
                    unsafe_allow_html=True,
                )
    elif not query:
        st.markdown(
            '<div class="kn-ai-empty">'
            '<div style="font-weight:600; margin-bottom:0.25rem;">Semantic highlight search</div>'
            'Type a phrase or idea above and click <strong>Find similar highlights</strong> '
            'to discover related passages across your entire library.'
            '</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def render_insights(books: list[Book]) -> None:
    """Render the AI Insights page with the Insight Feed experience."""

    _inject_insight_css()

    st.markdown('<div class="kn-insights-page">', unsafe_allow_html=True)

    st.markdown(
        '<div style="margin-bottom:0.25rem;">'
        '<span style="font-size:1.6rem; font-weight:800; letter-spacing:-0.02em;">'
        'Reading Intelligence</span>'
        '<div style="font-size:0.85rem; color:#64748b; margin-top:0.15rem;">'
        'Evidence-backed insights from your Kobo library</div></div>',
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # 1. Build the Insight Feed
    # ------------------------------------------------------------------
    from services.insight_feed import build_feed, extract_takeaways

    word_lookups = st.session_state.get("word_lookups", [])
    all_cards = build_feed(books, word_lookups=word_lookups)

    # ------------------------------------------------------------------
    # 2. Filters
    # ------------------------------------------------------------------
    available_cats = sorted({c.category for c in all_cards})
    filters = _render_filters(books, available_cats)

    # Apply filters
    visible = all_cards
    if filters["categories"]:
        cat_set = {c.lower() for c in filters["categories"]}
        visible = [c for c in visible if c.category.lower() in cat_set]
    if filters["book_filter"]:
        visible = [c for c in visible if filters["book_filter"] in c.related_books]
    if filters["min_priority"] > 0:
        visible = [c for c in visible if c.priority_score >= filters["min_priority"]]
    if filters["actionable_only"]:
        visible = [c for c in visible if c.recommendation]

    # ------------------------------------------------------------------
    # 3. Takeaway summary
    # ------------------------------------------------------------------
    takeaways = extract_takeaways(all_cards)
    _render_takeaway_bar(takeaways)

    # ------------------------------------------------------------------
    # 4. Feed stats
    # ------------------------------------------------------------------
    st.markdown(
        f'<div style="font-size:0.78rem; color:#64748b; margin-bottom:0.75rem;">'
        f'{len(visible)} insight{"s" if len(visible) != 1 else ""} '
        f'across {len(available_cats)} categories</div>',
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # 5. Render insight cards
    # ------------------------------------------------------------------
    if not visible:
        st.info("No insights match your current filters.")
    else:
        # Group by category for clean sections
        current_category = ""
        for card in visible:
            if card.category != current_category:
                current_category = card.category
                st.markdown(
                    f'<div class="kn-section-header" style="margin-top:1.5rem;">'
                    f'{html_mod.escape(current_category)}</div>',
                    unsafe_allow_html=True,
                )
            _render_card(card)

    # ------------------------------------------------------------------
    # 6. Export
    # ------------------------------------------------------------------
    st.divider()
    _render_export(visible)

    # ------------------------------------------------------------------
    # 7. AI-powered analysis (redesigned)
    # ------------------------------------------------------------------
    if not _ai_available():
        st.info(
            "AI-powered theme detection, clustering, and similarity search "
            "require additional dependencies. Install with: `pip install 'konotes[ai]'`"
        )
    else:
        st.divider()
        st.markdown(
            '<div class="kn-ai-header">'
            '<div class="kn-ai-title">AI Analysis</div>'
            '<div class="kn-ai-subtitle">'
            'Embedding-based semantic analysis of your highlights -- discover themes, '
            'cross-book connections, and reading summaries.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        highlights = [
            a for book in books for a in book.annotations
            if a.kind == "highlight" and a.text.strip()
        ]

        if len(highlights) < 3:
            st.info("Need at least 3 highlights to run AI analysis.")
        else:
            st.markdown(
                f'<div style="font-size:0.78rem; color:#64748b; margin-bottom:0.75rem;">'
                f'{len(highlights)} highlights across '
                f'{len(books)} book{"s" if len(books) != 1 else ""} '
                f'available for analysis</div>',
                unsafe_allow_html=True,
            )

            # -- Run controls --
            col_run, col_t, col_c, col_s = st.columns([2.5, 1, 1, 1])
            with col_run:
                run_all = st.button(
                    "Run Full Analysis",
                    type="primary",
                    width="stretch",
                    key="ai_run_all",
                )
            with col_t:
                run_themes = st.button("Themes", width="stretch", key="ai_run_themes")
            with col_c:
                run_cluster = st.button(
                    "Connections", width="stretch", key="ai_run_clusters",
                )
            with col_s:
                run_summary = st.button(
                    "Summaries", width="stretch", key="ai_run_summaries",
                )

            # -- Execute analyses --
            if run_all or run_themes:
                provider_inst = _get_provider()
                if provider_inst is not None:
                    from services.insights import detect_themes
                    with st.spinner("Detecting themes across your library..."):
                        all_themes: list[ThemeCluster] = []
                        for book in books:
                            bh = [
                                a for a in book.annotations
                                if a.kind == "highlight" and a.text.strip()
                            ]
                            if len(bh) >= 3:
                                all_themes.extend(detect_themes(book, provider_inst))
                        st.session_state["ai_themes"] = all_themes

            if run_all or run_cluster:
                provider_inst = _get_provider()
                if provider_inst is not None:
                    from services.insights import cluster_highlights_across_books
                    with st.spinner("Finding connections across books..."):
                        clusters = cluster_highlights_across_books(books, provider_inst)
                        st.session_state["ai_clusters"] = clusters

            if run_all or run_summary:
                from services.summaries import generate_summary
                with st.spinner("Generating book summaries..."):
                    summaries: list[BookSummary] = []
                    for book in books:
                        if book.annotations:
                            themes = st.session_state.get("ai_themes", [])
                            book_themes = [
                                t for t in themes if book.title in t.book_titles
                            ]
                            summaries.append(
                                generate_summary(book, themes=book_themes),
                            )
                    st.session_state["ai_summaries"] = summaries

            # -- Results in tabs --
            tab_themes, tab_connections, tab_summaries, tab_search = st.tabs([
                "Themes by Book",
                "Cross-Book Connections",
                "Book Summaries",
                "Semantic Search",
            ])

            with tab_themes:
                _render_themes(st.session_state.get("ai_themes", []))

            with tab_connections:
                _render_clusters(st.session_state.get("ai_clusters", []))

            with tab_summaries:
                _render_summaries(
                    st.session_state.get("ai_summaries", []),
                    books,
                )

            with tab_search:
                _render_similarity_search(books)

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    st.markdown(
        '<div class="kn-footer">Made with love for the Kobo community.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)
