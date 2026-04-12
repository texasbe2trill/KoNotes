"""Insight Feed service -- generates structured InsightCard objects from library data.

Each generator function produces zero or more InsightCard instances for a
specific category. The top-level ``build_feed`` function collects them all,
deduplicates, ranks, and returns the final feed.
"""
from __future__ import annotations

import hashlib
import logging
from collections import Counter
from datetime import datetime, timedelta

from models.book import Book
from models.insight import EvidenceItem, InsightCard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _card_id(*parts: str) -> str:
    """Deterministic short ID from key parts."""
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _fmt_time(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60}m"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m}m" if m else f"{h}h"


def _pct(value: float) -> str:
    return f"{value:.0f}%"


# ---------------------------------------------------------------------------
# Category generators
# ---------------------------------------------------------------------------


def _library_overview(books: list[Book]) -> list[InsightCard]:
    """Top-level library stats."""
    if not books:
        return []
    total_hl = sum(sum(1 for a in b.annotations if a.kind == "highlight") for b in books)
    total_notes = sum(sum(1 for a in b.annotations if a.kind == "note") for b in books)
    annotated = [b for b in books if b.annotations]
    avg_hl = round(total_hl / len(annotated), 1) if annotated else 0
    total_time = sum(b.time_spent_reading or 0 for b in books)

    evidence = [
        EvidenceItem(label="Books loaded", value=str(len(books))),
        EvidenceItem(label="Books with annotations", value=str(len(annotated))),
        EvidenceItem(label="Total highlights", value=str(total_hl)),
        EvidenceItem(label="Total notes", value=str(total_notes)),
    ]
    if total_time > 0:
        evidence.append(EvidenceItem(label="Total reading time", value=_fmt_time(total_time)))

    body_parts = [
        f"Your library contains {len(books)} books with {total_hl} highlights "
        f"and {total_notes} notes across {len(annotated)} annotated titles.",
    ]
    if avg_hl > 0:
        body_parts.append(f"On average, you capture {avg_hl} highlights per book.")
    if total_time > 0:
        body_parts.append(f"You have spent {_fmt_time(total_time)} reading in total.")

    return [InsightCard(
        id=_card_id("library-overview"),
        title="Library at a Glance",
        category="Library Overview",
        summary=f"{len(annotated)} annotated books, {total_hl} highlights, {total_notes} notes",
        body=" ".join(body_parts),
        evidence=evidence,
        priority_score=_score_overview(books),
        related_books=[b.title for b in annotated[:5]],
        source="computed",
    )]


def _most_engaged_books(books: list[Book]) -> list[InsightCard]:
    """Identify the books with the most engagement."""
    scored: list[tuple[Book, float]] = []
    for b in books:
        hl = sum(1 for a in b.annotations if a.kind == "highlight")
        nt = sum(1 for a in b.annotations if a.kind == "note")
        time_hrs = (b.time_spent_reading or 0) / 3600
        engagement = hl * 1.0 + nt * 1.5 + time_hrs * 2.0
        if engagement > 0:
            scored.append((b, engagement))
    scored.sort(key=lambda x: x[1], reverse=True)
    if not scored:
        return []

    top = scored[:5]
    cards: list[InsightCard] = []

    # Top book card
    best, best_score = top[0]
    hl_count = sum(1 for a in best.annotations if a.kind == "highlight")
    nt_count = sum(1 for a in best.annotations if a.kind == "note")
    evidence = [
        EvidenceItem(label="Highlights", value=str(hl_count)),
        EvidenceItem(label="Notes", value=str(nt_count)),
    ]
    if best.time_spent_reading and best.time_spent_reading > 0:
        evidence.append(EvidenceItem(label="Reading time", value=_fmt_time(best.time_spent_reading)))
    if best.read_percent is not None:
        evidence.append(EvidenceItem(label="Progress", value=_pct(best.read_percent)))

    author_part = f" by {best.author}" if best.author else ""
    cards.append(InsightCard(
        id=_card_id("most-engaged", best.id),
        title=f"Your Most Engaged Book: {best.title}",
        category="Most Engaged Books",
        summary=f"{best.title}{author_part} leads with {hl_count} highlights and {nt_count} notes.",
        body=(
            f"Across your entire library, \"{best.title}\"{author_part} has the highest "
            f"engagement score. You captured {hl_count} highlights and {nt_count} notes"
            + (f", spending {_fmt_time(best.time_spent_reading)} reading" if best.time_spent_reading else "")
            + "."
        ),
        evidence=evidence,
        recommendation=f"Export your notes from \"{best.title}\" for deeper reflection.",
        priority_score=min(best_score / 10, 1.0),
        related_books=[best.title],
        source="computed",
    ))

    # Runner-ups summary
    if len(top) > 1:
        runner_evidence = []
        runner_titles = []
        for book, score in top[1:]:
            hl = sum(1 for a in book.annotations if a.kind == "highlight")
            runner_evidence.append(EvidenceItem(label=book.title, value=f"{hl} highlights"))
            runner_titles.append(book.title)
        cards.append(InsightCard(
            id=_card_id("engaged-runners"),
            title="Other Highly Engaged Books",
            category="Most Engaged Books",
            summary=f"{', '.join(runner_titles[:3])} also show strong engagement.",
            body=(
                "These books round out your most-engaged titles. "
                "Each has a substantial number of annotations relative to the rest of your library."
            ),
            evidence=runner_evidence,
            priority_score=min(top[1][1] / 15, 0.8),
            related_books=runner_titles,
            source="computed",
        ))

    return cards


