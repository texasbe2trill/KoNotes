"""Stats service: compute summary statistics over a collection of Books."""
from __future__ import annotations

from dataclasses import dataclass

from models.book import Book


@dataclass
class LibraryStats:
    total_books: int
    total_annotations: int
    total_highlights: int
    total_notes: int
    books_by_highlight_count: list[tuple[str, int]]


def compute_stats(books: list[Book]) -> LibraryStats:
    """Return aggregate statistics for a list of :class:`Book` objects."""
    total_annotations = 0
    total_highlights = 0
    total_notes = 0
    highlight_counts: list[tuple[str, int]] = []

    for book in books:
        ann_count = len(book.annotations)
        total_annotations += ann_count

        h_count = sum(1 for a in book.annotations if a.kind == "highlight")
        n_count = sum(1 for a in book.annotations if a.kind == "note")
        total_highlights += h_count
        total_notes += n_count

        highlight_counts.append((book.title, h_count))

    highlight_counts.sort(key=lambda x: x[1], reverse=True)

    return LibraryStats(
        total_books=len(books),
        total_annotations=total_annotations,
        total_highlights=total_highlights,
        total_notes=total_notes,
        books_by_highlight_count=highlight_counts,
    )
