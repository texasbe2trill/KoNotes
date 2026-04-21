"""Overview dashboard -- library-wide reading intelligence at a glance."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Callable

import plotly.graph_objects as go
import streamlit as st

from app.charts import (
    AMBER,
    AMBER_GRADIENT,
    BLUE,
    BLUE_GRADIENT,
    BLUE_LIGHT,
    CYAN,
    GREEN,
    GREEN_GRADIENT,
    GRAY,
    PALETTE,
    PURPLE,
    PURPLE_GRADIENT,
    ROSE,
    figure,
    styled_axis,
)
from app.components.hero_insight import render_hero_insight
from app.components.recommendation_card import render_recommendation_section
from models.activity import ProgressSnapshot, ReadingSession
from models.book import Book
from models.vocabulary import WordLookup
from services.hero_insight_engine import generate_hero_insight
from services.recommendation_ranking import rank_recommendations
from services.recommender import generate_recommendations
from services.stats import LibraryStats, compute_stats


def render_overview(
    books: list[Book],
    sessions: list[ReadingSession],
    snapshots: list[ProgressSnapshot],
    navigate: Callable[..., None],
    word_lookups: list[WordLookup] | None = None,
    data_source: str = "kobo",
    using_demo: bool = False,
) -> None:
    stats = compute_stats(books)
    word_lookups = word_lookups or []
    is_kindle = data_source == "kindle"

    render_landing_header(using_demo=using_demo, has_data=bool(books))

    if not books:
        st.caption("Upload your KoboReader.sqlite or Kindle My Clippings.txt from the sidebar to get started.")
        return

    st.caption(
        f"{stats.total_books} books  /  {stats.total_annotations} annotations  /  "
        f"{stats.total_highlights} highlights  /  {stats.total_notes} notes"
    )

    # Hero insight — the "instant view" at the top of the page.
    if books:
        longest_streak = _compute_streak(stats.reading_activity_by_day) if stats.reading_activity_by_day else 0
        hero = generate_hero_insight(
            stats,
            books,
            word_lookups=word_lookups,
            longest_streak=longest_streak,
            total_reading_time_sec=stats.total_reading_time_sec,
        )
        render_hero_insight(hero)

    # Recommendations — deterministic, grounded next steps from the user's own library.
    recs = generate_recommendations(books, stats, word_lookups=word_lookups)
    ranked = rank_recommendations(recs, max_results=3)
    render_recommendation_section(ranked, books=books)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Books", stats.total_books)
    c2.metric("Highlights", stats.total_highlights)
    c3.metric("Notes", stats.total_notes)
    if is_kindle:
        c4.metric("Date Range", _kindle_date_range(books))
        c5.metric("Avg HL / Book", stats.avg_highlights_per_book)
        c6.metric("Active Days", len(stats.reading_activity_by_day))
    else:
        c4.metric("Reading Time", _format_reading_time(stats.total_reading_time_sec))
        c5.metric("Words Looked Up", len(word_lookups))
        c6.metric("Avg HL / Book", stats.avg_highlights_per_book)

    st.markdown("")

    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        _render_annotation_trend(stats)

    with col_right:
        _render_annotation_type_split(stats)

    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        _render_top_highlighted(stats, navigate)

    with col_b:
        _render_top_authors(stats)

    col_c, col_d = st.columns(2, gap="large")

    with col_c:
        if is_kindle:
            _render_annotation_density(books)
        else:
            _render_progress_overview(stats, books)

    with col_d:
        if is_kindle:
            _render_highlight_note_ratio(books)
        else:
            _render_reading_time_chart(stats)

    col_e, col_f = st.columns(2, gap="large")

    with col_e:
        if is_kindle:
            _render_kindle_page_coverage(books)
        else:
            _render_vocabulary(word_lookups, books)

    with col_f:
        _render_shelves_and_recent(stats, books, sessions)

    _community = "Kindle & Kobo" if is_kindle else "Kobo"
    st.markdown(
        f'<div class="kn-footer">Made with love for the {_community} community.</div>',
        unsafe_allow_html=True,
    )


def render_landing_header(using_demo: bool, has_data: bool) -> None:
    """Contextual header shown at the top of the Overview tab.

    When the user has data loaded, only a quiet status line is shown — the
    app title already provides the product name so no duplicate is needed.
    The full onboarding copy is shown only before any data is loaded.
    """
    if has_data:
        label = (
            "Using sample data \u2014 upload your own to personalize."
            if using_demo
            else "Showing your reading data."
        )
        st.markdown(
            f"<div class='kn-landing-footer' style='margin-bottom:0.5rem;'>{label}</div>",
            unsafe_allow_html=True,
        )
        return

    # No data yet — show full onboarding copy.
    st.markdown("<div class='kn-landing-wrap'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='kn-landing-subtitle'>"
        "Your reading already says something about you.<br>"
        "KoNotes helps you see it."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='kn-landing-body'>"
        "Upload your Kobo or Kindle data to uncover:"
        "<ul>"
        "<li>what you return to</li>"
        "<li>where you slow down</li>"
        "<li>what's worth revisiting</li>"
        "</ul>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("##")


# ═════════════════════════════════════════════════════════════════
# Component renderers
# ═════════════════════════════════════════════════════════════════


def _render_insight(
    stats: LibraryStats, books: list[Book], sessions: list[ReadingSession]
) -> None:
    """Generate a plain-language reading insight."""
    parts: list[str] = []

    if stats.top_authors:
        top_author, top_count = stats.top_authors[0]
        parts.append(
            f"Your most-read author is <strong>{top_author}</strong> ({top_count} book{'s' if top_count != 1 else ''})."
        )

    if stats.books_by_highlight_count:
        top_title, top_hl = stats.books_by_highlight_count[0]
        if top_hl > 0:
            parts.append(f"<strong>{top_title}</strong> is your most highlighted book with {top_hl} highlights.")

    # Reading streak
    if stats.reading_activity_by_day:
        streak = _compute_streak(stats.reading_activity_by_day)
        if streak >= 3:
            parts.append(f"Your longest annotation streak is <strong>{streak} consecutive days</strong>.")

    if parts:
        st.markdown(
            '<div class="kn-insight">'
            '<span class="kn-insight-label">Insight</span> '
            + " ".join(parts)
            + "</div>",
            unsafe_allow_html=True,
        )


def _compute_streak(activity_by_day: list[tuple[str, int]]) -> int:
    """Compute the longest streak of consecutive days with annotations."""
    dates = sorted({d for d, _ in activity_by_day})
    if not dates:
        return 0
    best = 1
    current = 1
    for i in range(1, len(dates)):
        prev = datetime.strptime(dates[i - 1], "%Y-%m-%d").date()
        curr = datetime.strptime(dates[i], "%Y-%m-%d").date()
        if (curr - prev).days == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def _render_annotation_trend(stats: LibraryStats) -> None:
    """Area chart: annotation volume over time (weekly buckets)."""
    st.markdown('<div class="kn-section-header">Annotation Activity</div>', unsafe_allow_html=True)

    if not stats.reading_activity_by_day or len(stats.reading_activity_by_day) < 2:
        st.caption("Not enough annotation data to show a trend.")
        return

    # Aggregate to weekly buckets for a cleaner look
    from collections import defaultdict

    weekly: dict[str, int] = defaultdict(int)
    for day_str, count in stats.reading_activity_by_day:
        dt = datetime.strptime(day_str, "%Y-%m-%d")
        week_start = dt - timedelta(days=dt.weekday())
        weekly[week_start.strftime("%Y-%m-%d")] += count

    weeks = sorted(weekly.keys())
    counts = [weekly[w] for w in weeks]
    labels = [datetime.strptime(w, "%Y-%m-%d").strftime("%b %d") for w in weeks]

    fig = figure(
        data=[
            go.Scatter(
                x=labels,
                y=counts,
                mode="lines",
                fill="tozeroy",
                line=dict(color=BLUE, width=2.5, shape="spline"),
                fillcolor="rgba(59,130,246,0.1)",
                hovertemplate="%{x}<br>%{y} annotations<extra></extra>",
            )
        ],
        height=260,
        xaxis=styled_axis(show_grid=False, tickangle=-45),
        yaxis=styled_axis(title="Annotations"),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_annotation_type_split(stats: LibraryStats) -> None:
    """Donut chart: highlights vs notes vs other."""
    st.markdown('<div class="kn-section-header">Annotation Breakdown</div>', unsafe_allow_html=True)

    type_counts = stats.annotation_type_counts
    if not type_counts or sum(type_counts.values()) == 0:
        st.caption("No annotation type data.")
        return

    labels = []
    values = []
    colors = []
    _color_map = {"highlight": AMBER, "note": BLUE, "unknown": GRAY}
    _label_map = {"highlight": "Highlights", "note": "Notes", "unknown": "Other"}
    for kind in ["highlight", "note", "unknown"]:
        if type_counts.get(kind, 0) > 0:
            labels.append(_label_map.get(kind, kind.title()))
            values.append(type_counts[kind])
            colors.append(_color_map.get(kind, GRAY))

    fig = figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="#0f172a", width=2)),
                textinfo="label+percent",
                textfont=dict(size=12, color="#e2e8f0"),
                hovertemplate="%{label}: %{value}<extra></extra>",
            )
        ],
        height=260,
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_top_highlighted(stats: LibraryStats, navigate: Callable) -> None:
    """Horizontal bar chart: most highlighted books."""
    st.markdown('<div class="kn-section-header">Most Highlighted Books</div>', unsafe_allow_html=True)

    top = [(t, c) for t, c in stats.books_by_highlight_count[:8] if c > 0]
    if not top:
        st.caption("No highlights yet.")
        return

    titles = [t[:30] + "..." if len(t) > 30 else t for t, _ in top]
    counts = [c for _, c in top]

    # Reverse for horizontal bar (top item at top)
    titles.reverse()
    counts.reverse()

    fig = figure(
        data=[
            go.Bar(
                x=counts,
                y=titles,
                orientation="h",
                marker=dict(
                    color=counts,
                    colorscale=BLUE_GRADIENT,
                    line=dict(width=0),
                    cornerradius=4,
                ),
                hovertemplate="%{y}<br>%{x} highlights<extra></extra>",
            )
        ],
        height=260,
        xaxis=styled_axis(title="Highlights"),
        yaxis=styled_axis(show_grid=False),
        margin=dict(l=0, r=10, t=10, b=30),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_top_authors(stats: LibraryStats) -> None:
    """Ranked list of top authors."""
    st.markdown('<div class="kn-section-header">Top Authors</div>', unsafe_allow_html=True)

    if not stats.top_authors:
        st.caption("No author data available.")
        return

    items_html = ""
    for i, (author, count) in enumerate(stats.top_authors[:8], 1):
        items_html += (
            f'<div class="kn-list-item">'
            f'<div><span class="kn-list-rank">{i}</span>{author}</div>'
            f'<span class="kn-list-value">{count} book{"s" if count != 1 else ""}</span>'
            f'</div>'
        )

    st.markdown(items_html, unsafe_allow_html=True)


def _render_progress_overview(stats: LibraryStats, books: list[Book]) -> None:
    """Donut chart: reading progress distribution."""
    st.markdown('<div class="kn-section-header">Reading Progress</div>', unsafe_allow_html=True)

    dist = {k: v for k, v in stats.progress_distribution.items() if v > 0}
    if not dist:
        st.caption("No reading progress data available.")
        return

    # Build per-bucket book title lists
    buckets: dict[str, list[str]] = {k: [] for k in dist}
    for book in books:
        pct = book.read_percent
        if pct is None:
            continue
        if pct <= 0:
            key = "0%"
        elif pct <= 25:
            key = "1-25%"
        elif pct <= 50:
            key = "26-50%"
        elif pct <= 75:
            key = "51-75%"
        elif pct < 100:
            key = "76-99%"
        else:
            key = "100%"
        if key in buckets:
            buckets[key].append(book.title)

    labels = list(dist.keys())
    values = list(dist.values())

    # Build custom hover text showing book titles per bucket
    custom_hover: list[str] = []
    for label in labels:
        titles = buckets.get(label, [])
        if len(titles) <= 5:
            title_list = "<br>".join(titles)
        else:
            title_list = "<br>".join(titles[:5]) + f"<br>+{len(titles) - 5} more"
        custom_hover.append(f"<b>{label}</b>: {len(titles)} books<br>{title_list}")

    _prog_colors = {
        "0%": "#475569",
        "1-25%": ROSE,
        "26-50%": AMBER,
        "51-75%": PURPLE,
        "76-99%": BLUE,
        "100%": GREEN,
    }
    colors = [_prog_colors.get(l, GRAY) for l in labels]

    fig = figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="#0f172a", width=2)),
                textinfo="label+value",
                textfont=dict(size=11, color="#e2e8f0"),
                hovertext=custom_hover,
                hoverinfo="text",
                sort=False,
            )
        ],
        height=260,
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_shelves_and_recent(
    stats: LibraryStats,
    books: list[Book],
    sessions: list[ReadingSession] | None = None,
) -> None:
    """Shelves badges + recently read list."""
    # Shelves
    if stats.shelf_counts:
        st.markdown('<div class="kn-section-header">Shelves</div>', unsafe_allow_html=True)
        shelf_html = " ".join(
            f'<span class="kn-badge-shelf">{name} ({count})</span>'
            for name, count in stats.shelf_counts
        )
        st.markdown(shelf_html, unsafe_allow_html=True)
        st.markdown("")

    # Build a map of the most recent session end-time per book
    session_dates: dict[str, datetime] = {}
    for s in sessions or []:
        prev = session_dates.get(s.book_id)
        if prev is None or s.end_time > prev:
            session_dates[s.book_id] = s.end_time

    # Determine the best "last activity" date for each book:
    #   1. date_last_read (from Kobo metadata)
    #   2. latest reading session end-time
    #   3. latest annotation created_at / modified_at timestamp
    def _best_date(b: Book) -> datetime | None:
        candidates: list[datetime] = []
        if b.date_last_read:
            candidates.append(b.date_last_read)
        session_dt = session_dates.get(b.id)
        if session_dt:
            candidates.append(session_dt)
        for ann in b.annotations:
            if ann.modified_at:
                candidates.append(ann.modified_at)
            elif ann.created_at:
                candidates.append(ann.created_at)
        return max(candidates) if candidates else None

    # Recently read
    st.markdown('<div class="kn-section-header">Recently Read</div>', unsafe_allow_html=True)
    book_dates = [(b, _best_date(b)) for b in books]
    recently_read = sorted(
        [(b, d) for b, d in book_dates if d is not None],
        key=lambda pair: pair[1],  # type: ignore[arg-type]
        reverse=True,
    )[:6]

    if recently_read:
        items_html = ""
        for b, d in recently_read:
            assert d is not None
            date_str = d.strftime("%b %d, %Y")
            items_html += (
                f'<div class="kn-list-item">'
                f'<div style="font-weight:500;">{b.title}</div>'
                f'<span class="kn-list-value">{date_str}</span>'
                f'</div>'
            )
        st.markdown(items_html, unsafe_allow_html=True)
    else:
        st.caption("No reading dates available.")


def _format_reading_time(seconds: int) -> str:
    """Format seconds into a human-readable reading time."""
    if seconds <= 0:
        return "0m"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.0f}m"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}h"
    days = hours / 24
    return f"{days:.1f}d"


def _render_reading_time_chart(stats: LibraryStats) -> None:
    """Horizontal bar chart: reading time per book (top 8)."""
    st.markdown(
        '<div class="kn-section-header">Time Spent Reading</div>',
        unsafe_allow_html=True,
    )

    top = [(t, s) for t, s in stats.books_by_reading_time[:8] if s > 0]
    if not top:
        st.caption("No reading time data available.")
        return

    titles = [t[:30] + "..." if len(t) > 30 else t for t, _ in top]
    hours = [s / 3600 for _, s in top]

    titles.reverse()
    hours.reverse()

    fig = figure(
        data=[
            go.Bar(
                x=hours,
                y=titles,
                orientation="h",
                marker=dict(
                    color=hours,
                    colorscale=GREEN_GRADIENT,
                    line=dict(width=0),
                    cornerradius=4,
                ),
                hovertemplate="%{y}<br>%{x:.1f} hours<extra></extra>",
            )
        ],
        height=260,
        xaxis=styled_axis(title="Hours"),
        yaxis=styled_axis(show_grid=False),
        margin=dict(l=0, r=10, t=10, b=30),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_vocabulary(
    word_lookups: list[WordLookup], books: list[Book]
) -> None:
    """Show vocabulary / dictionary lookups."""
    st.markdown(
        '<div class="kn-section-header">Vocabulary Lookups</div>',
        unsafe_allow_html=True,
    )

    if not word_lookups:
        st.caption("No dictionary lookups recorded.")
        return

    # Group by book
    book_word_counts: Counter[str] = Counter()
    for wl in word_lookups:
        title = wl.book_title or wl.book_id[:20]
        book_word_counts[title] += 1

    items_html = ""
    for i, (title, count) in enumerate(book_word_counts.most_common(6), 1):
        short_title = title[:35] + "..." if len(title) > 35 else title
        items_html += (
            f'<div class="kn-list-item">'
            f'<div><span class="kn-list-rank">{i}</span>{short_title}</div>'
            f'<span class="kn-list-value">{count} word{"s" if count != 1 else ""}</span>'
            f'</div>'
        )

    st.markdown(items_html, unsafe_allow_html=True)

    # Show recent words
    recent = sorted(
        [w for w in word_lookups if w.looked_up_at],
        key=lambda w: w.looked_up_at or datetime.min,
        reverse=True,
    )[:8]
    if recent:
        word_tags = " ".join(
            f'<span class="kn-badge-shelf">{w.word}</span>' for w in recent
        )
        st.markdown(
            f'<div style="margin-top:0.5rem; font-size:0.75rem; color:#64748b;">Recent:</div>'
            f'{word_tags}',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Kindle-specific helpers
# ---------------------------------------------------------------------------

def _kindle_date_range(books: list[Book]) -> str:
    """Return a compact date range string from annotation timestamps."""
    dates = [
        a.created_at
        for b in books for a in b.annotations
        if a.created_at
    ]
    if not dates:
        return "—"
    mn, mx = min(dates), max(dates)
    if mn.date() == mx.date():
        return mn.strftime("%b %d")
    if mn.year == mx.year and mn.month == mx.month:
        return f"{mn.strftime('%b %d')}–{mx.strftime('%d')}"
    if mn.year == mx.year:
        return f"{mn.strftime('%b')}–{mx.strftime('%b')}"
    return f"{mn.strftime('%b %y')}–{mx.strftime('%b %y')}"


def _render_annotation_density(books: list[Book]) -> None:
    """Stacked horizontal bar: highlights & notes per book."""
    st.markdown(
        '<div class="kn-section-header">Highlights & Notes by Book</div>',
        unsafe_allow_html=True,
    )

    book_data = []
    for b in books:
        hl = sum(1 for a in b.annotations if a.kind == "highlight")
        nt = sum(1 for a in b.annotations if a.kind == "note")
        if hl + nt > 0:
            book_data.append((b.title, hl, nt))

    if not book_data:
        st.caption("No annotations to chart.")
        return

    book_data.sort(key=lambda x: x[1] + x[2], reverse=True)
    top = book_data[:10]
    top.reverse()  # Plotly draws bottom-up

    titles = [t[:30] + "…" if len(t) > 30 else t for t, _, _ in top]
    hls = [h for _, h, _ in top]
    nts = [n for _, _, n in top]

    totals = [h + n for h, n in zip(hls, nts)]

    fig = figure(
        data=[
            go.Bar(
                x=hls,
                y=titles,
                orientation="h",
                name="Highlights",
                marker=dict(color=GREEN, cornerradius=4, line=dict(width=0)),
                hovertemplate="%{y}<br>%{x} highlights<extra></extra>",
                text=[""] * len(hls),
                textposition="none",
            ),
            go.Bar(
                x=nts,
                y=titles,
                orientation="h",
                name="Notes",
                marker=dict(color=PURPLE, cornerradius=4, line=dict(width=0)),
                hovertemplate="%{y}<br>%{x} notes<extra></extra>",
                text=totals,
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ),
        ],
        height=max(260, len(top) * 34),
        xaxis=styled_axis(show_grid=True),
        yaxis=styled_axis(show_grid=False, automargin=True),
        margin=dict(l=10, r=40, t=10, b=40),
        barmode="stack",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.12,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#94a3b8"),
        ),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_highlight_note_ratio(books: list[Book]) -> None:
    """Area chart: weekly annotation pace over time."""
    st.markdown(
        '<div class="kn-section-header">Annotation Pace</div>',
        unsafe_allow_html=True,
    )
    st.caption("Weekly annotations — highlights vs notes")

    # Collect all annotations with dates
    hl_dates: list[datetime] = []
    nt_dates: list[datetime] = []
    for b in books:
        for a in b.annotations:
            if a.created_at:
                if a.kind == "highlight":
                    hl_dates.append(a.created_at)
                elif a.kind == "note":
                    nt_dates.append(a.created_at)

    if not hl_dates and not nt_dates:
        st.caption("No annotations recorded.")
        return

    all_dates = hl_dates + nt_dates
    mn = min(all_dates)
    mx = max(all_dates)

    # Build weekly buckets
    from datetime import date

    start = mn.date() - timedelta(days=mn.weekday())  # Monday
    end = mx.date()
    weeks: list[date] = []
    current = start
    while current <= end:
        weeks.append(current)
        current += timedelta(days=7)
    if not weeks:
        st.caption("Not enough data to chart.")
        return

    hl_counts = [0] * len(weeks)
    nt_counts = [0] * len(weeks)
    for d in hl_dates:
        idx = (d.date() - start).days // 7
        if 0 <= idx < len(weeks):
            hl_counts[idx] += 1
    for d in nt_dates:
        idx = (d.date() - start).days // 7
        if 0 <= idx < len(weeks):
            nt_counts[idx] += 1

    week_labels = [w.strftime("%b %d") for w in weeks]

    fig = figure(
        data=[
            go.Scatter(
                x=week_labels,
                y=hl_counts,
                mode="lines",
                name="Highlights",
                fill="tozeroy",
                line=dict(color=GREEN, width=2),
                fillcolor="rgba(74, 222, 128, 0.25)",
                hovertemplate="Week of %{x}<br>%{y} highlights<extra></extra>",
            ),
            go.Scatter(
                x=week_labels,
                y=nt_counts,
                mode="lines",
                name="Notes",
                fill="tozeroy",
                line=dict(color=PURPLE, width=2),
                fillcolor="rgba(192, 132, 252, 0.25)",
                hovertemplate="Week of %{x}<br>%{y} notes<extra></extra>",
            ),
        ],
        height=280,
        xaxis=styled_axis(show_grid=False, tickangle=-45),
        yaxis=styled_axis(title="Count", show_grid=True),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.35,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#94a3b8"),
        ),
        margin=dict(l=40, r=10, t=10, b=70),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_kindle_page_coverage(books: list[Book]) -> None:
    """Horizontal bar showing note-to-highlight ratio per book — which books sparked the most original thought."""
    st.markdown(
        '<div class="kn-section-header">Engagement Ratio</div>',
        unsafe_allow_html=True,
    )
    st.caption("Notes as % of total annotations — higher = more active thinking")

    book_data: list[tuple[str, int, int, float]] = []  # (title, notes, total, ratio)
    for b in books:
        hl = sum(1 for a in b.annotations if a.kind == "highlight")
        nt = sum(1 for a in b.annotations if a.kind == "note")
        total = hl + nt
        if total >= 3:  # Need enough annotations to be meaningful
            book_data.append((b.title, nt, total, nt / total * 100))

    if not book_data:
        st.caption("Not enough annotation data.")
        return

    book_data.sort(key=lambda x: x[3], reverse=True)
    top = book_data[:10]
    top.reverse()

    titles = [t[:30] + "…" if len(t) > 30 else t for t, _, _, _ in top]
    ratios = [round(r, 1) for _, _, _, r in top]
    hover = [
        f"{t}<br>{nt} notes / {tot} annotations ({r:.1f}%)"
        for t, nt, tot, r in top
    ]

    fig = figure(
        data=[
            go.Bar(
                x=ratios,
                y=titles,
                orientation="h",
                marker=dict(
                    color=ratios,
                    colorscale=[[0, BLUE], [0.5, PURPLE], [1, ROSE]],
                    cornerradius=4,
                    line=dict(width=0),
                ),
                hovertext=hover,
                hoverinfo="text",
                text=[f"{r}%" for r in ratios],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            )
        ],
        height=max(260, len(top) * 34),
        xaxis=styled_axis(title="Note %", show_grid=True, range=[0, max(ratios) * 1.2 if ratios else 100]),
        yaxis=styled_axis(show_grid=False, automargin=True),
        margin=dict(l=10, r=50, t=10, b=40),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)