def _highlight_behavior(books: list[Book]) -> list[InsightCard]:
    """Analyze highlighting patterns."""
    cards: list[InsightCard] = []
    all_books_hl: list[tuple[str, int]] = []
    chapter_counts: Counter[str] = Counter()
    total_hl = 0

    for b in books:
        hl_list = [a for a in b.annotations if a.kind == "highlight"]
        hl_count = len(hl_list)
        total_hl += hl_count
        if hl_count > 0:
            all_books_hl.append((b.title, hl_count))
        for a in hl_list:
            if a.chapter:
                chapter_counts[a.chapter] += 1

    if total_hl < 3:
        return []

    # Distribution insight
    all_books_hl.sort(key=lambda x: x[1], reverse=True)
    top_title, top_count = all_books_hl[0]
    concentration = top_count / total_hl if total_hl else 0

    evidence = [
        EvidenceItem(label="Total highlights", value=str(total_hl)),
        EvidenceItem(label="Books with highlights", value=str(len(all_books_hl))),
        EvidenceItem(label="Most highlighted book", value=f"{top_title} ({top_count})"),
    ]
    if concentration > 0.5:
        summary = (
            f"Over half your highlights ({_pct(concentration * 100)}) "
            f"come from \"{top_title}\". Your focus is concentrated."
        )
        rec = "Try annotating other books to broaden your capture pattern."
    else:
        summary = (
            f"Your highlights are spread across {len(all_books_hl)} books. "
            f"\"{top_title}\" leads with {top_count}."
        )
        rec = None

    cards.append(InsightCard(
        id=_card_id("hl-behavior-dist"),
        title="Highlight Distribution",
        category="Highlight Behavior",
        summary=summary,
        body=(
            f"You have {total_hl} highlights across {len(all_books_hl)} books. "
            f"The top book accounts for {_pct(concentration * 100)} of all highlights."
        ),
        evidence=evidence,
        recommendation=rec,
        priority_score=0.6 + (0.2 if concentration > 0.5 else 0),
        related_books=[t for t, _ in all_books_hl[:5]],
        source="computed",
    ))

    # Most annotated chapters
    if chapter_counts:
        top_chapters = chapter_counts.most_common(5)
        ch_evidence = [
            EvidenceItem(label=ch, value=f"{cnt} highlights") for ch, cnt in top_chapters
        ]
        cards.append(InsightCard(
            id=_card_id("hl-behavior-chapters"),
            title="Your Most Annotated Chapters",
            category="Highlight Behavior",
            summary=f"\"{top_chapters[0][0]}\" has the most highlights ({top_chapters[0][1]}).",
            body=(
                "These chapters captured the most of your attention. "
                "Revisiting them may surface insights you marked but haven't returned to."
            ),
            evidence=ch_evidence,
            recommendation=f"Revisit \"{top_chapters[0][0]}\" and review your annotations.",
            priority_score=0.5,
            related_books=[],
            source="computed",
        ))

    return cards


