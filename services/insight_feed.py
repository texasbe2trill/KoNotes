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
    """Top-level library stats — your reading story."""
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

    # Build a warm, narrative body
    body_parts = []
    if len(books) == 1:
        body_parts.append(
            f"You've loaded one book so far — and already captured "
            f"{total_hl} highlights and {total_notes} notes. Every reader starts somewhere."
        )
    else:
        body_parts.append(
            f"You've built a personal library of {len(books)} books, "
            f"marking {total_hl} passages and writing {total_notes} notes along the way. "
            f"That's {len(annotated)} books where something caught your attention."
        )
    if avg_hl > 0:
        body_parts.append(
            f"On average, you save about {avg_hl} highlights per book — "
            f"that's your natural annotation rhythm."
        )
    if total_time > 0:
        body_parts.append(
            f"You've invested {_fmt_time(total_time)} in reading. "
            f"That's real time spent with ideas that matter to you."
        )

    return [InsightCard(
        id=_card_id("library-overview"),
        title="Your Reading Story So Far",
        category="Library Overview",
        summary=(
            f"{len(annotated)} books carry your marginalia — "
            f"that's a personal library of ideas you've been building."
        ),
        body="\n\n".join(body_parts),
        evidence=evidence,
        priority_score=_score_overview(books),
        related_books=[b.title for b in annotated[:5]],
        source="computed",
    )]


def _most_engaged_books(books: list[Book]) -> list[InsightCard]:
    """Identify the books that captivated you most."""
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
        title=f"The Book That Captivated You: {best.title}",
        category="Most Engaged Books",
        summary=(
            f"\"{best.title}\"{author_part} kept pulling you in — "
            f"it left a bigger mark on you than any other book in your library."
        ),
        body=(
            f"Something about \"{best.title}\"{author_part} kept pulling you in. "
            f"You captured {hl_count} highlights and wrote {nt_count} notes"
            + (f", spending {_fmt_time(best.time_spent_reading)} reading" if best.time_spent_reading else "")
            + ". That kind of engagement usually means a book challenged you, surprised you, or confirmed something you already believed."
        ),
        evidence=evidence,
        recommendation=f"Revisit your notes from \"{best.title}\" — you might find ideas worth acting on.",
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
            title="Other Books That Grabbed You",
            category="Most Engaged Books",
            summary=(
                f"{', '.join(runner_titles[:3])} also left a mark — "
                f"you kept coming back to highlight and annotate."
            ),
            body=(
                "These aren't your most-annotated book, but they still earned "
                "serious attention. Each one has a substantial number of annotations "
                "relative to your library."
            ),
            evidence=runner_evidence,
            priority_score=min(top[1][1] / 15, 0.8),
            related_books=runner_titles,
            source="computed",
        ))

    return cards


