"""Reading streaks and goals service.

Computes reading streaks from annotation timestamps and reading sessions.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from models.activity import ReadingSession
from models.book import Book


@dataclass
class ReadingStreaks:
    """Computed streak and consistency data."""

    current_streak: int = 0
    longest_streak: int = 0
    active_days: int = 0
    total_span_days: int = 0
    weekly_consistency: float = 0.0  # % of weeks with >= 1 active day
    active_weeks: int = 0
    total_weeks: int = 0
    most_active_day: str | None = None  # e.g. "Monday"
    most_active_day_count: int = 0
    this_week_days: int = 0
    this_month_days: int = 0


def compute_streaks(
    books: list[Book],
    sessions: list[ReadingSession] | None = None,
    today: date | None = None,
) -> ReadingStreaks:
    """Compute reading streak data from annotation dates and sessions.

    Parameters
    ----------
    books:
        Books with annotations (dates extracted from ``created_at``).
    sessions:
        Optional reading sessions (dates extracted from ``start_time``).
    today:
        Override for "today" (useful for testing).
    """
    if today is None:
        today = date.today()

    # Gather all active dates
    active_dates: set[date] = set()
    for book in books:
        for ann in book.annotations:
            if ann.created_at:
                active_dates.add(ann.created_at.date())

    for session in sessions or []:
        active_dates.add(session.start_time.date())
        active_dates.add(session.end_time.date())

    if not active_dates:
        return ReadingStreaks()

    sorted_dates = sorted(active_dates)
    first_date = sorted_dates[0]
    last_date = sorted_dates[-1]
    total_span = max((last_date - first_date).days, 1)

    # Current streak: consecutive days ending on today or the last active day
    current_streak = 0
    check_date = today
    # Allow a 1-day gap — if today has no activity, start from the last active day
    if check_date not in active_dates and check_date - timedelta(days=1) in active_dates:
        check_date = check_date - timedelta(days=1)
    while check_date in active_dates:
        current_streak += 1
        check_date -= timedelta(days=1)

    # Longest streak
    longest = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    longest_streak = longest if len(sorted_dates) > 0 else 0

    # Weekly consistency
    week_set: set[tuple[int, int]] = set()
    for d in sorted_dates:
        iso = d.isocalendar()
        week_set.add((iso[0], iso[1]))

    first_iso = first_date.isocalendar()
    last_iso = today.isocalendar()
    total_weeks = max(
        ((today - first_date).days // 7) + 1,
        1,
    )
    active_weeks = len(week_set)
    weekly_consistency = (active_weeks / total_weeks) * 100 if total_weeks else 0.0

    # Most active day of week
    dow_counter: Counter[str] = Counter()
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for d in sorted_dates:
        dow_counter[day_names[d.weekday()]] += 1
    most_active_day = None
    most_active_day_count = 0
    if dow_counter:
        most_active_day, most_active_day_count = dow_counter.most_common(1)[0]

    # This week / this month
    week_start = today - timedelta(days=today.weekday())
    this_week = sum(1 for d in sorted_dates if week_start <= d <= today)
    month_start = today.replace(day=1)
    this_month = sum(1 for d in sorted_dates if month_start <= d <= today)

    return ReadingStreaks(
        current_streak=current_streak,
        longest_streak=longest_streak,
        active_days=len(active_dates),
        total_span_days=total_span,
        weekly_consistency=round(weekly_consistency, 1),
        active_weeks=active_weeks,
        total_weeks=total_weeks,
        most_active_day=most_active_day,
        most_active_day_count=most_active_day_count,
        this_week_days=this_week,
        this_month_days=this_month,
    )