def _reading_patterns(books: list[Book]) -> list[InsightCard]:
    """Analyze reading habits: timing, completion, frequency."""
    cards: list[InsightCard] = []

    # Books by completion status
    completed = [b for b in books if b.read_percent is not None and b.read_percent >= 95]
    in_progress = [b for b in books if b.read_percent is not None and 5 < b.read_percent < 95]
    not_started = [b for b in books if b.read_percent is not None and b.read_percent <= 5]

    if completed or in_progress:
        evidence = [
            EvidenceItem(label="Completed", value=str(len(completed))),
            EvidenceItem(label="In progress", value=str(len(in_progress))),
        ]
        if not_started:
            evidence.append(EvidenceItem(label="Not started", value=str(len(not_started))))

        total_tracked = len(completed) + len(in_progress) + len(not_started)
        completion_rate = len(completed) / total_tracked * 100 if total_tracked else 0

        cards.append(InsightCard(
            id=_card_id("reading-pattern-completion"),
            title="Completion Rate",
            category="Reading Patterns",
            summary=f"{_pct(completion_rate)} of your tracked books are completed ({len(completed)} of {total_tracked}).",
            body=(
                f"You have finished {len(completed)} books, with {len(in_progress)} still in progress"
                + (f" and {len(not_started)} not yet started" if not_started else "")
                + "."
            ),
            evidence=evidence,
            recommendation=(
                f"You have {len(in_progress)} books in progress. Consider finishing one before starting a new title."
                if len(in_progress) > 2 else None
            ),
            priority_score=0.55 + (0.15 if len(in_progress) > 3 else 0),
            related_books=[b.title for b in in_progress[:5]],
            source="computed",
        ))

    # Reading time patterns
    timed_books = [(b, b.time_spent_reading) for b in books if b.time_spent_reading and b.time_spent_reading > 0]
    if timed_books:
        timed_books.sort(key=lambda x: x[1], reverse=True)
        longest, longest_time = timed_books[0]
        total_time = sum(t for _, t in timed_books)

        evidence = [
            EvidenceItem(label="Longest reading session", value=f"{longest.title} ({_fmt_time(longest_time)})"),
            EvidenceItem(label="Total reading time", value=_fmt_time(total_time)),
            EvidenceItem(label="Books with time data", value=str(len(timed_books))),
        ]

        cards.append(InsightCard(
            id=_card_id("reading-pattern-time"),
            title="Reading Time Breakdown",
            category="Reading Patterns",
            summary=f"You spent the most time reading \"{longest.title}\" ({_fmt_time(longest_time)}).",
            body=(
                f"Across {len(timed_books)} books with time data, you have logged "
                f"{_fmt_time(total_time)} of total reading. "
                f"\"{longest.title}\" represents the largest investment at {_fmt_time(longest_time)}."
            ),
            evidence=evidence,
            priority_score=0.6,
            related_books=[b.title for b, _ in timed_books[:5]],
            source="computed",
        ))

    return cards


def _books_in_progress(books: list[Book]) -> list[InsightCard]:
    """Surface books that are partially read."""
    in_progress = [
        b for b in books
        if b.read_percent is not None and 5 < b.read_percent < 95
    ]
    if not in_progress:
        return []

    in_progress.sort(key=lambda b: b.read_percent or 0, reverse=True)

    evidence = [
        EvidenceItem(label=b.title, value=_pct(b.read_percent or 0))
        for b in in_progress[:8]
    ]

    almost_done = [b for b in in_progress if (b.read_percent or 0) > 70]
    rec = None
    if almost_done:
        rec = f"You are close to finishing \"{almost_done[0].title}\" ({_pct(almost_done[0].read_percent or 0)}). Consider completing it."

    return [InsightCard(
        id=_card_id("books-in-progress"),
        title=f"{len(in_progress)} Books in Progress",
        category="Books in Progress",
        summary=(
            f"You have {len(in_progress)} books partially read. "
            f"\"{in_progress[0].title}\" is furthest along at {_pct(in_progress[0].read_percent or 0)}."
        ),
        body=(
            "These books still have pages waiting for you. "
            "Returning to a partially-read book can be more rewarding than starting a new one."
        ),
        evidence=evidence,
        recommendation=rec,
        priority_score=0.5 + min(len(in_progress) * 0.05, 0.3),
        related_books=[b.title for b in in_progress[:5]],
        source="computed",
    )]


