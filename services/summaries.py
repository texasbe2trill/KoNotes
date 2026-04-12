"""Smart summary generation: template-based + optional LLM summaries per book."""
from __future__ import annotations

import logging
from collections import Counter

from models.book import Book
from models.insight import BookSummary, ThemeCluster

logger = logging.getLogger(__name__)


def generate_template_summary(
    book: Book,
    themes: list[ThemeCluster] | None = None,
) -> BookSummary:
    """Generate a structured text summary from annotation statistics."""
    highlights = [a for a in book.annotations if a.kind == "highlight"]
    notes = [a for a in book.annotations if a.kind == "note"]

    chapters = sorted({a.chapter for a in book.annotations if a.chapter})
    chapter_count = len(chapters)

    # Build summary paragraphs (separated by double newline for rendering)
    paragraphs: list[str] = []

    # Opening paragraph: overview
    author_part = f" by {book.author}" if book.author else ""
    opening = (
        f"From {book.title}{author_part}, you captured "
        f"{len(highlights)} highlight{'s' if len(highlights) != 1 else ''}"
        f"{f' and {len(notes)} note{chr(115) if len(notes) != 1 else chr(0)[0:0]}' if notes else ''}"
        f" across {chapter_count} chapter{'s' if chapter_count != 1 else ''}."
    )
    paragraphs.append(opening)

    # Themes paragraph
    if themes:
        theme_texts = [t.representative_text[:80] for t in themes[:3]]
        theme_line = (
            f"Key themes include: "
            f"{'; '.join(f'\"{t}...\"' if len(t) >= 80 else f'\"{t}\"' for t in theme_texts)}."
        )
        paragraphs.append(theme_line)

    # Reading engagement paragraph
    engagement_parts: list[str] = []

    if chapters:
        chapter_counter: Counter[str] = Counter()
        for a in book.annotations:
            if a.chapter:
                chapter_counter[a.chapter] += 1
        if chapter_counter:
            top_chapter, top_count = chapter_counter.most_common(1)[0]
            engagement_parts.append(
                f"Your most annotated chapter was \"{top_chapter}\" "
                f"with {top_count} annotation{'s' if top_count != 1 else ''}."
            )

    if book.time_spent_reading and book.time_spent_reading > 0:
        hours = book.time_spent_reading // 3600
        minutes = (book.time_spent_reading % 3600) // 60
        if hours > 0:
            engagement_parts.append(f"You spent {hours}h {minutes}m reading this book.")
        elif minutes > 0:
            engagement_parts.append(f"You spent {minutes} minutes reading this book.")

    if book.read_percent is not None:
        engagement_parts.append(f"Your reading progress stands at {book.read_percent:.0f}%.")

    if book.rating and book.rating > 0:
        engagement_parts.append(f"You rated it {book.rating} out of 5.")

    if engagement_parts:
        paragraphs.append(" ".join(engagement_parts))

    # Telemetry paragraph
    telemetry_parts: list[str] = []
    if book.word_count and book.word_count > 0:
        telemetry_parts.append(f"The book contains {book.word_count:,} words.")
    if book.page_turns and book.page_turns > 0:
        telemetry_parts.append(f"You turned {book.page_turns:,} pages while reading.")
    if telemetry_parts:
        paragraphs.append(" ".join(telemetry_parts))

    # Representative highlights paragraph
    if highlights:
        top_hl = sorted(highlights, key=lambda a: len(a.text), reverse=True)[:3]
        hl_quotes = [f'"{h.text[:120].rstrip()}..."' if len(h.text) > 120 else f'"{h.text}"' for h in top_hl]
        paragraphs.append("Notable highlights: " + " / ".join(hl_quotes))

    theme_labels = [t.label for t in themes] if themes else []

    return BookSummary(
        book_id=book.id,
        book_title=book.title,
        summary="\n\n".join(paragraphs),
        themes=theme_labels,
        highlight_count=len(highlights),
        method="template",
    )


def generate_summary(
    book: Book,
    themes: list[ThemeCluster] | None = None,
) -> BookSummary:
    """Generate a book summary using the local template engine."""
    return generate_template_summary(book, themes)
