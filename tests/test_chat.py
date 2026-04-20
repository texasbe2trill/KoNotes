"""Tests for the chat context builder."""
from __future__ import annotations

from datetime import datetime

import pytest

from models.annotation import Annotation
from models.activity import ReadingSession
from models.book import Book
from services.hero_insight_engine import generate_hero_insight
from services.chat import build_context, build_system_prompt
from services.stats import compute_stats
from services.streaks import ReadingStreaks, compute_streaks


def _make_books() -> list[Book]:
    return [
        Book(
            id="b1",
            title="Deep Work",
            author="Cal Newport",
            source="test",
            read_percent=100.0,
            rating=5,
            time_spent_reading=7200,
            shelves=["productivity"],
            annotations=[
                Annotation(
                    id="a1",
                    book_id="b1",
                    kind="highlight",
                    text="Professional activities performed in a state of distraction-free concentration.",
                    chapter="Chapter 1",
                    created_at=datetime(2025, 3, 10),
                    source="test",
                ),
                Annotation(
                    id="a2",
                    book_id="b1",
                    kind="note",
                    text="Key definition of deep work.",
                    created_at=datetime(2025, 3, 10),
                    source="test",
                ),
            ],
        ),
        Book(
            id="b2",
            title="Atomic Habits",
            author="James Clear",
            source="test",
            read_percent=65.0,
            annotations=[
                Annotation(
                    id="a3",
                    book_id="b2",
                    kind="highlight",
                    text="Every action you take is a vote for the person you wish to become.",
                    chapter="Identity",
                    created_at=datetime(2025, 3, 12),
                    source="test",
                ),
            ],
        ),
    ]


class TestBuildSystemPrompt:
    def test_includes_library_overview(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks()
        prompt = build_system_prompt(books, stats, streaks)
        assert "Total books: 2" in prompt
        assert "Highlights: 2" in prompt
        assert "Notes: 1" in prompt

    def test_includes_book_titles(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks()
        prompt = build_system_prompt(books, stats, streaks)
        assert "Deep Work" in prompt
        assert "Atomic Habits" in prompt

    def test_includes_authors(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks()
        prompt = build_system_prompt(books, stats, streaks)
        assert "Cal Newport" in prompt
        assert "James Clear" in prompt

    def test_includes_sample_highlights(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks()
        prompt = build_system_prompt(books, stats, streaks)
        assert "distraction-free concentration" in prompt
        assert "vote for the person" in prompt

    def test_includes_reading_time(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks()
        prompt = build_system_prompt(books, stats, streaks)
        assert "reading time" in prompt.lower()

    def test_includes_rating(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks()
        prompt = build_system_prompt(books, stats, streaks)
        assert "rated 5/5" in prompt

    def test_includes_shelves(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks()
        prompt = build_system_prompt(books, stats, streaks)
        assert "productivity" in prompt

    def test_includes_streaks_when_present(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks(
            current_streak=5,
            longest_streak=10,
            active_days=30,
            weekly_consistency=80.0,
            most_active_day="Monday",
        )
        prompt = build_system_prompt(books, stats, streaks)
        assert "Current streak: 5" in prompt
        assert "Longest streak: 10" in prompt
        assert "Monday" in prompt

    def test_skips_streaks_when_few_days(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks(active_days=1)
        prompt = build_system_prompt(books, stats, streaks)
        assert "Reading Streaks" not in prompt

    def test_includes_notes(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks()
        prompt = build_system_prompt(books, stats, streaks)
        assert "Key definition of deep work" in prompt

    def test_includes_progress(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks()
        prompt = build_system_prompt(books, stats, streaks)
        assert "100% read" in prompt
        assert "65% read" in prompt

    def test_includes_hero_reading_pattern_when_provided(self):
        books = _make_books()
        stats = compute_stats(books)
        streaks = ReadingStreaks(longest_streak=4)
        hero = generate_hero_insight(
            stats,
            books,
            longest_streak=streaks.longest_streak,
            total_reading_time_sec=stats.total_reading_time_sec,
        )
        prompt = build_system_prompt(books, stats, streaks, hero_insight=hero)
        assert "Hero Reading Pattern" in prompt
        assert hero.title in prompt
        assert hero.summary in prompt


class TestBuildContext:
    def test_convenience_wrapper(self):
        books = _make_books()
        context = build_context(books)
        assert "Library Overview" in context
        assert "Deep Work" in context

    def test_with_sessions(self):
        books = _make_books()
        session = ReadingSession(
            book_id="b1",
            book_title="Deep Work",
            start_time=datetime(2025, 3, 10, 10, 0),
            end_time=datetime(2025, 3, 10, 11, 0),
            duration_minutes=60.0,
        )
        context = build_context(books, sessions=[session])
        assert "Library Overview" in context

    def test_empty_library(self):
        context = build_context([])
        assert "Total books: 0" in context

    def test_context_includes_hero_reading_pattern(self):
        books = _make_books()
        context = build_context(books)
        assert "Hero Reading Pattern" in context
