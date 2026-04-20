"""Tests for the hero insight engine."""
from __future__ import annotations

from models.annotation import Annotation
from models.book import Book
from services.hero_insight_engine import generate_hero_insight
from services.stats import compute_stats


def _ann(book_id: str, kind: str, idx: int) -> Annotation:
    return Annotation(
        id=f"{book_id}-{kind}-{idx}",
        book_id=book_id,
        kind=kind,  # type: ignore[arg-type]
        text=f"sample {kind} {idx}",
        source="test",
    )


def _book(book_id: str, title: str, highlights: int = 0, notes: int = 0) -> Book:
    annotations: list[Annotation] = []
    for i in range(highlights):
        annotations.append(_ann(book_id, "highlight", i))
    for i in range(notes):
        annotations.append(_ann(book_id, "note", i))
    return Book(id=book_id, title=title, source="test", annotations=annotations)


# ---------------------------------------------------------------------------
# Pattern triggers
# ---------------------------------------------------------------------------


def test_fallback_when_data_is_sparse() -> None:
    books = [_book("b1", "Tiny Book", highlights=2)]
    stats = compute_stats(books)
    insight = generate_hero_insight(stats, books)
    assert insight.is_fallback is True
    assert insight.pattern == "getting_started"
    assert insight.recommendation


def test_deep_reader_triggered_by_high_note_ratio() -> None:
    books = [
        _book("b1", "Notes Heavy", highlights=40, notes=20),
        _book("b2", "Notes Heavier", highlights=30, notes=15),
    ]
    stats = compute_stats(books)
    insight = generate_hero_insight(stats, books)
    assert insight.pattern == "deep_reader"
    assert "note" in insight.title.lower() or "understand" in insight.title.lower()
    assert insight.evidence
    assert insight.recommendation


def test_pattern_seeker_triggered_by_breadth() -> None:
    books = [_book(f"b{i}", f"Book {i}", highlights=20) for i in range(5)]
    stats = compute_stats(books)
    insight = generate_hero_insight(stats, books)
    assert insight.pattern == "pattern_seeker"
    assert any("5" in e or "Book" in e for e in insight.evidence)


def test_selective_thinker_triggered_by_few_notes() -> None:
    # Spread across many books so no single one dominates (avoid focused_deep_dive)
    # and keep highlight counts under the pattern_seeker threshold per book.
    books = [
        _book(f"b{i}", f"Book {i}", highlights=10, notes=0) for i in range(8)
    ]
    stats = compute_stats(books)
    insight = generate_hero_insight(stats, books)
    assert insight.pattern == "selective_thinker"


def test_focused_deep_dive_triggered_by_dominant_book() -> None:
    books = [
        _book("b1", "The One Book", highlights=80, notes=10),
        _book("b2", "Side", highlights=10),
        _book("b3", "Side Two", highlights=5),
    ]
    stats = compute_stats(books)
    insight = generate_hero_insight(stats, books)
    assert insight.pattern == "focused_deep_dive"
    assert "The One Book" in insight.summary


def test_priority_picks_strongest_match() -> None:
    # A library that triggers BOTH deep_reader and focused_deep_dive;
    # focused_deep_dive should win because of higher priority.
    books = [
        _book("b1", "Dominant", highlights=100, notes=40),
        _book("b2", "Tiny", highlights=5, notes=2),
    ]
    stats = compute_stats(books)
    insight = generate_hero_insight(stats, books)
    assert insight.pattern == "focused_deep_dive"


def test_friction_reader_requires_vocabulary() -> None:
    from models.vocabulary import WordLookup
    from datetime import datetime

    # Multiple books so we don't accidentally trigger focused_deep_dive.
    books = [
        _book("b1", "Reader", highlights=20, notes=1),
        _book("b2", "Reader Two", highlights=18, notes=1),
        _book("b3", "Reader Three", highlights=15, notes=0),
    ]
    lookups = [
        WordLookup(word=f"word{i}", book_id="b1", looked_up_at=datetime(2026, 1, 1))
        for i in range(60)
    ]
    stats = compute_stats(books)
    insight = generate_hero_insight(stats, books, word_lookups=lookups)
    assert insight.pattern == "friction_reader"


def test_insight_always_returns_recommendation_for_real_patterns() -> None:
    books = [_book(f"b{i}", f"Book {i}", highlights=20) for i in range(5)]
    stats = compute_stats(books)
    insight = generate_hero_insight(stats, books)
    assert insight.recommendation
    assert insight.title
    assert insight.summary


def test_evidence_capped_at_four() -> None:
    books = [_book(f"b{i}", f"Book {i}", highlights=25, notes=8) for i in range(6)]
    stats = compute_stats(books)
    insight = generate_hero_insight(
        stats,
        books,
        longest_streak=11,
        total_reading_time_sec=4 * 3600 + 48 * 60,
    )
    assert len(insight.evidence) <= 4