def _highlight_behavior(books: list[Book]) -> list[InsightCard]:
    """Analyze highlighting patterns — how the reader annotates."""
    cards: list[InsightCard] = []
    all_books_hl: list[tuple[str, int]] = []
    chapter_counts: Counter[tuple[str, str]] = Counter()
    total_hl = 0

    for b in books:
        hl_list = [a for a in b.annotations if a.kind == "highlight"]
        hl_count = len(hl_list)
        total_hl += hl_count
        if hl_count > 0:
            all_books_hl.append((b.title, hl_count))
        for a in hl_list:
            if a.chapter:
                chapter_counts[(b.title, a.chapter)] += 1

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
            f"come from \"{top_title}\". When a book clicks, you go all in."
        )
        rec = "Try spreading your annotations across more books — you might find unexpected connections."
    else:
        summary = (
            f"Your highlights are spread across {len(all_books_hl)} books — "
            f"you're the kind of reader who finds something worth saving wherever you look."
        )
        rec = None

    cards.append(InsightCard(
        id=_card_id("hl-behavior-dist"),
        title="How You Annotate",
        category="Highlight Behavior",
        summary=summary,
        body=(
            f"You've saved {total_hl} highlights across {len(all_books_hl)} books. "
            + (
                f"\"{top_title}\" dominates with {_pct(concentration * 100)} of them — "
                f"the rest of your library shares the remaining highlights."
                if concentration > 0.5
                else f"\"{top_title}\" leads with {top_count}, but no single book dominates — "
                f"your curiosity is broad."
            )
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
            EvidenceItem(label=f"{book}: {ch}", value=f"{cnt} highlights")
            for (book, ch), cnt in top_chapters
        ]
        top_book, top_ch = top_chapters[0][0]
        top_ch_label = f"{top_ch}" if len({b for (b, _), _ in top_chapters[:1]}) == 1 else f"{top_ch} ({top_book})"
        cards.append(InsightCard(
            id=_card_id("hl-behavior-chapters"),
            title="Chapters That Made You Stop and Think",
            category="Highlight Behavior",
            summary=f"\"{top_ch}\" kept stopping you in your tracks — something in that chapter demanded attention.",
            body=(
                "These are the chapters where you paused most often to mark a passage. "
                "That's usually a sign the content was challenging, surprising, or directly useful to you."
            ),
            evidence=ch_evidence,
            recommendation=f"Go back to \"{top_ch}\" in \"{top_book}\" — your highlights might be waiting for a second look.",
            priority_score=0.5,
            related_books=[top_book],
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

        if completion_rate >= 80:
            tone = "You finish what you start — that's rare."
        elif completion_rate >= 50:
            tone = "A solid finish rate — you see most books through."
        elif len(in_progress) > 3:
            tone = "You've got a lot of plates spinning. No judgment — some readers thrive that way."
        else:
            tone = "Every reader has their rhythm."

        cards.append(InsightCard(
            id=_card_id("reading-pattern-completion"),
            title="Your Completion Rate",
            category="Reading Patterns",
            summary=tone,
            body=(
                f"You have completed {len(completed)} books"
                + (f", with {len(in_progress)} still in progress" if in_progress else "")
                + (f" and {len(not_started)} not yet started" if not_started else "")
                + "."
            ),
            evidence=evidence,
            recommendation=(
                f"You have {len(in_progress)} books mid-read. Finishing \"{in_progress[0].title}\" "
                f"({_pct(in_progress[0].read_percent or 0)}) might feel more satisfying than starting something new."
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
            EvidenceItem(label="Longest read", value=f"{longest.title} ({_fmt_time(longest_time)})"),
            EvidenceItem(label="Total reading time", value=_fmt_time(total_time)),
            EvidenceItem(label="Books with time data", value=str(len(timed_books))),
        ]

        cards.append(InsightCard(
            id=_card_id("reading-pattern-time"),
            title="Where Your Time Went",
            category="Reading Patterns",
            summary=(
                f"\"{longest.title}\" is where you spent the most time — "
                f"that kind of sustained attention usually means a book got under your skin."
            ),
            body=(
                f"Across {len(timed_books)} books, you've logged {_fmt_time(total_time)} of reading. "
                f"\"{longest.title}\" was your biggest time investment at {_fmt_time(longest_time)}. "
                f"Time spent reading is time spent thinking."
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
        rec = (
            f"You're {_pct(almost_done[0].read_percent or 0)} through "
            f"\"{almost_done[0].title}\" — so close. That last stretch often has the best payoff."
        )

    if len(in_progress) == 1:
        summary = (
            f"You have one book in progress: \"{in_progress[0].title}\" "
            f"at {_pct(in_progress[0].read_percent or 0)}."
        )
    else:
        summary = (
            f"{len(in_progress)} books are waiting for you to come back. "
            f"\"{in_progress[0].title}\" is closest to the finish line at "
            f"{_pct(in_progress[0].read_percent or 0)}."
        )

    return [InsightCard(
        id=_card_id("books-in-progress"),
        title=f"Unfinished Stories ({len(in_progress)})",
        category="Books in Progress",
        summary=summary,
        body=(
            "Every book here has pages that still have something to offer. "
            "Sometimes returning to a half-read book hits different — "
            "you bring new perspective to old passages."
        ),
        evidence=evidence,
        recommendation=rec,
        priority_score=0.5 + min(len(in_progress) * 0.05, 0.3),
        related_books=[b.title for b in in_progress[:5]],
        source="computed",
    )]


def _vocabulary_activity(books: list[Book], word_lookups: list | None = None) -> list[InsightCard]:
    """Insights about vocabulary lookups — words that caught your eye."""
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
        evidence.append(EvidenceItem(label="Most curious book", value=f"{top_book} ({top_count})"))
    if word_counts:
        top_words = word_counts.most_common(5)
        for w, c in top_words:
            evidence.append(EvidenceItem(label=f'"{w}"', value=f"looked up {c} time{'s' if c != 1 else ''}"))

    # Surface the actual top words in the summary for personality
    unique = len(word_counts)
    if word_counts:
        word_samples = [w for w, _ in word_counts.most_common(3)]
        word_str = ", ".join(f'"{w}"' for w in word_samples)
        summary = (
            f"You looked up {unique} unique words while reading — including {word_str}. "
            f"Curiosity like that is a sign of an active mind."
        )
    else:
        summary = f"You looked up {unique} words across your reading sessions."

    return [InsightCard(
        id=_card_id("vocab-activity"),
        title=f"Words That Caught Your Eye",
        category="Vocabulary Activity",
        summary=summary,
        body=(
            f"Your vocabulary exploration spans {len(book_counts)} books. "
            + (f"\"{book_counts.most_common(1)[0][0]}\" made you reach for the dictionary the most — "
               f"probably because it pushed you into unfamiliar territory." if book_counts else "")
        ),
        evidence=evidence,
        recommendation="Try using your most-looked-up words in conversation or writing — that's how they stick.",
        priority_score=min(total / 50, 0.8),
        related_books=[b for b, _ in book_counts.most_common(5)],
        source="computed",
    )]


def _reading_momentum(books: list[Book]) -> list[InsightCard]:
    """Detect reading momentum — recent vs. forgotten books."""
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
        if len(recent_books) >= 3:
            summary = (
                f"You've been active with {len(recent_books)} books this month. "
                f"You're in a great reading groove right now."
            )
        else:
            summary = (
                f"You picked up a book in the last 30 days — keep that momentum going."
            )
        cards.append(InsightCard(
            id=_card_id("momentum-recent"),
            title=f"You're on a Roll",
            category="Reading Momentum",
            summary=summary,
            body=(
                f"Reading momentum matters. You've engaged with "
                f"{len(recent_books)} title{'s' if len(recent_books) != 1 else ''} recently, "
                f"which means ideas are flowing."
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
            title=f"Hidden Gems: {len(stale_books)} Forgotten Books",
            category="Forgotten Insights",
            summary=(
                f"You have annotated books gathering dust — "
                f"\"{stale_books[0].title}\" has ideas you invested time in "
                f"but haven't revisited in months."
            ),
            body=(
                "These books have highlights and notes you invested time in — "
                "but you might have forgotten what you captured. "
                "Re-reading old annotations often surfaces ideas that feel brand new. "
                "Your past self left you breadcrumbs."
            ),
            evidence=evidence,
            recommendation=(
                f"Start with \"{stale_books[0].title}\" — it has the most unreviewed annotations. "
                f"Even 5 minutes of review can spark something."
            ),
            priority_score=0.7,
            related_books=[b.title for b in stale_books[:5]],
            source="computed",
        ))

    return cards


def _deep_reading_signals(books: list[Book]) -> list[InsightCard]:
    """Identify books with strong deep-reading signals."""
    cards: list[InsightCard] = []

    deep_reads: list[tuple[Book, float, int, int]] = []
    for b in books:
        hl = sum(1 for a in b.annotations if a.kind == "highlight")
        nt = sum(1 for a in b.annotations if a.kind == "note")
        if hl < 3:
            continue
        note_ratio = nt / hl if hl else 0
        chapters = len({a.chapter for a in b.annotations if a.chapter})
        density = min(hl / max(chapters, 1), 10)
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
    if note_ratio >= 0.3:
        depth_desc = (
            "With a note-to-highlight ratio of {ratio}, you weren't just reading — "
            "you were thinking out loud on the page. "
            "That's where your best ideas tend to live."
        ).format(ratio=f"{note_ratio:.0%}")
    else:
        depth_desc = (
            "You captured {hl} highlights across this book, "
            "showing sustained, careful attention. "
            "That kind of focus usually means the ideas resonated with you personally."
        ).format(hl=best_hl)

    cards.append(InsightCard(
        id=_card_id("deep-reading", best.id),
        title=f"Where Your Best Thinking Lives: {best.title}",
        category="Deep Reading Signals",
        summary=(
            f"\"{best.title}\"{author_part} is where you did your deepest thinking — "
            f"not just reading, but genuinely wrestling with the ideas."
        ),
        body=depth_desc,
        evidence=evidence,
        recommendation=(
            f"Your notes from \"{best.title}\" are worth exporting — "
            f"they're a personal knowledge summary in your own words."
        ),
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
        title=f"An Author Who Speaks to You: {top_author}",
        category="Reading Patterns",
        summary=(
            f"You keep coming back to {top_author} — "
            f"{len(top_books)} books deep. There's clearly something that resonates."
        ),
        body=(
            f"{top_author} is your most annotated author across multiple titles. "
            f"When an author shows up repeatedly in someone's library, it usually means "
            f"their ideas align with how you see the world — or challenge it in the right way."
        ),
        evidence=evidence,
        recommendation=f"Compare your highlights across {top_author}'s books — you might find a thread that connects them.",
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

    if avg_rating >= 4.0:
        tone = "You have high standards — and your library meets them."
    elif avg_rating >= 3.0:
        tone = "You rate honestly — not every book earns a 5."
    else:
        tone = "You're a critical reader. That's a strength."

    return [InsightCard(
        id=_card_id("rating-insight"),
        title=f"Your Taste in Books",
        category="Reading Patterns",
        summary=(
            f"Across {len(rated)} rated books, your average is {avg_rating:.1f}/5. {tone}"
        ),
        body=(
            f"\"{top_rated.title}\" earned your highest rating. "
            f"Every rating is a data point about what kind of writing moves you."
        ),
        evidence=evidence,
        priority_score=0.4,
        related_books=[b.title for b, _ in rated[:5]],
        source="computed",
    )]


def _vocabulary_friction(books: list[Book], word_lookups: list | None = None) -> list[InsightCard]:
    """Identify books where vocabulary lookups spiked — cognitive friction zones."""
    if not word_lookups:
        return []

    book_lookup_counts: Counter[str] = Counter()
    for wl in word_lookups:
        book_title = getattr(wl, "book_title", None) or "Unknown"
        book_lookup_counts[book_title] += 1

    if len(book_lookup_counts) < 2:
        return []

    avg = sum(book_lookup_counts.values()) / len(book_lookup_counts)
    friction_books = [
        (title, count) for title, count in book_lookup_counts.most_common()
        if count >= avg * 1.5 and count >= 5
    ]
    if not friction_books:
        return []

    top_title, top_count = friction_books[0]
    evidence = [
        EvidenceItem(label=t, value=f"{c} lookups") for t, c in friction_books[:5]
    ]
    evidence.append(EvidenceItem(label="Average per book", value=f"{avg:.1f}"))

    return [InsightCard(
        id=_card_id("vocab-friction"),
        title=f"Where Reading Got Harder: {top_title}",
        category="Vocabulary Activity",
        summary=(
            f"\"{top_title}\" pushed your vocabulary harder than any other book — "
            f"that's a sign it stretched how you think, not just what you read."
        ),
        body=(
            "Books that force you to slow down and look up words are often the ones "
            "that expand how you think. Vocabulary friction is a signal of intellectual "
            "growth, not confusion."
        ),
        evidence=evidence,
        recommendation=(
            f"Your vocabulary lookups in \"{top_title}\" suggest it stretched your "
            f"language — revisit those passages with fresh eyes."
        ),
        priority_score=0.65,
        related_books=[t for t, _ in friction_books[:5]],
        source="computed",
    )]


def _passive_vs_active(books: list[Book]) -> list[InsightCard]:
    """Differentiate passive highlighting from active note-taking."""
    cards: list[InsightCard] = []

    active_books: list[tuple[Book, float, int, int]] = []
    passive_books: list[tuple[Book, int]] = []

    for b in books:
        hl = sum(1 for a in b.annotations if a.kind == "highlight")
        nt = sum(1 for a in b.annotations if a.kind == "note")
        if hl < 3:
            continue
        ratio = nt / hl if hl else 0
        if ratio >= 0.2 and nt >= 2:
            active_books.append((b, ratio, hl, nt))
        elif nt == 0 and hl >= 5:
            passive_books.append((b, hl))

    if not active_books and not passive_books:
        return []

    if active_books:
        active_books.sort(key=lambda x: x[1], reverse=True)
        best, best_ratio, best_hl, best_nt = active_books[0]
        evidence = [
            EvidenceItem(label=b.title, value=f"{nt} notes / {hl} highlights ({r:.0%})")
            for b, r, hl, nt in active_books[:5]
        ]
        cards.append(InsightCard(
            id=_card_id("active-reading"),
            title="Books Where You Thought Out Loud",
            category="Deep Reading Signals",
            summary=(
                f"In \"{best.title}\", {best_ratio:.0%} of your annotations are notes — "
                f"you weren't just saving quotes, you were building on the ideas."
            ),
            body=(
                "Active reading — writing notes alongside highlights — is where "
                "understanding deepens. These books drew genuine reflection from you, "
                "not just passive marking."
            ),
            evidence=evidence,
            recommendation=(
                f"Your notes in \"{best.title}\" are personal commentary worth "
                f"revisiting — they capture how you processed the ideas."
            ),
            priority_score=0.7,
            related_books=[b.title for b, *_ in active_books[:5]],
            source="computed",
        ))

    if passive_books and len(passive_books) >= 2:
        passive_books.sort(key=lambda x: x[1], reverse=True)
        evidence = [
            EvidenceItem(label=b.title, value=f"{hl} highlights, 0 notes")
            for b, hl in passive_books[:5]
        ]
        cards.append(InsightCard(
            id=_card_id("passive-reading"),
            title="Books You Highlighted But Didn't Reflect On",
            category="Highlight Behavior",
            summary=(
                f"Some of your books are full of highlights but no notes — "
                f"you saved the words but didn't capture why they mattered."
            ),
            body=(
                "Highlighting without notes isn't bad — but adding even one sentence "
                "about why a passage stood out turns a bookmark into a thinking tool. "
                "These books might benefit from a second pass with a note-taking mindset."
            ),
            evidence=evidence,
            recommendation=(
                f"Pick \"{passive_books[0][0].title}\" and add one note per highlight. "
                f"Future-you will thank present-you."
            ),
            priority_score=0.55,
            related_books=[b.title for b, _ in passive_books[:5]],
            source="computed",
        ))

    return cards


def _export_worthy(books: list[Book]) -> list[InsightCard]:
    """Recommend books whose annotations are most worth exporting and reviewing."""
    candidates: list[tuple[Book, float]] = []

    for b in books:
        hl = sum(1 for a in b.annotations if a.kind == "highlight")
        nt = sum(1 for a in b.annotations if a.kind == "note")
        if hl < 3:
            continue
        chapters = len({a.chapter for a in b.annotations if a.chapter})
        # Score: annotation density, note ratio, chapter spread
        score = (
            hl * 0.5
            + nt * 2.0
            + chapters * 1.5
            + (1.0 if (b.read_percent or 0) >= 90 else 0)
        )
        candidates.append((b, score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    if not candidates:
        return []

    top = candidates[:5]
    best = top[0][0]
    hl_count = sum(1 for a in best.annotations if a.kind == "highlight")
    nt_count = sum(1 for a in best.annotations if a.kind == "note")
    ch_count = len({a.chapter for a in best.annotations if a.chapter})

    evidence = [
        EvidenceItem(label=b.title, value=f"{len(b.annotations)} annotations across {len({a.chapter for a in b.annotations if a.chapter})} chapters")
        for b, _ in top
    ]

    return [InsightCard(
        id=_card_id("export-worthy"),
        title="Books Worth Exporting Next",
        category="Most Engaged Books",
        summary=(
            f"You left the most thoughtful trail through \"{best.title}\" — "
            f"{ch_count} chapters of highlights and notes worth keeping."
        ),
        body=(
            "The best books to export are the ones where you invested the most thought "
            "across the widest range of chapters. These annotations form a personal "
            "knowledge summary that's worth keeping outside your Kobo."
        ),
        evidence=evidence,
        recommendation=(
            f"Export \"{best.title}\" — your annotations already read like a personal reference guide."
        ),
        priority_score=0.6,
        related_books=[b.title for b, _ in top],
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
    - Share-worthiness (interpretation > raw stats)

    This function applies boosts based on evidence count, actionability,
    multi-book relevance, and content depth, then sorts.
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
        # Boost for substantial body (interpretation, not just stats)
        if len(card.body) > 100:
            card.priority_score += 0.03

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
        _passive_vs_active,
        _export_worthy,
        _author_insights,
        _rating_insights,
    ]

    for gen in generators:
        try:
            all_cards.extend(gen(books))
        except Exception:
            logger.warning("Insight generator %s failed", gen.__name__, exc_info=True)

    # Vocabulary generators need extra data
    for vocab_gen in [_vocabulary_activity, _vocabulary_friction]:
        try:
            all_cards.extend(vocab_gen(books, word_lookups))
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
