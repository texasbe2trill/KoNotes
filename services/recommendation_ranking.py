"""Recommendation ranking — deduplication and priority ordering.

Keeps the top *max_results* recommendations, ensuring no book appears in more
than one non-compare recommendation slot.  The ``compare`` kind is exempt from
deduplication because it intentionally surfaces two books at once.
"""
from __future__ import annotations

from models.recommendation import KIND_COMPARE, Recommendation


def rank_recommendations(
    recs: list[Recommendation],
    *,
    max_results: int = 5,
) -> list[Recommendation]:
    """Return the top *max_results* recommendations, deduplicated by book.

    Rules:
    - Sorted by ``priority_score`` descending.
    - A book title may appear in at most one recommendation (except ``compare``).
    - ``compare`` recommendations are kept as-is (two books, one card).
    - ``max_results`` caps the final list.
    """
    seen_books: set[str] = set()
    ranked: list[Recommendation] = []

    for rec in sorted(recs, key=lambda r: r.priority_score, reverse=True):
        if rec.kind == KIND_COMPARE:
            # Compare cards are always included (not deduplicated against other kinds)
            ranked.append(rec)
        else:
            book_key = rec.related_books[0] if rec.related_books else rec.id
            if book_key in seen_books:
                continue
            seen_books.add(book_key)
            ranked.append(rec)

        if len(ranked) >= max_results:
            break

    return ranked
