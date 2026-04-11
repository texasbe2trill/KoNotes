"""Library summary service: builds structured summaries for CLI and UI."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.activity import ReadingSession
from models.book import Book
from models.shelf import Shelf
from services.stats import LibraryStats, compute_stats


@dataclass
class LibrarySummary:
    """A complete summary of the user's Kobo library and reading activity."""

    stats: LibraryStats
    shelves: list[Shelf] = field(default_factory=list)
    sessions: list[ReadingSession] = field(default_factory=list)
    recently_read_books: list[Book] = field(default_factory=list)
    in_progress_books: list[Book] = field(default_factory=list)
    completed_books: list[Book] = field(default_factory=list)
    most_highlighted_books: list[tuple[Book, int]] = field(default_factory=list)


def build_library_summary(
    books: list[Book],
    shelves: list[Shelf] | None = None,
    sessions: list[ReadingSession] | None = None,
) -> LibrarySummary:
    """Build a complete library summary from books and optional telemetry."""
    stats = compute_stats(books)

    recently_read = sorted(
        [b for b in books if b.date_last_read is not None],
        key=lambda b: b.date_last_read or datetime.min,
        reverse=True,
    )[:10]

    in_progress = [
        b for b in books
        if b.read_percent is not None and 0 < b.read_percent < 100
    ]

    completed = [
        b for b in books
        if b.read_percent is not None and b.read_percent >= 100
    ]

    most_highlighted: list[tuple[Book, int]] = []
    for book in books:
        h_count = sum(1 for a in book.annotations if a.kind == "highlight")
        if h_count > 0:
            most_highlighted.append((book, h_count))
    most_highlighted.sort(key=lambda x: x[1], reverse=True)

    return LibrarySummary(
        stats=stats,
        shelves=shelves or [],
        sessions=sessions or [],
        recently_read_books=recently_read,
        in_progress_books=in_progress,
        completed_books=completed,
        most_highlighted_books=most_highlighted[:10],
    )
