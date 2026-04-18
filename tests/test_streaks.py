"""Tests for reading streaks service."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from models.annotation import Annotation
from models.activity import ReadingSession
from models.book import Book
from services.streaks import ReadingStreaks, compute_streaks


def _make_book_with_dates(dates: list[str]) -> Book:
    """Create a book with annotations on the given dates (YYYY-MM-DD)."""
    return Book(
        id="streaks1",
        title="Streak Book",
        source="test",
        annotations=[
            Annotation(
                id=f"a{i}",
                book_id="streaks1",
                kind="highlight",
                text=f"Annotation {i}",
                created_at=datetime.strptime(d, "%Y-%m-%d"),
                source="test",
            )
            for i, d in enumerate(dates)
        ],
    )


class TestStreakComputation:
    def test_no_data(self):
        streaks = compute_streaks([])
        assert streaks.current_streak == 0
        assert streaks.longest_streak == 0
        assert streaks.active_days == 0

    def test_single_day(self):
        book = _make_book_with_dates(["2025-03-15"])
        streaks = compute_streaks([book], today=date(2025, 3, 15))
        assert streaks.current_streak == 1
        assert streaks.longest_streak == 1
        assert streaks.active_days == 1

    def test_consecutive_days(self):
        book = _make_book_with_dates(["2025-03-13", "2025-03-14", "2025-03-15"])
        streaks = compute_streaks([book], today=date(2025, 3, 15))
        assert streaks.current_streak == 3
        assert streaks.longest_streak == 3

    def test_broken_streak(self):
        book = _make_book_with_dates([
            "2025-03-10", "2025-03-11",  # 2-day streak
            "2025-03-14", "2025-03-15",  # 2-day streak (current)
        ])
        streaks = compute_streaks([book], today=date(2025, 3, 15))
        assert streaks.current_streak == 2
        assert streaks.longest_streak == 2

    def test_longest_streak_in_past(self):
        book = _make_book_with_dates([
            "2025-03-01", "2025-03-02", "2025-03-03", "2025-03-04",  # 4-day
            "2025-03-14", "2025-03-15",  # 2-day (current)
        ])
        streaks = compute_streaks([book], today=date(2025, 3, 15))
        assert streaks.current_streak == 2
        assert streaks.longest_streak == 4

    def test_yesterday_grace(self):
        """If today has no activity but yesterday did, streak should still count."""
        book = _make_book_with_dates(["2025-03-14", "2025-03-15"])
        streaks = compute_streaks([book], today=date(2025, 3, 16))
        assert streaks.current_streak == 2

    def test_no_grace_after_two_days(self):
        """If the gap is 2+ days, current streak is 0."""
        book = _make_book_with_dates(["2025-03-13", "2025-03-14"])
        streaks = compute_streaks([book], today=date(2025, 3, 17))
        assert streaks.current_streak == 0

    def test_active_days(self):
        book = _make_book_with_dates([
            "2025-03-10", "2025-03-12", "2025-03-15",
        ])
        streaks = compute_streaks([book], today=date(2025, 3, 15))
        assert streaks.active_days == 3

    def test_sessions_contribute(self):
        book = _make_book_with_dates(["2025-03-14"])
        session = ReadingSession(
            book_id="streaks1",
            book_title="Streak Book",
            start_time=datetime(2025, 3, 15, 10, 0),
            end_time=datetime(2025, 3, 15, 11, 0),
            duration_minutes=60.0,
        )
        streaks = compute_streaks([book], sessions=[session], today=date(2025, 3, 15))
        assert streaks.current_streak == 2
        assert streaks.active_days == 2

    def test_weekly_consistency(self):
        # Activity on 3 different weeks within a 3-week span
        book = _make_book_with_dates([
            "2025-03-03",  # week 1
            "2025-03-10",  # week 2
            "2025-03-17",  # week 3
        ])
        streaks = compute_streaks([book], today=date(2025, 3, 17))
        assert streaks.weekly_consistency > 0
        assert streaks.active_weeks == 3

    def test_most_active_day(self):
        book = _make_book_with_dates([
            "2025-03-10",  # Monday
            "2025-03-17",  # Monday
            "2025-03-18",  # Tuesday
        ])
        streaks = compute_streaks([book], today=date(2025, 3, 18))
        assert streaks.most_active_day == "Monday"
        assert streaks.most_active_day_count == 2

    def test_this_week_days(self):
        # March 17, 2025 is a Monday
        book = _make_book_with_dates([
            "2025-03-05",  # prior week
            "2025-03-17",  # this week Mon
            "2025-03-18",  # this week Tue
        ])
        streaks = compute_streaks([book], today=date(2025, 3, 19))
        assert streaks.this_week_days == 2

    def test_this_month_days(self):
        book = _make_book_with_dates([
            "2025-02-28",  # last month
            "2025-03-01",
            "2025-03-15",
        ])
        streaks = compute_streaks([book], today=date(2025, 3, 15))
        assert streaks.this_month_days == 2

    def test_multiple_books(self):
        book1 = _make_book_with_dates(["2025-03-14"])
        book2 = Book(
            id="b2",
            title="Book 2",
            source="test",
            annotations=[
                Annotation(
                    id="b2a1",
                    book_id="b2",
                    kind="note",
                    text="Note",
                    created_at=datetime(2025, 3, 15),
                    source="test",
                ),
            ],
        )
        streaks = compute_streaks([book1, book2], today=date(2025, 3, 15))
        assert streaks.current_streak == 2
        assert streaks.active_days == 2


class TestReadingStreaksDataclass:
    def test_defaults(self):
        s = ReadingStreaks()
        assert s.current_streak == 0
        assert s.longest_streak == 0
        assert s.weekly_consistency == 0.0
        assert s.most_active_day is None
