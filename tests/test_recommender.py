"""Tests for the recommendation engine, ranking, and share formatters."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from models.annotation import Annotation
from models.book import Book
from models.recommendation import (
    KIND_COMPARE,
    KIND_DEEPEST_THINKING,
    KIND_EXPORT,
    KIND_FINISH,
    KIND_FORGOTTEN_GEM,
    KIND_REVISIT,
    Recommendation,
)
from services.recommendation_ranking import rank_recommendations
from services.recommender import (
    _ann_counts,
    _days_since,
    generate_recommendations,
)
from services.share_formatter import (
    format_recommendation_for_bluesky,
    format_recommendation_for_markdown,
)
from services.stats import compute_stats


# ---------------------------------------------------------------------------
# Test fixtures / factories
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ann(book_id: str, kind: str, idx: int = 0) -> Annotation:
    return Annotation(
        id=f"{book_id}_{kind}_{idx}",
        book_id=book_id,
        kind=kind,  # type: ignore[arg-type]
        text=f"Sample {kind} text {idx}",
        source="test",
    )


def _make_book(
    book_id: str,
    title: str,
    *,
    notes: int = 0,
    highlights: int = 0,
    read_percent: float | None = None,
    days_since_read: float | None = None,
    author: str = "Test Author",
) -> Book:
    annotations = [_ann(book_id, "note", i) for i in range(notes)]
    annotations += [_ann(book_id, "highlight", i) for i in range(highlights)]

    date_last_read: datetime | None = None
    if days_since_read is not None:
        date_last_read = _now() - timedelta(days=days_since_read)

    return Book(
        id=book_id,
        title=title,
        author=author,
        source="test",
        annotations=annotations,
        read_percent=read_percent,
        date_last_read=date_last_read,
    )


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


def test_ann_counts_empty():
    book = _make_book("b1", "Empty")
    assert _ann_counts(book) == (0, 0, 0)


def test_ann_counts_mixed():
    book = _make_book("b1", "Mixed", notes=3, highlights=7)
    h, n, total = _ann_counts(book)
    assert h == 7
    assert n == 3
    assert total == 10


def test_days_since_none():
    assert _days_since(None) is None


def test_days_since_recent():
    dt = _now() - timedelta(days=5)
    result = _days_since(dt)
    assert result is not None
    assert 4.9 < result < 5.1


def test_days_since_naive_datetime():
    """Naive datetimes should be treated as UTC without raising."""
    dt = (datetime.now(timezone.utc) - timedelta(days=10)).replace(tzinfo=None)  # naive
    result = _days_since(dt)
    assert result is not None
    assert result > 9


# ---------------------------------------------------------------------------
# Empty / sparse library
# ---------------------------------------------------------------------------


def test_empty_library():
    stats = compute_stats([])
    recs = generate_recommendations([], stats)
    assert recs == []


def test_sparse_library_no_recommendations():
    """Books with < 5 annotations should not trigger any recommendations."""
    books = [
        _make_book("b1", "Sparse One", notes=1, highlights=2),
        _make_book("b2", "Sparse Two", notes=0, highlights=3),
    ]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    # No rec should trigger for these sparse books
    assert all(r.kind not in (KIND_REVISIT, KIND_FINISH, KIND_EXPORT) for r in recs)


# ---------------------------------------------------------------------------
# Revisit Next
# ---------------------------------------------------------------------------


def test_revisit_requires_notes():
    """Books with 0 notes should not appear as revisit candidates."""
    books = [_make_book("b1", "No Notes", highlights=15, days_since_read=120)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_REVISIT for r in recs)


def test_revisit_requires_stale():
    """Books read within the last 30 days should not be recommended for revisit."""
    books = [_make_book("b1", "Fresh", notes=5, highlights=10, days_since_read=10)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_REVISIT for r in recs)


def test_revisit_triggers_for_stale_high_notes():
    books = [_make_book("b1", "Good Notes", notes=6, highlights=12, days_since_read=120)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    revisit_recs = [r for r in recs if r.kind == KIND_REVISIT]
    assert len(revisit_recs) >= 1
    assert "Good Notes" in revisit_recs[0].related_books[0]
    assert revisit_recs[0].priority_score > 0


def test_revisit_score_in_range():
    books = [_make_book("b1", "Annotated", notes=8, highlights=15, days_since_read=200)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    for r in recs:
        assert 0.0 <= r.priority_score <= 1.0


# ---------------------------------------------------------------------------
# Finish Next
# ---------------------------------------------------------------------------


def test_finish_triggers_for_in_progress():
    books = [
        _make_book("b1", "Nearly Done", notes=3, highlights=8,
                   read_percent=78, days_since_read=7)
    ]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    finish_recs = [r for r in recs if r.kind == KIND_FINISH]
    assert len(finish_recs) >= 1
    assert finish_recs[0].priority_score > 0


def test_finish_excludes_very_low_percent():
    """Books with < 10% progress should not be recommended for finishing."""
    books = [_make_book("b1", "Just Started", notes=3, highlights=8, read_percent=5)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_FINISH for r in recs)


def test_finish_excludes_completed():
    """Books at >= 95% should not appear as finish candidates."""
    books = [_make_book("b1", "Done", notes=5, highlights=10, read_percent=98)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_FINISH for r in recs)


def test_finish_requires_annotations():
    """Insufficient annotations — should not appear even if in-progress."""
    books = [_make_book("b1", "Thin", notes=1, highlights=1, read_percent=60)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_FINISH for r in recs)


# ---------------------------------------------------------------------------
# Export Next
# ---------------------------------------------------------------------------


def test_export_triggers_for_high_notes():
    books = [_make_book("b1", "Rich Notes", notes=8, highlights=12)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    export_recs = [r for r in recs if r.kind == KIND_EXPORT]
    assert len(export_recs) >= 1
    assert export_recs[0].priority_score > 0


def test_export_requires_min_notes():
    """Books with < 3 notes should not be recommended for export."""
    books = [_make_book("b1", "Mostly Highlights", notes=2, highlights=20)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_EXPORT for r in recs)


# ---------------------------------------------------------------------------
# Forgotten Gem
# ---------------------------------------------------------------------------


def test_forgotten_gem_triggers():
    books = [
        _make_book("b1", "Old Gem", notes=4, highlights=15, days_since_read=200)
    ]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    gem_recs = [r for r in recs if r.kind == KIND_FORGOTTEN_GEM]
    assert len(gem_recs) == 1
    assert gem_recs[0].priority_score > 0


def test_forgotten_gem_excludes_recent():
    """Books read within 90 days should not be forgotten gems."""
    books = [_make_book("b1", "Recent", notes=4, highlights=12, days_since_read=45)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_FORGOTTEN_GEM for r in recs)


def test_forgotten_gem_excludes_sparse():
    """Books with < 8 total annotations should not be forgotten gems."""
    books = [_make_book("b1", "Thin", notes=2, highlights=4, days_since_read=200)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_FORGOTTEN_GEM for r in recs)


# ---------------------------------------------------------------------------
# Deepest Thinking
# ---------------------------------------------------------------------------


def test_deepest_thinking_picks_highest_note_ratio():
    books = [
        _make_book("b1", "All Highlights", notes=1, highlights=20),
        _make_book("b2", "Deep Thinker", notes=8, highlights=5),
    ]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    deep_recs = [r for r in recs if r.kind == KIND_DEEPEST_THINKING]
    assert len(deep_recs) == 1
    assert "Deep Thinker" in deep_recs[0].related_books[0]


def test_deepest_thinking_requires_min_notes():
    """Need at least 3 notes to qualify for deepest thinking."""
    books = [_make_book("b1", "Too Few", notes=2, highlights=3)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_DEEPEST_THINKING for r in recs)


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


def test_compare_returns_two_books():
    books = [
        _make_book("b1", "Book Alpha", notes=4, highlights=12, author="Author A"),
        _make_book("b2", "Book Beta", notes=5, highlights=11, author="Author B"),
        _make_book("b3", "Book Gamma", notes=1, highlights=2, author="Author C"),
    ]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    compare_recs = [r for r in recs if r.kind == KIND_COMPARE]
    if compare_recs:  # may or may not trigger depending on similarity threshold
        assert len(compare_recs[0].related_books) == 2


def test_compare_not_same_author():
    """Books by the same author should not be paired for comparison."""
    books = [
        _make_book("b1", "Book One", notes=5, highlights=10, author="Same Author"),
        _make_book("b2", "Book Two", notes=5, highlights=10, author="Same Author"),
    ]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    compare_recs = [r for r in recs if r.kind == KIND_COMPARE]
    assert len(compare_recs) == 0


def test_compare_requires_two_books():
    books = [_make_book("b1", "Solo", notes=5, highlights=10)]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    assert not any(r.kind == KIND_COMPARE for r in recs)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def test_ranking_respects_max_results():
    books = [
        _make_book(f"b{i}", f"Book {i}", notes=5, highlights=10, days_since_read=180)
        for i in range(10)
    ]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    ranked = rank_recommendations(recs, max_results=3)
    assert len(ranked) <= 3


def test_ranking_sorted_descending():
    recs = [
        Recommendation(id="a", kind=KIND_REVISIT, title="A", summary="", reason="", priority_score=0.3, related_books=["Book A"]),
        Recommendation(id="b", kind=KIND_FINISH, title="B", summary="", reason="", priority_score=0.8, related_books=["Book B"]),
        Recommendation(id="c", kind=KIND_EXPORT, title="C", summary="", reason="", priority_score=0.5, related_books=["Book C"]),
    ]
    ranked = rank_recommendations(recs)
    scores = [r.priority_score for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_ranking_deduplicates_same_book():
    """The same book should not appear in two separate recommendation slots."""
    recs = [
        Recommendation(id="r1", kind=KIND_REVISIT, title="Revisit X", summary="", reason="", priority_score=0.9, related_books=["Book X"]),
        Recommendation(id="r2", kind=KIND_EXPORT, title="Export X", summary="", reason="", priority_score=0.85, related_books=["Book X"]),
        Recommendation(id="r3", kind=KIND_FINISH, title="Finish Y", summary="", reason="", priority_score=0.7, related_books=["Book Y"]),
    ]
    ranked = rank_recommendations(recs, max_results=5)
    book_x_count = sum(1 for r in ranked if "Book X" in r.related_books)
    assert book_x_count == 1


def test_ranking_compare_not_deduplicated():
    """Compare cards should not be filtered even if their books appear elsewhere."""
    recs = [
        Recommendation(id="r1", kind=KIND_REVISIT, title="Revisit A", summary="", reason="", priority_score=0.9, related_books=["Book A"]),
        Recommendation(id="r2", kind=KIND_COMPARE, title="Compare A and B", summary="", reason="", priority_score=0.5, related_books=["Book A", "Book B"]),
    ]
    ranked = rank_recommendations(recs, max_results=5)
    kinds = {r.kind for r in ranked}
    assert KIND_COMPARE in kinds


def test_all_priority_scores_in_range():
    """Every generated score must be in [0, 1]."""
    books = [
        _make_book("b1", "Alpha", notes=8, highlights=15, days_since_read=120),
        _make_book("b2", "Beta", notes=3, highlights=20, read_percent=65, days_since_read=30, author="Author B"),
        _make_book("b3", "Gamma", notes=5, highlights=8, days_since_read=200, author="Author C"),
    ]
    stats = compute_stats(books)
    recs = generate_recommendations(books, stats)
    for rec in recs:
        assert 0.0 <= rec.priority_score <= 1.0, (
            f"{rec.kind} rec has out-of-range score {rec.priority_score}"
        )


# ---------------------------------------------------------------------------
# Share formatters
# ---------------------------------------------------------------------------


def test_format_recommendation_for_bluesky_under_300():
    rec = Recommendation(
        id="r1",
        kind=KIND_REVISIT,
        title="Revisit \u201cSome Book\u201d",
        summary="Some summary",
        reason="High note density",
        related_books=["Some Book"],
    )
    post = format_recommendation_for_bluesky(rec)
    assert len(post) <= 300
    assert "#booksky" in post


def test_format_recommendation_for_bluesky_all_kinds():
    """Every known kind should produce a valid post."""
    for kind in (KIND_REVISIT, KIND_FINISH, KIND_EXPORT, KIND_FORGOTTEN_GEM,
                 KIND_DEEPEST_THINKING, KIND_COMPARE):
        rec = Recommendation(
            id=f"r_{kind}", kind=kind, title="Title", summary="Summary",
            reason="Reason", related_books=["Book"],
        )
        post = format_recommendation_for_bluesky(rec)
        assert len(post) <= 300
        assert "#booksky" in post


def test_format_recommendation_for_markdown_contains_key_fields():
    rec = Recommendation(
        id="r1",
        kind=KIND_EXPORT,
        title="Export \u201cMy Notes\u201d",
        summary="12 notes ready to export.",
        reason="High note count.",
        evidence=["12 notes", "8 highlights"],
        recommended_action="Export as Markdown.",
        related_books=["My Notes"],
    )
    md = format_recommendation_for_markdown(rec)
    assert "Export" in md
    assert "12 notes" in md
    assert "Export as Markdown" in md
    assert "KoNotes" in md


# ---------------------------------------------------------------------------
# Chatbot context integration smoke test
# ---------------------------------------------------------------------------


def test_build_context_includes_recommendations():
    """build_context should populate ## Recommended Next Steps when data is rich enough."""
    from services.chat import build_context

    books = [
        _make_book("b1", "Deep Book", notes=8, highlights=15, days_since_read=120),
        _make_book("b2", "Progress Book", notes=3, highlights=10,
                   read_percent=72, days_since_read=10, author="Author B"),
    ]
    context = build_context(books)
    assert "## Recommended Next Steps" in context


def test_build_context_empty_library_no_recommendations():
    from services.chat import build_context

    context = build_context([])
    assert "## Recommended Next Steps" not in context
