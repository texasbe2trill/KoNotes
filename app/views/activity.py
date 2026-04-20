"""Activity view -- reading sessions, progress tracking, annotation patterns."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

from app.charts import (
    AMBER,
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
from models.activity import ProgressSnapshot, ReadingSession
from models.book import Book
from services.streaks import compute_streaks
from services.stats import compute_stats


def render_activity(
    books: list[Book],
    sessions: list[ReadingSession],
    snapshots: list[ProgressSnapshot],
    data_source: str = "kobo",
) -> None:
    stats = compute_stats(books)
    is_kindle = data_source == "kindle"

    st.markdown("## Activity")

    has_data = bool(sessions) or bool(snapshots) or bool(stats.reading_activity_by_day)
    if not has_data:
        st.info(
            "No reading activity data available. "
            "Upload a Kobo SQLite database or Kindle My Clippings.txt to see activity."
        )
        return

    active_days = len(stats.reading_activity_by_day)
    total_annotations = stats.total_annotations

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Books Read", stats.total_books)
    if is_kindle:
        c2.metric("Highlights", stats.total_highlights)
    else:
        c2.metric("Reading Time", _format_duration_sec(stats.total_reading_time_sec))
    c3.metric("Annotations", f"{total_annotations:,}")
    c4.metric("Active Days", active_days)

    _render_streaks(books, sessions)

    _render_activity_insight(books, stats, active_days, is_kindle=is_kindle)

    st.markdown("")

    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        _render_annotation_calendar(stats)

    with col_right:
        _render_day_of_week_pattern(stats)

    col_left2, col_right2 = st.columns(2, gap="large")

    with col_left2:
        if is_kindle:
            _render_annotations_by_book(books)
        else:
            _render_reading_time_by_book(books)

    with col_right2:
        _render_time_of_day(books)

    if sessions:
        _render_sessions_timeline(sessions, books)
    elif is_kindle:
        _render_kindle_annotation_timeline(books)

    if snapshots:
        _render_progress_curves(snapshots, books, sessions)
    elif is_kindle:
        _render_kindle_location_scatter(books)

    _community = "Kindle & Kobo" if is_kindle else "Kobo"
    st.markdown(
        f'<div class="kn-footer">Made with love for the {_community} community.</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════


def _format_duration_sec(seconds: int) -> str:
    """Format seconds into a human-readable duration string."""
    if not seconds or seconds <= 0:
        return "0m"
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    if hours <= 0:
        return f"{mins}m"
    if hours < 24:
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    days = hours // 24
    remaining_h = hours % 24
    return f"{days}d {remaining_h}h" if remaining_h else f"{days}d"


def _truncate(text: str, max_len: int = 30) -> str:
    return text[:max_len - 3] + "..." if len(text) > max_len else text


def _render_activity_insight(
    books: list[Book],
    stats,
    active_days: int,
    is_kindle: bool = False,
) -> None:
    parts: list[str] = []

    # Reading pace (Kobo only — Kindle has no time_spent_reading)
    if not is_kindle:
        books_with_time = [b for b in books if b.time_spent_reading and b.time_spent_reading > 0]
        if books_with_time:
            total_sec = sum(b.time_spent_reading or 0 for b in books_with_time)
            avg_per_book_min = (total_sec / len(books_with_time)) / 60
            parts.append(
                f"Average reading time per book: <strong>{avg_per_book_min:.0f} minutes</strong>."
            )

    # Kindle: average annotations per book
    if is_kindle and books:
        total_ann = sum(len(b.annotations) for b in books)
        avg_ann = total_ann / len(books)
        parts.append(
            f"Average annotations per book: <strong>{avg_ann:.1f}</strong>."
        )

    if active_days > 1 and stats.reading_activity_by_day:
        dates = sorted(stats.reading_activity_by_day, key=lambda x: x[0])
        first = datetime.strptime(dates[0][0], "%Y-%m-%d")
        last = datetime.strptime(dates[-1][0], "%Y-%m-%d")
        span_days = max((last - first).days, 1)
        if span_days > 0:
            pct = (active_days / span_days) * 100
            parts.append(
                f"You annotated on <strong>{pct:.0f}%</strong> of days "
                f"across a <strong>{span_days}-day</strong> window."
            )

    # Busiest day
    if stats.reading_activity_by_day:
        busiest = max(stats.reading_activity_by_day, key=lambda x: x[1])
        dt = datetime.strptime(busiest[0], "%Y-%m-%d")
        parts.append(
            f"Most active day: <strong>{dt.strftime('%b %d, %Y')}</strong> "
            f"with {busiest[1]} annotations."
        )

    if parts:
        st.markdown(
            '<div class="kn-insight">'
            '<span class="kn-insight-label">Insight</span> '
            + " ".join(parts)
            + "</div>",
            unsafe_allow_html=True,
        )


def _render_streaks(
    books: list[Book],
    sessions: list[ReadingSession],
) -> None:
    """Display reading streak metrics."""
    streaks = compute_streaks(books, sessions)

    if streaks.active_days < 2:
        return

    st.markdown("")
    s1, s2, s3, s4 = st.columns(4)

    streak_icon = "🔥" if streaks.current_streak >= 3 else "📅"
    s1.metric(f"{streak_icon} Current Streak", f"{streaks.current_streak} day{'s' if streaks.current_streak != 1 else ''}")
    s2.metric("🏆 Longest Streak", f"{streaks.longest_streak} day{'s' if streaks.longest_streak != 1 else ''}")
    s3.metric("📆 This Week", f"{streaks.this_week_days} day{'s' if streaks.this_week_days != 1 else ''}")
    s4.metric("📊 Weekly Consistency", f"{streaks.weekly_consistency:.0f}%")

    # Reading goal tracker (session-scoped)
    _render_goals(streaks)


def _render_goals(streaks) -> None:
    """Render a collapsible reading goal tracker."""
    with st.expander("Reading Goals", expanded=False):
        if "reading_goal_days" not in st.session_state:
            st.session_state["reading_goal_days"] = 5

        goal = st.slider(
            "Weekly reading goal (days per week)",
            min_value=1,
            max_value=7,
            value=st.session_state["reading_goal_days"],
            key="goal_slider",
        )
        st.session_state["reading_goal_days"] = goal

        progress = min(streaks.this_week_days / goal, 1.0)
        pct = int(progress * 100)
        bar_color = "#10b981" if progress >= 1.0 else "#3b82f6"
        status = "Goal reached! 🎉" if progress >= 1.0 else f"{streaks.this_week_days}/{goal} days this week"

        st.markdown(
            f'<div style="margin:0.5rem 0;">'
            f'<div style="font-size:0.85rem; color:#94a3b8; margin-bottom:4px;">{status}</div>'
            f'<div style="background:#1e293b; border-radius:6px; height:8px; overflow:hidden;">'
            f'<div style="background:{bar_color}; width:{pct}%; height:100%; '
            f'border-radius:6px; transition:width 0.3s;"></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        if streaks.most_active_day:
            st.caption(f"You read most often on **{streaks.most_active_day}s** ({streaks.most_active_day_count} days).")


def _render_annotation_calendar(stats) -> None:
    """Bar chart of annotation frequency over time."""
    st.markdown(
        '<div class="kn-section-header">Annotation Timeline</div>',
        unsafe_allow_html=True,
    )

    if not stats.reading_activity_by_day or len(stats.reading_activity_by_day) < 2:
        st.caption("Not enough data for timeline.")
        return

    day_data = {d: c for d, c in stats.reading_activity_by_day}
    dates_sorted = sorted(day_data.keys())
    first = datetime.strptime(dates_sorted[0], "%Y-%m-%d")
    last = datetime.strptime(dates_sorted[-1], "%Y-%m-%d")

    # Fill in zero days
    all_dates: list[str] = []
    all_counts: list[int] = []
    current = first
    while current <= last:
        ds = current.strftime("%Y-%m-%d")
        all_dates.append(ds)
        all_counts.append(day_data.get(ds, 0))
        current += timedelta(days=1)

    # Weekly aggregation if span > 90 days
    if len(all_dates) > 90:
        weekly: dict[str, int] = defaultdict(int)
        for ds, c in zip(all_dates, all_counts):
            dt = datetime.strptime(ds, "%Y-%m-%d")
            wk = (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
            weekly[wk] += c
        sorted_weeks = sorted(weekly.keys())
        x_vals = [datetime.strptime(w, "%Y-%m-%d").strftime("%b %d") for w in sorted_weeks]
        y_vals = [weekly[w] for w in sorted_weeks]
        hover_tmpl = "%{x}<br>%{y} annotations (week)<extra></extra>"
        label = "Weekly"
    else:
        x_vals = [datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d in all_dates]
        y_vals = all_counts
        hover_tmpl = "%{x}<br>%{y} annotations<extra></extra>"
        label = "Daily"

    fig = figure(
        data=[
            go.Bar(
                x=x_vals,
                y=y_vals,
                marker=dict(
                    color=BLUE,
                    opacity=0.85,
                    line=dict(width=0),
                    cornerradius=2,
                ),
                hovertemplate=hover_tmpl,
                name=label,
            )
        ],
        height=260,
        xaxis=styled_axis(
            show_grid=False,
            tickangle=-45,
            nticks=min(len(x_vals), 15),
        ),
        yaxis=styled_axis(title="Annotations", dtick=max(1, max(y_vals) // 5) if y_vals else 1),
        margin=dict(l=40, r=10, t=10, b=60),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_day_of_week_pattern(stats) -> None:
    """Bar chart: which days of the week you annotate most."""
    st.markdown(
        '<div class="kn-section-header">Day of Week</div>',
        unsafe_allow_html=True,
    )

    if not stats.reading_activity_by_day:
        st.caption("No annotation data.")
        return

    dow_counter: Counter[str] = Counter()
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for day_str, count in stats.reading_activity_by_day:
        dt = datetime.strptime(day_str, "%Y-%m-%d")
        dow_counter[day_names[dt.weekday()]] += count

    values = [dow_counter.get(d, 0) for d in day_names]
    max_val = max(values) if values else 1
    colors = [BLUE if v == max_val else "rgba(59,130,246,0.4)" for v in values]

    fig = figure(
        data=[
            go.Bar(
                x=day_names,
                y=values,
                marker=dict(color=colors, cornerradius=4, line=dict(width=0)),
                hovertemplate="%{x}: %{y} annotations<extra></extra>",
                text=values,
                textposition="outside",
                textfont=dict(size=11, color="#94a3b8"),
            )
        ],
        height=260,
        xaxis=styled_axis(show_grid=False),
        yaxis=styled_axis(title="Annotations", showticklabels=False, show_grid=False),
        margin=dict(l=10, r=10, t=20, b=30),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_reading_time_by_book(books: list[Book]) -> None:
    """Horizontal bar chart of total reading time per book."""
    st.markdown(
        '<div class="kn-section-header">Reading Time by Book</div>',
        unsafe_allow_html=True,
    )

    timed = [(b.title, b.time_spent_reading) for b in books
             if b.time_spent_reading and b.time_spent_reading > 0]
    if not timed:
        st.caption("No reading time data available.")
        return

    timed.sort(key=lambda x: x[1], reverse=True)
    top = timed[:10]
    top.reverse()  # Plotly draws bottom-up

    titles = [_truncate(t, 35) for t, _ in top]
    seconds = [s for _, s in top]
    hours = [s / 3600 for s in seconds]
    hover = [
        f"{t}<br>{_format_duration_sec(s)}"
        for t, s in zip([t for t, _ in top], seconds)
    ]

    fig = figure(
        data=[
            go.Bar(
                x=hours,
                y=titles,
                orientation="h",
                marker=dict(color=GREEN, cornerradius=4, line=dict(width=0)),
                hovertext=hover,
                hoverinfo="text",
                text=[_format_duration_sec(s) for s in seconds],
                textposition="outside",
                textfont=dict(size=11, color="#94a3b8"),
            )
        ],
        height=max(220, len(top) * 32),
        xaxis=styled_axis(title="Hours", show_grid=True),
        yaxis=styled_axis(show_grid=False, automargin=True),
        margin=dict(l=10, r=60, t=10, b=40),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_annotations_by_book(books: list[Book]) -> None:
    """Stacked horizontal bar: highlights & notes per book (Kindle alternative)."""
    st.markdown(
        '<div class="kn-section-header">Annotations by Book</div>',
        unsafe_allow_html=True,
    )

    book_data = []
    for b in books:
        hl = sum(1 for a in b.annotations if a.kind == "highlight")
        nt = sum(1 for a in b.annotations if a.kind == "note")
        if hl + nt > 0:
            book_data.append((b.title, hl, nt))

    if not book_data:
        st.caption("No annotation data available.")
        return

    book_data.sort(key=lambda x: x[1] + x[2], reverse=True)
    top = book_data[:8]
    top.reverse()

    titles = [_truncate(t, 28) for t, _, _ in top]
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
        height=max(240, len(top) * 32),
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


def _render_time_of_day(books: list[Book]) -> None:
    """Bar chart showing annotation distribution by hour of day."""
    st.markdown(
        '<div class="kn-section-header">Time of Day</div>',
        unsafe_allow_html=True,
    )

    hour_counter: Counter[int] = Counter()
    for book in books:
        for ann in book.annotations:
            if ann.created_at:
                hour_counter[ann.created_at.hour] += 1

    if not hour_counter:
        st.caption("No timestamp data available.")
        return

    hours_24 = list(range(24))
    counts = [hour_counter.get(h, 0) for h in hours_24]
    labels = [f"{h:02d}:00" for h in hours_24]
    max_count = max(counts) if counts else 1
    colors = [PURPLE if c == max_count else "rgba(168,85,247,0.4)" for c in counts]

    # Find the peak reading period
    peak_hour = max(hour_counter, key=lambda h: hour_counter[h])
    period = "morning" if 5 <= peak_hour < 12 else (
        "afternoon" if 12 <= peak_hour < 17 else (
            "evening" if 17 <= peak_hour < 21 else "night"
        )
    )
    st.caption(f"Peak reading: {peak_hour:02d}:00 ({period})")

    fig = figure(
        data=[
            go.Bar(
                x=labels,
                y=counts,
                marker=dict(color=colors, cornerradius=3, line=dict(width=0)),
                hovertemplate="%{x}<br>%{y} annotations<extra></extra>",
            )
        ],
        height=260,
        xaxis=styled_axis(show_grid=False, nticks=12, tickangle=-45),
        yaxis=styled_axis(title="Annotations", show_grid=True),
        margin=dict(l=40, r=10, t=10, b=60),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_sessions_timeline(
    sessions: list[ReadingSession], books: list[Book]
) -> None:
    """Scatter plot of reading sessions: x=date, y=duration, colored by book."""
    st.markdown(
        '<div class="kn-section-header">Reading Sessions</div>',
        unsafe_allow_html=True,
    )
    st.caption("Inferred from annotation timestamp clustering")

    session_sorted = sorted(sessions, key=lambda s: s.start_time)

    # Group by book for color-coded traces
    book_sessions: dict[str, list[ReadingSession]] = defaultdict(list)
    for s in session_sorted:
        book_sessions[s.book_id].append(s)

    # Sort books by total sessions (most active first)
    sorted_books = sorted(book_sessions.keys(), key=lambda b: len(book_sessions[b]), reverse=True)

    traces = []
    for i, bid in enumerate(sorted_books[:10]):
        sess_list = book_sessions[bid]
        title = _truncate(sess_list[0].book_title, 25)
        color = PALETTE[i % len(PALETTE)]

        dates = [s.start_time for s in sess_list]
        durations = [s.duration_minutes for s in sess_list]
        hover = [
            f"{s.book_title}<br>"
            f"{s.start_time.strftime('%b %d, %Y %H:%M')}<br>"
            f"Duration: {s.duration_minutes:.0f} min"
            + (f"<br>Progress: {s.start_percent * 100:.0f}% → {s.end_percent * 100:.0f}%"
               if s.start_percent is not None and s.end_percent is not None else "")
            for s in sess_list
        ]

        traces.append(
            go.Scatter(
                x=dates,
                y=durations,
                mode="markers",
                name=title,
                marker=dict(
                    color=color,
                    size=[max(6, min(20, d / 3)) for d in durations],
                    opacity=0.8,
                    line=dict(width=1, color="rgba(0,0,0,0.2)"),
                ),
                hovertext=hover,
                hoverinfo="text",
            )
        )

    fig = figure(
        data=traces,
        height=320,
        xaxis=styled_axis(show_grid=False, title="Date"),
        yaxis=styled_axis(title="Duration (min)"),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#94a3b8"),
        ),
        margin=dict(l=50, r=10, t=10, b=80),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_progress_curves(
    snapshots: list[ProgressSnapshot],
    books: list[Book],
    sessions: list[ReadingSession] | None = None,
) -> None:
    """Line chart showing reading progress over time per book."""
    st.markdown(
        '<div class="kn-section-header">Reading Progress</div>',
        unsafe_allow_html=True,
    )
    st.caption("Extracted from reading progress at annotation time")

    # Group by book
    book_snaps: dict[str, list[ProgressSnapshot]] = defaultdict(list)
    for snap in snapshots:
        book_snaps[snap.book_id].append(snap)

    # Build title map: Book.id (SHA1) + VolumeID (from snapshots/sessions) -> title
    title_map = {b.id: b.title for b in books}
    for snap in snapshots:
        if snap.book_id not in title_map and snap.book_title:
            title_map[snap.book_id] = snap.book_title
    for s in sessions or []:
        if s.book_id not in title_map:
            title_map[s.book_id] = s.book_title

    # Filter to books with at least 2 snapshots
    valid = {
        bid: sorted(snaps, key=lambda s: s.recorded_at or datetime.min)
        for bid, snaps in book_snaps.items()
        if len(snaps) >= 2
    }

    if not valid:
        st.caption("Not enough progress snapshots to chart.")
        return

    # Limit to top 8 books by number of snapshots
    top_books = sorted(valid.keys(), key=lambda b: len(valid[b]), reverse=True)[:8]

    traces = []
    for i, bid in enumerate(top_books):
        snaps = valid[bid]
        title = _truncate(title_map.get(bid, bid[:20]), 25)

        x_dates = [s.recorded_at for s in snaps if s.recorded_at]
        y_pcts = [s.percent for s in snaps if s.recorded_at]

        traces.append(
            go.Scatter(
                x=x_dates,
                y=y_pcts,
                mode="lines+markers",
                name=title,
                line=dict(color=PALETTE[i % len(PALETTE)], width=2),
                marker=dict(size=5),
                hovertemplate=f"{title}<br>%{{x|%b %d, %Y}}<br>%{{y:.0f}}%<extra></extra>",
            )
        )

    fig = figure(
        data=traces,
        height=340,
        xaxis=styled_axis(show_grid=False),
        yaxis=styled_axis(title="Progress (%)", range=[0, 105]),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#94a3b8"),
        ),
        margin=dict(l=50, r=10, t=10, b=80),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


# ---------------------------------------------------------------------------
# Kindle-specific plots
# ---------------------------------------------------------------------------


def _render_kindle_annotation_timeline(books: list[Book]) -> None:
    """Cumulative annotation chart for top books + weekly summary bar."""
    st.markdown(
        '<div class="kn-section-header">Annotation Timeline</div>',
        unsafe_allow_html=True,
    )

    # Gather annotations with timestamps, grouped by book
    book_anns: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for b in books:
        for a in b.annotations:
            if a.created_at:
                book_anns[b.title].append((a.created_at, a.kind))

    if not book_anns:
        st.caption("No timestamp data available.")
        return

    sorted_titles = sorted(book_anns.keys(), key=lambda t: len(book_anns[t]), reverse=True)

    show_all = st.toggle("Show all books", value=False, key="kindle_timeline_all")

    if show_all:
        display_titles = sorted_titles
        st.caption(f"All {len(sorted_titles)} books")
    else:
        display_titles = sorted_titles[:10]
        remaining = len(sorted_titles) - 10
        st.caption(
            f"Top 10 of {len(sorted_titles)} books"
            if remaining > 0
            else f"All {len(sorted_titles)} books"
        )

    traces = []
    for i, title in enumerate(display_titles):
        anns = sorted(book_anns[title], key=lambda x: x[0])
        color = PALETTE[i % len(PALETTE)]
        short = _truncate(title, 22)

        dates = [a[0] for a in anns]
        cumulative = list(range(1, len(anns) + 1))
        hover = [
            f"{title}<br>"
            f"{a[0].strftime('%b %d, %Y %H:%M')}<br>"
            f"{a[1].capitalize()} #{c}"
            for a, c in zip(anns, cumulative)
        ]

        traces.append(
            go.Scatter(
                x=dates,
                y=cumulative,
                mode="lines+markers",
                name=short,
                line=dict(color=color, width=2.5 if not show_all else 1.5),
                marker=dict(size=4 if not show_all else 3, opacity=0.7),
                hovertext=hover,
                hoverinfo="text",
            )
        )

    chart_height = 320 if not show_all else max(380, len(display_titles) * 6)

    fig = figure(
        data=traces,
        height=chart_height,
        xaxis=styled_axis(show_grid=False, title="Date"),
        yaxis=styled_axis(title="Cumulative Annotations"),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25 if not show_all else -0.15,
            xanchor="center",
            x=0.5,
            font=dict(size=11 if not show_all else 10, color="#94a3b8"),
        ),
        margin=dict(l=50, r=10, t=10, b=80),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)


def _render_kindle_location_scatter(books: list[Book]) -> None:
    """Heatmap: annotation activity per book over time (weekly buckets)."""
    import re

    st.markdown(
        '<div class="kn-section-header">Reading Activity by Book</div>',
        unsafe_allow_html=True,
    )
    st.caption("Weekly annotation intensity across your library")

    # Gather annotations with timestamps, grouped by book
    book_weeks: dict[str, Counter] = defaultdict(Counter)
    all_dates: list[datetime] = []
    for b in books:
        for a in b.annotations:
            if a.created_at:
                all_dates.append(a.created_at)
                week_start = a.created_at.date() - timedelta(days=a.created_at.weekday())
                book_weeks[b.title][week_start] += 1

    if not book_weeks or not all_dates:
        st.caption("No timestamp data available.")
        return

    # Build week list
    from datetime import date

    mn = min(all_dates).date()
    mx = max(all_dates).date()
    start = mn - timedelta(days=mn.weekday())
    weeks: list[date] = []
    current = start
    while current <= mx:
        weeks.append(current)
        current += timedelta(days=7)

    if not weeks:
        st.caption("Not enough data to chart.")
        return

    # Top 12 books by total annotations
    sorted_books = sorted(book_weeks.keys(), key=lambda t: sum(book_weeks[t].values()), reverse=True)
    top_books = sorted_books[:12]
    top_books.reverse()  # Plotly heatmap: bottom = first

    week_labels = [w.strftime("%b %d") for w in weeks]
    book_labels = [_truncate(t, 25) for t in top_books]

    # Build z-matrix
    z = []
    hover_text = []
    for title in top_books:
        row = []
        h_row = []
        for w in weeks:
            count = book_weeks[title].get(w, 0)
            row.append(count)
            h_row.append(
                f"{title}<br>Week of {w.strftime('%b %d')}<br>{count} annotations"
                if count > 0
                else f"{title}<br>Week of {w.strftime('%b %d')}<br>—"
            )
        z.append(row)
        hover_text.append(h_row)

    fig = figure(
        data=[
            go.Heatmap(
                z=z,
                x=week_labels,
                y=book_labels,
                colorscale=[
                    [0, "#1e293b"],
                    [0.01, "#1e3a5f"],
                    [0.25, "#2563eb"],
                    [0.5, "#38bdf8"],
                    [1, "#4ade80"],
                ],
                hovertext=hover_text,
                hoverinfo="text",
                showscale=False,
                xgap=2,
                ygap=2,
            )
        ],
        height=max(280, len(top_books) * 28),
        xaxis=styled_axis(show_grid=False, tickangle=-45),
        yaxis=styled_axis(show_grid=False, automargin=True),
        margin=dict(l=10, r=10, t=10, b=60),
    )
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None)
