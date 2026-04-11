"""Stats service: compute summary statistics over a collection of Books."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from models.book import Book


@dataclass
class LibraryStats:
    total_books: int = 0
    total_annotations: int = 0
    total_highlights: int = 0
    total_notes: int = 0
    books_in_progress: int = 0
    books_completed: int = 0
    books_not_started: int = 0
    avg_highlights_per_book: float = 0.0
    books_by_highlight_count: list[tuple[str, int]] = field(default_factory=list)
    top_authors: list[tuple[str, int]] = field(default_factory=list)
    shelf_counts: list[tuple[str, int]] = field(default_factory=list)
    annotation_type_counts: dict[str, int] = field(default_factory=dict)
    recently_read: list[tuple[str, str | None, datetime]] = field(default_factory=list)
    reading_activity_by_day: list[tuple[str, int]] = field(default_factory=list)
    progress_distribution: dict[str, int] = field(default_factory=dict)
    total_reading_time_sec: int = 0
    total_page_turns: int = 0
    total_words_looked_up: int = 0
    books_with_ratings: int = 0
    avg_rating: float = 0.0
    books_by_reading_time: list[tuple[str, int]] = field(default_factory=list)


def compute_stats(books: list[Book]) -> LibraryStats:
    """Return aggregate statistics for a list of :class:`Book` objects."""
    if not books:
        return LibraryStats()

    total_annotations = 0
    total_highlights = 0
    total_notes = 0
    highlight_counts: list[tuple[str, int]] = []
    reading_time_counts: list[tuple[str, int]] = []
    author_counter: Counter[str] = Counter()
    shelf_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    day_counter: Counter[str] = Counter()
    in_progress = 0
    completed = 0
    not_started = 0
    recently_read: list[tuple[str, str | None, datetime]] = []
    total_reading_time = 0
    total_page_turns = 0
    rating_sum = 0
    rating_count = 0

    for book in books:
        ann_count = len(book.annotations)
        total_annotations += ann_count

        h_count = sum(1 for a in book.annotations if a.kind == "highlight")
        n_count = sum(1 for a in book.annotations if a.kind == "note")
        u_count = ann_count - h_count - n_count
        total_highlights += h_count
        total_notes += n_count

        type_counter["highlight"] += h_count
        type_counter["note"] += n_count
        if u_count:
            type_counter["unknown"] += u_count

        highlight_counts.append((book.title, h_count))

        if book.author:
            author_counter[book.author] += 1

        for shelf in book.shelves:
            shelf_counter[shelf] += 1

        # Progress classification
        pct = book.read_percent
        if pct is not None:
            if pct >= 100:
                completed += 1
            elif pct > 0:
                in_progress += 1
            else:
                not_started += 1
        elif book.read_status:
            rs = str(book.read_status).lower()
            if "finish" in rs or rs == "2":
                completed += 1
            elif rs in ("1", "reading"):
                in_progress += 1

        if book.date_last_read:
            recently_read.append((book.title, book.author, book.date_last_read))

        # Reading time and page turns
        if book.time_spent_reading and book.time_spent_reading > 0:
            total_reading_time += book.time_spent_reading
            reading_time_counts.append((book.title, book.time_spent_reading))
        if book.page_turns and book.page_turns > 0:
            total_page_turns += book.page_turns
        if book.rating and 1 <= book.rating <= 5:
            rating_sum += book.rating
            rating_count += 1

        # Activity by day from annotation timestamps
        for ann in book.annotations:
            if ann.created_at:
                day_counter[ann.created_at.strftime("%Y-%m-%d")] += 1

    highlight_counts.sort(key=lambda x: x[1], reverse=True)
    reading_time_counts.sort(key=lambda x: x[1], reverse=True)
    recently_read.sort(key=lambda x: x[2], reverse=True)

    avg_hl = total_highlights / len(books) if books else 0.0

    # Progress distribution buckets
    progress_dist: dict[str, int] = {
        "0%": 0, "1-25%": 0, "26-50%": 0, "51-75%": 0, "76-99%": 0, "100%": 0,
    }
    for book in books:
        pct = book.read_percent
        if pct is None:
            continue
        if pct <= 0:
            progress_dist["0%"] += 1
        elif pct <= 25:
            progress_dist["1-25%"] += 1
        elif pct <= 50:
            progress_dist["26-50%"] += 1
        elif pct <= 75:
            progress_dist["51-75%"] += 1
        elif pct < 100:
            progress_dist["76-99%"] += 1
        else:
            progress_dist["100%"] += 1

    return LibraryStats(
        total_books=len(books),
        total_annotations=total_annotations,
        total_highlights=total_highlights,
        total_notes=total_notes,
        books_in_progress=in_progress,
        books_completed=completed,
        books_not_started=not_started,
        avg_highlights_per_book=round(avg_hl, 1),
        books_by_highlight_count=highlight_counts,
        top_authors=author_counter.most_common(10),
        shelf_counts=shelf_counter.most_common(),
        annotation_type_counts=dict(type_counter),
        recently_read=recently_read[:10],
        reading_activity_by_day=sorted(day_counter.items()),
        progress_distribution=progress_dist,
        total_reading_time_sec=total_reading_time,
        total_page_turns=total_page_turns,
        books_with_ratings=rating_count,
        avg_rating=round(rating_sum / rating_count, 1) if rating_count else 0.0,
        books_by_reading_time=reading_time_counts,
    )