def _vocabulary_activity(books: list[Book], word_lookups: list | None = None) -> list[InsightCard]:
    """Insights about vocabulary lookups if data exists."""
    if not word_lookups:
        return []

    total = len(word_lookups)
    # Group by book
    book_counts: Counter[str] = Counter()
    word_counts: Counter[str] = Counter()
    for wl in word_lookups:
        book_title = getattr(wl, "book_title", None) or "Unknown"
        word = getattr(wl, "word", None) or getattr(wl, "text", None) or ""
        book_counts[book_title] += 1
        if word:
            word_counts[word.lower()] += 1

    evidence = [EvidenceItem(label="Total lookups", value=str(total))]
    if book_counts:
        top_book, top_count = book_counts.most_common(1)[0]
        evidence.append(EvidenceItem(label="Most looked-up book", value=f"{top_book} ({top_count})"))
    if word_counts:
        top_words = word_counts.most_common(5)
        for w, c in top_words:
            evidence.append(EvidenceItem(label=f'"{w}"', value=f"looked up {c} time{'s' if c != 1 else ''}"))

    return [InsightCard(
        id=_card_id("vocab-activity"),
        title=f"Vocabulary Activity: {total} Lookups",
        category="Vocabulary Activity",
        summary=f"You looked up {total} words across your reading sessions.",
        body=(
            f"Your vocabulary exploration spans {len(book_counts)} books. "
            + (f"\"{book_counts.most_common(1)[0][0]}\" triggered the most lookups." if book_counts else "")
        ),
        evidence=evidence,
        recommendation="Review your most-looked-up words to reinforce vocabulary retention.",
        priority_score=min(total / 50, 0.8),
        related_books=[b for b, _ in book_counts.most_common(5)],
        source="computed",
    )]


def _reading_momentum(books: list[Book]) -> list[InsightCard]:
    """Detect reading momentum -- recent activity vs. stale books."""
    cards: list[InsightCard] = []
    now = datetime.now()
    recent_cutoff = now - timedelta(days=30)
    stale_cutoff = now - timedelta(days=90)

    recent_books = []
    stale_books = []
    for b in books:
        if b.date_last_read:
            if b.date_last_read >= recent_cutoff:
                recent_books.append(b)
            elif b.date_last_read < stale_cutoff and b.annotations:
                stale_books.append(b)

    if recent_books:
        evidence = [
            EvidenceItem(label=b.title, value=b.date_last_read.strftime("%Y-%m-%d") if b.date_last_read else "")
            for b in sorted(recent_books, key=lambda b: b.date_last_read or datetime.min, reverse=True)[:5]
        ]
        cards.append(InsightCard(
            id=_card_id("momentum-recent"),
            title=f"Active Reading: {len(recent_books)} Books This Month",
            category="Reading Momentum",
            summary=f"You have been active with {len(recent_books)} books in the last 30 days.",
            body=(
                "Strong recent reading momentum. "
                f"You touched {len(recent_books)} titles in the past month."
            ),
            evidence=evidence,
            priority_score=0.65,
            related_books=[b.title for b in recent_books[:5]],
            source="computed",
        ))

    if stale_books:
        stale_books.sort(key=lambda b: len(b.annotations), reverse=True)
        evidence = [
            EvidenceItem(
                label=b.title,
                value=f"{len(b.annotations)} annotations, last read {b.date_last_read.strftime('%Y-%m-%d') if b.date_last_read else 'unknown'}",
            )
            for b in stale_books[:5]
        ]
        cards.append(InsightCard(
            id=_card_id("momentum-stale"),
            title=f"Forgotten Books: {len(stale_books)} Titles with Unreviewed Notes",
            category="Forgotten Insights",
            summary=(
                f"{len(stale_books)} annotated books have not been opened in over 90 days. "
                f"\"{stale_books[0].title}\" has {len(stale_books[0].annotations)} annotations waiting."
            ),
            body=(
                "These books have annotations you captured but may have forgotten about. "
                "Revisiting old highlights often surfaces ideas that feel fresh the second time around."
            ),
            evidence=evidence,
            recommendation=f"Start by revisiting \"{stale_books[0].title}\" -- it has the most unreviewed annotations.",
            priority_score=0.7,
            related_books=[b.title for b in stale_books[:5]],
            source="computed",
        ))

    return cards


