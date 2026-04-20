"""Hero insight engine — generates the headline insight shown at the top
of the Overview tab.

The engine inspects a user's library and selects the single most accurate,
personal pattern that describes their reading behavior. Logic is fully
deterministic — no templates, no LLM calls. Each pattern carries a
priority score; when several patterns match, the highest-priority one wins.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from models.book import Book
from models.vocabulary import WordLookup
from services.stats import LibraryStats


@dataclass
class HeroInsight:
    """A single headline insight for the Overview tab."""

    pattern: str  # machine id: "deep_reader", "pattern_seeker", etc.
    title: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    recommendation: str = ""
    priority: float = 0.0
    is_fallback: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_hero_insight(
    stats: LibraryStats,
    books: list[Book],
    word_lookups: Iterable[WordLookup] | None = None,
    longest_streak: int = 0,
    total_reading_time_sec: int | None = None,
) -> HeroInsight:
    """Return the strongest hero insight that matches the user's data.

    Patterns are evaluated independently, then the highest-priority match
    wins. If the library is too sparse to produce a meaningful insight, a
    softer fallback is returned.
    """
    word_lookups = list(word_lookups or [])

    # Sparse-data fallback: not enough signal to interpret behavior.
    if stats.total_annotations < 10 or stats.total_books == 0:
        return _fallback_insight(stats)

    candidates: list[HeroInsight] = []
    for builder in (
        _deep_reader,
        _pattern_seeker,
        _selective_thinker,
        _friction_reader,
        _focused_deep_dive,
    ):
        result = builder(stats, books, word_lookups, longest_streak, total_reading_time_sec)
        if result is not None:
            candidates.append(result)

    if not candidates:
        return _fallback_insight(stats)

    candidates.sort(key=lambda c: c.priority, reverse=True)
    return candidates[0]


# ---------------------------------------------------------------------------
# Pattern builders
# ---------------------------------------------------------------------------


def _deep_reader(
    stats: LibraryStats,
    books: list[Book],
    word_lookups: list[WordLookup],
    longest_streak: int,
    reading_time_sec: int | None,
) -> HeroInsight | None:
    if stats.total_highlights == 0:
        return None
    ratio = stats.total_notes / max(stats.total_highlights, 1)
    if ratio < 0.20 and stats.total_notes < 40:
        return None

    priority = 0.70 + min(ratio, 0.5) * 0.4  # up to ~0.90
    if stats.total_notes >= 80:
        priority += 0.05

    evidence = [
        f"{stats.total_notes} notes across {stats.total_books} book{'s' if stats.total_books != 1 else ''}",
        f"{int(round(ratio * 100))}% note-to-highlight ratio",
    ]
    evidence.extend(_shared_evidence(stats, longest_streak, reading_time_sec))

    top_note_book = _book_with_most_notes(books)
    rec = (
        f'Revisit your notes on "{top_note_book}" — that\'s where your best thinking lives.'
        if top_note_book
        else "Revisit your most-noted book — that's where your best thinking lives."
    )

    return HeroInsight(
        pattern="deep_reader",
        title="You read to understand, not just highlight.",
        summary="You consistently take notes when ideas get complex — your reading isn't passive.",
        evidence=evidence[:4],
        recommendation=rec,
        priority=round(priority, 3),
    )


def _pattern_seeker(
    stats: LibraryStats,
    books: list[Book],
    word_lookups: list[WordLookup],
    longest_streak: int,
    reading_time_sec: int | None,
) -> HeroInsight | None:
    threshold = 15
    qualifying = [(t, c) for t, c in stats.books_by_highlight_count if c >= threshold]
    if len(qualifying) < 3:
        return None

    priority = 0.65 + min(len(qualifying), 8) * 0.02  # up to 0.81
    sample_titles = [t for t, _ in qualifying[:3]]

    evidence = [
        f"{len(qualifying)} books with {threshold}+ highlights each",
        f"Top three: {', '.join(sample_titles)}",
    ]
    evidence.extend(_shared_evidence(stats, longest_streak, reading_time_sec))

    return HeroInsight(
        pattern="pattern_seeker",
        title="You're tracking ideas across books.",
        summary="Your highlights show recurring attention to similar concepts — you read like a researcher, not a tourist.",
        evidence=evidence[:4],
        recommendation="Export these highlights and look for the threads that repeat.",
        priority=round(priority, 3),
    )


def _selective_thinker(
    stats: LibraryStats,
    books: list[Book],
    word_lookups: list[WordLookup],
    longest_streak: int,
    reading_time_sec: int | None,
) -> HeroInsight | None:
    if stats.total_highlights < 50:
        return None
    ratio = stats.total_notes / max(stats.total_highlights, 1)
    if ratio >= 0.05:
        return None

    priority = 0.70 + min(stats.total_highlights, 500) / 5000  # up to 0.80

    evidence = [
        f"{stats.total_highlights} highlights, {stats.total_notes} notes",
        f"{int(round(ratio * 100))}% note-to-highlight ratio",
    ]
    evidence.extend(_shared_evidence(stats, longest_streak, reading_time_sec))

    return HeroInsight(
        pattern="selective_thinker",
        title="You highlight broadly, reflect selectively.",
        summary="You mark a lot, but only write when something really stands out — your notes carry weight.",
        evidence=evidence[:4],
        recommendation="Pull your handful of notes into one place — they're the signal in the noise.",
        priority=round(priority, 3),
    )


def _friction_reader(
    stats: LibraryStats,
    books: list[Book],
    word_lookups: list[WordLookup],
    longest_streak: int,
    reading_time_sec: int | None,
) -> HeroInsight | None:
    lookup_count = len(word_lookups)
    if lookup_count < 30:
        return None

    priority = 0.72 + min(lookup_count, 300) / 3000  # up to 0.82

    evidence = [
        f"{lookup_count} vocabulary lookups",
    ]
    if stats.total_highlights:
        evidence.append(
            f"{stats.total_highlights} highlights across {stats.total_books} book{'s' if stats.total_books != 1 else ''}"
        )
    evidence.extend(_shared_evidence(stats, longest_streak, reading_time_sec))

    return HeroInsight(
        pattern="friction_reader",
        title="You lean into difficulty.",
        summary="You slow down and look things up when the material gets dense — that's how vocabulary actually grows.",
        evidence=evidence[:4],
        recommendation="Open your vocabulary view and turn the words you've looked up into a study list.",
        priority=round(priority, 3),
    )


def _focused_deep_dive(
    stats: LibraryStats,
    books: list[Book],
    word_lookups: list[WordLookup],
    longest_streak: int,
    reading_time_sec: int | None,
) -> HeroInsight | None:
    if not stats.books_by_highlight_count or stats.total_highlights < 30:
        return None
    top_title, top_count = stats.books_by_highlight_count[0]
    share = top_count / max(stats.total_highlights, 1)
    if share < 0.40:
        return None

    # Confirm there's also reflection happening on that book.
    notes_on_top = _notes_for_book(books, top_title)
    if notes_on_top < 5 and stats.total_notes >= 10:
        return None

    priority = 0.78 + min(share, 0.95) * 0.15  # up to ~0.92

    evidence = [
        f'{top_count} highlights in "{top_title}"',
        f"{int(round(share * 100))}% of all your highlights came from this one book",
    ]
    if notes_on_top:
        evidence.append(f"{notes_on_top} notes on this title")
    evidence.extend(_shared_evidence(stats, longest_streak, reading_time_sec))

    return HeroInsight(
        pattern="focused_deep_dive",
        title="One book captured your attention.",
        summary=f'"{top_title}" pulled in most of your energy — that kind of focus is rare.',
        evidence=evidence[:4],
        recommendation="This is a strong candidate for a personal summary — your future self will thank you.",
        priority=round(priority, 3),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _shared_evidence(
    stats: LibraryStats,
    longest_streak: int,
    reading_time_sec: int | None,
) -> list[str]:
    """Generic supporting bullets that apply to most patterns."""
    items: list[str] = []
    if reading_time_sec and reading_time_sec > 0:
        items.append(f"{_format_reading_time(reading_time_sec)} of reading time")
    if longest_streak >= 3:
        items.append(f"{longest_streak}-day annotation streak")
    return items


def _format_reading_time(seconds: int) -> str:
    if seconds <= 0:
        return "0m"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem_minutes = minutes - hours * 60
    if hours < 24:
        if rem_minutes:
            return f"{hours}h {rem_minutes}m"
        return f"{hours}h"
    days = hours // 24
    rem_hours = hours - days * 24
    if rem_hours:
        return f"{days}d {rem_hours}h"
    return f"{days}d"


def _book_with_most_notes(books: list[Book]) -> str | None:
    best_title: str | None = None
    best_count = 0
    for book in books:
        notes = sum(1 for a in book.annotations if a.kind == "note")
        if notes > best_count:
            best_count = notes
            best_title = book.title
    return best_title if best_count > 0 else None


def _notes_for_book(books: list[Book], title: str) -> int:
    for book in books:
        if book.title == title:
            return sum(1 for a in book.annotations if a.kind == "note")
    return 0


def _fallback_insight(stats: LibraryStats) -> HeroInsight:
    evidence: list[str] = []
    if stats.total_books:
        evidence.append(f"{stats.total_books} book{'s' if stats.total_books != 1 else ''} in your library")
    if stats.total_annotations:
        evidence.append(f"{stats.total_annotations} annotation{'s' if stats.total_annotations != 1 else ''} so far")

    return HeroInsight(
        pattern="getting_started",
        title="Read a bit more to unlock deeper insights.",
        summary="There's not quite enough data yet to spot a clear pattern — keep highlighting and noting, and KoNotes will start to read the shape of your reading.",
        evidence=evidence,
        recommendation="Come back after a few more reading sessions to see your pattern emerge.",
        priority=0.1,
        is_fallback=True,
    )
