"""Recommendation engine — deterministic, explainable suggestions from the user's own library.

All logic is local-first: no external APIs, no ML models.  Every recommendation
is grounded in actual annotation data and includes a clear reason and evidence trail.

Recommendation types
--------------------
- revisit          Books with high note density not recently revisited
- finish           In-progress books close to completion with strong engagement
- export           Books whose notes are most worth moving to a notes system
- forgotten_gem    Books with past deep engagement that haven't been touched in months
- deepest_thinking The book where the user's own thinking is most present
- compare          Two books with similar engagement profiles worth reading side by side
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

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
from services.stats import LibraryStats


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_recommendations(
    books: list[Book],
    stats: LibraryStats,
    word_lookups: Iterable | None = None,
) -> list[Recommendation]:
    """Generate all recommendations sorted by priority (highest first).

    Safe to call with an empty library — returns an empty list.
    """
    if not books:
        return []

    recs: list[Recommendation] = []
    recs.extend(_revisit_next(books))
    recs.extend(_finish_next(books))
    recs.extend(_export_next(books))
    recs.extend(_forgotten_gem(books))
    recs.extend(_deepest_thinking(books))

    compare = _compare_these_two(books)
    if compare is not None:
        recs.append(compare)

    recs.sort(key=lambda r: r.priority_score, reverse=True)
    return recs


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _ann_counts(book: Book) -> tuple[int, int, int]:
    """Return (highlights, notes, total) for a book."""
    h = sum(1 for a in book.annotations if a.kind == "highlight")
    n = sum(1 for a in book.annotations if a.kind == "note")
    return h, n, h + n


def _days_since(dt: datetime | None) -> float | None:
    """Days elapsed since *dt*.  Returns None when *dt* is None."""
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _norm(value: float, lo: float, hi: float) -> float:
    """Linearly normalize *value* from [lo, hi] to [0, 1], clamped."""
    if hi <= lo:
        return 0.0
    return _clamp((value - lo) / (hi - lo))


# ---------------------------------------------------------------------------
# Rule: Revisit Next
# ---------------------------------------------------------------------------


def _revisit_next(books: list[Book]) -> list[Recommendation]:
    """Books with high note density that haven't been revisited recently.

    Requires >= 2 notes and >= 5 total annotations.  Books read within the
    last 30 days are excluded (already active).
    """
    results: list[Recommendation] = []

    for book in books:
        h, n, total = _ann_counts(book)
        if total < 5 or n < 2:
            continue

        days = _days_since(book.date_last_read)
        # Skip recently-active books
        if days is not None and days < 30:
            continue

        note_ratio = n / total

        # Staleness contributes up to 0.3 to the score; saturates at 1 year.
        staleness = _norm(days if days is not None else 60, 30, 365) * 0.3
        staleness_label = _staleness_label(days)

        score = _clamp(
            _norm(n, 2, 15) * 0.35
            + _norm(total, 5, 40) * 0.20
            + note_ratio * 0.25
            + staleness
        )

        evidence: list[str] = [f"{n} notes and {h} highlights captured"]
        if note_ratio >= 0.30:
            evidence.append(f"Note density: {note_ratio:.0%} of annotations are your own thoughts")
        if staleness_label:
            evidence.append(staleness_label)

        results.append(
            Recommendation(
                id=f"revisit_{book.id}",
                kind=KIND_REVISIT,
                title=f'Revisit \u201c{book.title}\u201d',
                summary=(
                    f"Your best thinking on this book may be waiting to be rediscovered."
                    f" {n} notes capture ideas worth returning to."
                ),
                reason=f"{total} annotations with strong note density suggest deep past engagement.",
                evidence=evidence[:4],
                priority_score=round(score, 3),
                related_books=[book.title],
                recommended_action=f'Reread your {n} notes in \u201c{book.title}\u201d and see what still holds.',
                source="rule",
            )
        )

    results.sort(key=lambda r: r.priority_score, reverse=True)
    return results[:2]


def _staleness_label(days: float | None) -> str:
    if days is None:
        return ""
    if days > 180:
        months = int(days // 30)
        return f"Not revisited in {months} months"
    if days > 90:
        return f"Not revisited in about {int(days // 30)} months"
    if days > 30:
        return f"Last read {int(days)} days ago"
    return ""


# ---------------------------------------------------------------------------
# Rule: Finish Next
# ---------------------------------------------------------------------------


def _finish_next(books: list[Book]) -> list[Recommendation]:
    """In-progress books close to completion with decent annotation activity.

    Considers books between 10% and 95% read.  Proximity to completion and
    recency of reading are the two strongest signals.
    """
    results: list[Recommendation] = []

    for book in books:
        pct = book.read_percent
        if pct is None or pct < 10 or pct >= 95:
            continue

        h, n, total = _ann_counts(book)
        if total < 3:
            continue

        days = _days_since(book.date_last_read)

        # Closer to done = higher score
        proximity = _norm(pct, 10, 95)

        # Recency: active in last 90 days gets a boost; unknown gets neutral 0.3
        if days is None:
            recency = 0.3
            recency_label = ""
        elif days <= 14:
            recency = 1.0
            recency_label = f"Reading actively ({int(days)} days ago)"
        elif days <= 60:
            recency = _norm(60 - days, 0, 60)
            recency_label = f"Last active {int(days)} days ago"
        else:
            recency = 0.0
            recency_label = f"Started {int(days // 30)} months ago"

        score = _clamp(
            proximity * 0.55
            + recency * 0.30
            + _norm(total, 3, 30) * 0.15
        )

        evidence: list[str] = [f"{pct:.0f}% complete"]
        evidence.append(f"{total} annotations already captured")
        if recency_label:
            evidence.append(recency_label)

        results.append(
            Recommendation(
                id=f"finish_{book.id}",
                kind=KIND_FINISH,
                title=f'Finish \u201c{book.title}\u201d',
                summary=f"You\u2019re {pct:.0f}% through \u2014 and your {total} annotations suggest it\u2019s worth completing.",
                reason=f"{pct:.0f}% complete with {total} annotations captured so far.",
                evidence=evidence[:4],
                priority_score=round(score, 3),
                related_books=[book.title],
                recommended_action=f'Pick up \u201c{book.title}\u201d where you left off.',
                source="engagement",
            )
        )

    results.sort(key=lambda r: r.priority_score, reverse=True)
    return results[:2]


# ---------------------------------------------------------------------------
# Rule: Export Next
# ---------------------------------------------------------------------------


def _export_next(books: list[Book]) -> list[Recommendation]:
    """Books whose notes are most worth exporting to a notes system.

    Prioritises high note count and strong note-to-highlight ratio.
    """
    results: list[Recommendation] = []

    for book in books:
        h, n, total = _ann_counts(book)
        if n < 3:
            continue

        note_ratio = n / total if total > 0 else 0.0

        score = _clamp(
            _norm(n, 3, 20) * 0.50
            + _norm(note_ratio, 0.15, 0.70) * 0.30
            + _norm(total, 5, 50) * 0.20
        )

        evidence: list[str] = [f"{n} notes worth preserving"]
        if h > 0:
            evidence.append(f"{h} highlights for additional context")
        if note_ratio >= 0.30:
            evidence.append(f"Note density: {note_ratio:.0%} of annotations are your own thoughts")

        results.append(
            Recommendation(
                id=f"export_{book.id}",
                kind=KIND_EXPORT,
                title=f'Export \u201c{book.title}\u201d',
                summary=f"{n} notes and {h} highlights are ready to move to your notes system.",
                reason="Strong note count and note-to-highlight ratio make this a high-value export.",
                evidence=evidence[:4],
                priority_score=round(score, 3),
                related_books=[book.title],
                recommended_action=f'Export \u201c{book.title}\u201d as Markdown or JSON to preserve your thinking.',
                source="rule",
            )
        )

    results.sort(key=lambda r: r.priority_score, reverse=True)
    return results[:2]


# ---------------------------------------------------------------------------
# Rule: Forgotten Gem
# ---------------------------------------------------------------------------


def _forgotten_gem(books: list[Book]) -> list[Recommendation]:
    """Books with strong historical engagement that haven't been touched in months.

    Requires >= 8 total annotations and >= 90 days since last read.
    """
    results: list[Recommendation] = []

    for book in books:
        h, n, total = _ann_counts(book)
        if total < 8:
            continue

        days = _days_since(book.date_last_read)
        if days is None or days < 90:
            continue

        months = max(1, int(days // 30))

        score = _clamp(
            _norm(total, 8, 60) * 0.50
            + _norm(days, 90, 730) * 0.30
            + _norm(n, 0, 10) * 0.20
        )

        evidence: list[str] = [f"{total} annotations captured in the past"]
        evidence.append(f"Not revisited in {months} month{'s' if months != 1 else ''}")
        if n > 0:
            evidence.append(f"{n} notes still in your library")

        results.append(
            Recommendation(
                id=f"gem_{book.id}",
                kind=KIND_FORGOTTEN_GEM,
                title=f'Rediscover \u201c{book.title}\u201d',
                summary=f"You engaged deeply here {months} month{'s' if months != 1 else ''} ago \u2014 these highlights still hold value.",
                reason=f"{total} annotations captured; not revisited in {months} months.",
                evidence=evidence[:4],
                priority_score=round(score, 3),
                related_books=[book.title],
                recommended_action=f'Spend 10 minutes rereading your highlights from \u201c{book.title}\u201d.',
                source="engagement",
            )
        )

    results.sort(key=lambda r: r.priority_score, reverse=True)
    return results[:1]


# ---------------------------------------------------------------------------
# Rule: Deepest Thinking
# ---------------------------------------------------------------------------


def _deepest_thinking(books: list[Book]) -> list[Recommendation]:
    """The single book where the user's own written thinking is most present.

    Selects the book with the highest note-to-annotation ratio (minimum 3 notes,
    5 total annotations).  Score is slightly deflated so it doesn't always
    dominate other higher-urgency recommendations.
    """
    candidates: list[tuple[Book, int, int, int, float, float]] = []

    for book in books:
        h, n, total = _ann_counts(book)
        if n < 3 or total < 5:
            continue
        note_ratio = n / total
        raw = _clamp(_norm(note_ratio, 0.3, 1.0) * 0.60 + _norm(n, 3, 20) * 0.40)
        # Deflate slightly so urgency recommendations surface first
        score = raw * 0.82
        candidates.append((book, h, n, total, note_ratio, score))

    if not candidates:
        return []

    candidates.sort(key=lambda x: x[5], reverse=True)
    book, h, n, total, note_ratio, score = candidates[0]

    evidence: list[str] = [
        f"{n} notes out of {total} total annotations",
        f"{note_ratio:.0%} of annotations are your own words",
    ]
    if h > 0:
        evidence.append(f"{h} highlights anchoring your notes in the text")

    return [
        Recommendation(
            id=f"deep_{book.id}",
            kind=KIND_DEEPEST_THINKING,
            title=f'Your Deepest Thinking: \u201c{book.title}\u201d',
            summary="More of your own words appear here than anywhere else in your library.",
            reason=f"{note_ratio:.0%} note density \u2014 the highest in your library.",
            evidence=evidence[:4],
            priority_score=round(score, 3),
            related_books=[book.title],
            recommended_action=f'Read your notes in \u201c{book.title}\u201d as if they were a personal essay.',
            source="rule",
        )
    ]


# ---------------------------------------------------------------------------
# Rule: Compare These Two
# ---------------------------------------------------------------------------


def _compare_these_two(books: list[Book]) -> Recommendation | None:
    """Suggest two books with similar engagement profiles worth reading side by side.

    Uses annotation count and note ratio as the similarity signal.  Caps
    candidates at the top 20 annotated books to keep it O(n).  Returns None
    when no sufficiently similar pair is found.
    """
    candidates = [
        (book, total, n / total if total > 0 else 0.0)
        for book in books
        for _, n, total in [_ann_counts(book)]
        if total >= 5
    ]

    if len(candidates) < 2:
        return None

    # Consider only the top 20 most-annotated books
    candidates.sort(key=lambda x: x[1], reverse=True)
    candidates = candidates[:20]

    best_pair: tuple | None = None
    best_similarity = float("inf")

    # Check all adjacent pairs after sorting by annotation count
    for i in range(len(candidates) - 1):
        b1, t1, r1 = candidates[i]
        b2, t2, r2 = candidates[i + 1]

        # Don't compare books by the same author if author is known
        if (
            b1.author
            and b2.author
            and b1.author.strip().lower() == b2.author.strip().lower()
        ):
            continue

        count_diff = abs(t1 - t2) / max(t1, t2, 1)
        ratio_diff = abs(r1 - r2)
        similarity = count_diff * 0.60 + ratio_diff * 0.40

        if similarity < best_similarity:
            best_similarity = similarity
            best_pair = (b1, b2, t1, t2, r1, r2)

    if best_pair is None or best_similarity > 0.40:
        return None

    b1, b2, t1, t2, r1, r2 = best_pair
    score = _clamp((1.0 - best_similarity) * 0.60)

    return Recommendation(
        id=f"compare_{b1.id}_{b2.id}",
        kind=KIND_COMPARE,
        title=f'Compare \u201c{b1.title}\u201d and \u201c{b2.title}\u201d',
        summary="These two books drew similar levels of engagement from you.",
        reason="Similar annotation count and note density suggest overlapping intellectual territory.",
        evidence=[
            f'\u201c{b1.title}\u201d: {t1} annotations ({r1:.0%} notes)',
            f'\u201c{b2.title}\u201d: {t2} annotations ({r2:.0%} notes)',
            "Similar depth of engagement across both books",
        ],
        priority_score=round(score, 3),
        related_books=[b1.title, b2.title],
        recommended_action="Read your highlights from both books side by side and look for patterns.",
        source="similarity",
    )