def _deep_reading_signals(books: list[Book]) -> list[InsightCard]:
    """Identify books with strong deep-reading signals: high highlight density, note-to-highlight ratio."""
    cards: list[InsightCard] = []

    deep_reads: list[tuple[Book, float, int, int]] = []
    for b in books:
        hl = sum(1 for a in b.annotations if a.kind == "highlight")
        nt = sum(1 for a in b.annotations if a.kind == "note")
        if hl < 3:
            continue
        note_ratio = nt / hl if hl else 0
        chapters = len({a.chapter for a in b.annotations if a.chapter})
        density = hl / max(chapters, 1)
        score = note_ratio * 3 + density * 0.5 + (1.0 if hl >= 10 else 0)
        deep_reads.append((b, score, hl, nt))

    deep_reads.sort(key=lambda x: x[1], reverse=True)
    if not deep_reads:
        return []

    best, best_score, best_hl, best_nt = deep_reads[0]
    note_ratio = best_nt / best_hl if best_hl else 0

    evidence = [
        EvidenceItem(label="Highlights", value=str(best_hl)),
        EvidenceItem(label="Notes", value=str(best_nt)),
        EvidenceItem(label="Note-to-highlight ratio", value=f"{note_ratio:.0%}"),
    ]
    if best.time_spent_reading and best.time_spent_reading > 0:
        evidence.append(EvidenceItem(label="Time spent", value=_fmt_time(best.time_spent_reading)))

    author_part = f" by {best.author}" if best.author else ""
    cards.append(InsightCard(
        id=_card_id("deep-reading", best.id),
        title=f"Deepest Read: {best.title}",
        category="Deep Reading Signals",
        summary=(
            f"\"{best.title}\"{author_part} shows your strongest deep-reading engagement: "
            f"{best_hl} highlights and {best_nt} notes."
        ),
        body=(
            f"This book has a note-to-highlight ratio of {note_ratio:.0%}, "
            "suggesting you went beyond passive highlighting into active reflection. "
            "Books with high note ratios are where your best thinking lives."
        ),
        evidence=evidence,
        recommendation="Export and review your notes from this book for a personal knowledge summary.",
        priority_score=min(best_score / 8, 0.95),
        related_books=[best.title],
        source="computed",
    ))

    return cards


def _author_insights(books: list[Book]) -> list[InsightCard]:
    """Surface author-level patterns."""
    author_books: dict[str, list[Book]] = {}
    for b in books:
        if b.author:
            author_books.setdefault(b.author, []).append(b)

    multi_book_authors = {a: bs for a, bs in author_books.items() if len(bs) >= 2}
    if not multi_book_authors:
        return []

    # Most read author
    top_author = max(multi_book_authors, key=lambda a: sum(len(b.annotations) for b in multi_book_authors[a]))
    top_books = multi_book_authors[top_author]
    total_ann = sum(len(b.annotations) for b in top_books)

    evidence = [
        EvidenceItem(label=b.title, value=f"{len(b.annotations)} annotations")
        for b in sorted(top_books, key=lambda b: len(b.annotations), reverse=True)
    ]

    return [InsightCard(
        id=_card_id("author-insight", top_author),
        title=f"Favorite Author: {top_author}",
        category="Reading Patterns",
        summary=f"You have read {len(top_books)} books by {top_author} with {total_ann} total annotations.",
        body=(
            f"{top_author} is your most annotated author across multiple titles. "
            f"You captured {total_ann} annotations across {len(top_books)} books."
        ),
        evidence=evidence,
        recommendation=f"Look for more titles by {top_author}, or compare themes across their books.",
        priority_score=0.55 + min(len(top_books) * 0.05, 0.2),
        related_books=[b.title for b in top_books],
        source="computed",
    )]


