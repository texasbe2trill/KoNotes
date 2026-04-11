"""Tests for the enhanced stats service."""
from __future__ import annotations

from datetime import datetime

import pytest

from models.annotation import Annotation
from models.book import Book
from services.stats import LibraryStats, compute_stats


def _book(
    title: str = "Book",
    author: str | None = "Author",
    highlights: int = 3,
    notes: int = 1,
    read_percent: float | None = None,
    shelves: list[str] | None = None,
    date_last_read: datetime | None = None,
) -> Book:
    anns = []
    for i in range(highlights):
        anns.append(Annotation(
            id=f"h{i}_{title}",
            book_id=title,
            kind="highlight",
            text=f"Highlight {i}",
            source="test",
            created_at=datetime(2026, 1, i + 1) if i < 28 else None,
        ))
    for i in range(notes):
        anns.append(Annotation(
            id=f"n{i}_{title}",
            book_id=title,
            kind="note",
            text=f"Note {i}",
            source="test",
        ))
    return Book(
        id=title,
        title=title,
        author=author,
        source="test",
        annotations=anns,
        read_percent=read_percent,
        shelves=shelves or [],
        date_last_read=date_last_read,
    )


class TestComputeStats:
    def test_empty(self):
        stats = compute_stats([])
        assert stats.total_books == 0
        assert stats.total_annotations == 0

    def test_basic_counts(self):
        books = [_book(highlights=5, notes=2)]
        stats = compute_stats(books)
        assert stats.total_books == 1
        assert stats.total_annotations == 7
        assert stats.total_highlights == 5
        assert stats.total_notes == 2

    def test_avg_highlights_per_book(self):
        books = [
            _book("A", highlights=4, notes=0),
            _book("B", highlights=6, notes=0),
        ]
        stats = compute_stats(books)
        assert stats.avg_highlights_per_book == 5.0

    def test_books_in_progress(self):
        books = [
            _book("A", read_percent=50.0),
            _book("B", read_percent=100.0),
            _book("C", read_percent=0.0),
        ]
        stats = compute_stats(books)
        assert stats.books_in_progress == 1
        assert stats.books_completed == 1

    def test_top_authors(self):
        books = [
            _book("A", author="Alice"),
            _book("B", author="Alice"),
            _book("C", author="Bob"),
        ]
        stats = compute_stats(books)
        assert stats.top_authors[0] == ("Alice", 2)

    def test_shelf_counts(self):
        books = [
            _book("A", shelves=["Sci-Fi", "Favorites"]),
            _book("B", shelves=["Sci-Fi"]),
        ]
        stats = compute_stats(books)
        shelf_dict = dict(stats.shelf_counts)
        assert shelf_dict["Sci-Fi"] == 2
        assert shelf_dict["Favorites"] == 1

    def test_annotation_type_counts(self):
        books = [_book(highlights=3, notes=2)]
        stats = compute_stats(books)
        assert stats.annotation_type_counts["highlight"] == 3
        assert stats.annotation_type_counts["note"] == 2

    def test_recently_read(self):
        books = [
            _book("A", date_last_read=datetime(2026, 3, 1)),
            _book("B", date_last_read=datetime(2026, 4, 1)),
        ]
        stats = compute_stats(books)
        assert len(stats.recently_read) == 2
        assert stats.recently_read[0][0] == "B"  # most recent first

    def test_reading_activity_by_day(self):
        books = [_book(highlights=3)]  # highlights have created_at dates
        stats = compute_stats(books)
        assert len(stats.reading_activity_by_day) > 0

    def test_progress_distribution(self):
        books = [
            _book("A", read_percent=0),
            _book("B", read_percent=25),
            _book("C", read_percent=50),
            _book("D", read_percent=75),
            _book("E", read_percent=100),
        ]
        stats = compute_stats(books)
        assert stats.progress_distribution["0%"] == 1
        assert stats.progress_distribution["100%"] == 1

    def test_books_by_highlight_count_sorted(self):
        books = [
            _book("A", highlights=1),
            _book("B", highlights=10),
            _book("C", highlights=5),
        ]
        stats = compute_stats(books)
        assert stats.books_by_highlight_count[0] == ("B", 10)