def _rating_insights(books: list[Book]) -> list[InsightCard]:
    """Surface patterns from book ratings."""
    rated = [(b, b.rating) for b in books if b.rating and b.rating > 0]
    if len(rated) < 2:
        return []

    rated.sort(key=lambda x: x[1], reverse=True)
    avg_rating = sum(r for _, r in rated) / len(rated)
    top_rated = rated[0][0]

    evidence = [
        EvidenceItem(label="Average rating", value=f"{avg_rating:.1f} / 5"),
        EvidenceItem(label="Books rated", value=str(len(rated))),
        EvidenceItem(label="Top rated", value=f"{top_rated.title} ({rated[0][1]} / 5)"),
    ]

    return [InsightCard(
        id=_card_id("rating-insight"),
        title=f"Your Average Rating: {avg_rating:.1f} / 5",
        category="Reading Patterns",
        summary=(
            f"Across {len(rated)} rated books, your average is {avg_rating:.1f}/5. "
            f"\"{top_rated.title}\" is your top-rated read."
        ),
        body=(
            f"You have rated {len(rated)} books. "
            f"Your top-rated book is \"{top_rated.title}\" at {rated[0][1]}/5."
        ),
        evidence=evidence,
        priority_score=0.4,
        related_books=[b.title for b, _ in rated[:5]],
        source="computed",
    )]


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate(cards: list[InsightCard]) -> list[InsightCard]:
    """Remove near-duplicate insight cards.

    Two cards are considered duplicate if they share the same ``id`` or if
    their summaries overlap by more than 80% of words.
    """
    seen_ids: set[str] = set()
    seen_summaries: list[set[str]] = []
    unique: list[InsightCard] = []

    for card in cards:
        if card.id in seen_ids:
            continue
        words = set(card.summary.lower().split())
        is_dup = False
        for prev_words in seen_summaries:
            if not words or not prev_words:
                continue
            overlap = len(words & prev_words) / min(len(words), len(prev_words))
            if overlap > 0.80:
                is_dup = True
                break
        if is_dup:
            continue
        seen_ids.add(card.id)
        seen_summaries.append(words)
        unique.append(card)

    return unique


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_cards(cards: list[InsightCard]) -> list[InsightCard]:
    """Sort cards by priority score descending, then by category grouping.

    Scoring factors (already encoded in priority_score during generation):
    - Amount of supporting evidence
    - Number of related books
    - Presence of a recommendation
    - Category importance

    This function applies a small boost based on evidence count and
    recommendation presence, then sorts.
    """
    for card in cards:
        # Boost for evidence richness
        card.priority_score += min(len(card.evidence) * 0.02, 0.1)
        # Boost for actionability
        if card.recommendation:
            card.priority_score += 0.05
        # Boost for multi-book relevance
        if len(card.related_books) >= 3:
            card.priority_score += 0.05

    cards.sort(key=lambda c: c.priority_score, reverse=True)
    return cards


# ---------------------------------------------------------------------------
# Top-level summary takeaways
# ---------------------------------------------------------------------------


def extract_takeaways(cards: list[InsightCard], n: int = 5) -> list[str]:
    """Pull the top *n* one-line takeaways from the ranked feed."""
    takeaways: list[str] = []
    seen_cats: set[str] = set()
    for card in cards:
        if card.category in seen_cats:
            continue
        takeaways.append(card.summary)
        seen_cats.add(card.category)
        if len(takeaways) >= n:
            break
    return takeaways


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_feed(
    books: list[Book],
    *,
    word_lookups: list | None = None,
    categories: list[str] | None = None,
    book_filter: str | None = None,
    min_priority: float = 0.0,
) -> list[InsightCard]:
    """Build the full Insight Feed from library data.

    Parameters
    ----------
    books:
        All loaded books (with annotations).
    word_lookups:
        Optional vocabulary lookup data.
    categories:
        If provided, only return insights matching these categories.
    book_filter:
        If provided, only return insights related to this book title.
    min_priority:
        Minimum priority score threshold (0.0-1.0).
    """
    all_cards: list[InsightCard] = []

    # Run all generators
    generators = [
        _library_overview,
        _most_engaged_books,
        _highlight_behavior,
        _reading_patterns,
        _books_in_progress,
        _reading_momentum,
        _deep_reading_signals,
        _author_insights,
        _rating_insights,
    ]

    for gen in generators:
        try:
            all_cards.extend(gen(books))
        except Exception:
            logger.warning("Insight generator %s failed", gen.__name__, exc_info=True)

    # Vocabulary needs extra data
    try:
        all_cards.extend(_vocabulary_activity(books, word_lookups))
    except Exception:
        logger.warning("Vocabulary insight generator failed", exc_info=True)

    # Deduplicate, rank, filter
    all_cards = deduplicate(all_cards)
    all_cards = rank_cards(all_cards)

    if categories:
        cat_set = {c.lower() for c in categories}
        all_cards = [c for c in all_cards if c.category.lower() in cat_set]

    if book_filter:
        all_cards = [c for c in all_cards if book_filter in c.related_books]

    if min_priority > 0:
        all_cards = [c for c in all_cards if c.priority_score >= min_priority]

    return all_cards


def _score_overview(books: list[Book]) -> float:
    """Priority score for the library overview card."""
    annotated = sum(1 for b in books if b.annotations)
    return min(0.4 + annotated * 0.02, 0.7)
