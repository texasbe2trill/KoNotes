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

    # Build summary text
    parts: list[str] = []

    author_part = f" by {book.author}" if book.author else ""
    parts.append(
        f"From {book.title}{author_part}, you captured "
        f"{len(highlights)} highlight{'s' if len(highlights) != 1 else ''}"
        f"{f' and {len(notes)} note{chr(115) if len(notes) != 1 else chr(0)[0:0]}' if notes else ''}"
        f" across {chapter_count} chapter{'s' if chapter_count != 1 else ''}."
    )

    if themes:
        theme_texts = [t.representative_text[:80] for t in themes[:3]]
        parts.append(
            f"Key themes include: {'; '.join(f'"{t}..."' if len(t) >= 80 else f'"{t}"' for t in theme_texts)}."
        )

    # Most annotated chapter
    if chapters:
        chapter_counter: Counter[str] = Counter()
        for a in book.annotations:
            if a.chapter:
                chapter_counter[a.chapter] += 1
        if chapter_counter:
            top_chapter, top_count = chapter_counter.most_common(1)[0]
            parts.append(
                f"Your most annotated chapter was \"{top_chapter}\" "
                f"with {top_count} annotation{'s' if top_count != 1 else ''}."
            )

    # Reading time
    if book.time_spent_reading and book.time_spent_reading > 0:
        hours = book.time_spent_reading // 3600
        minutes = (book.time_spent_reading % 3600) // 60
        if hours > 0:
            parts.append(f"You spent {hours}h {minutes}m reading this book.")
        elif minutes > 0:
            parts.append(f"You spent {minutes} minutes reading this book.")

    # Progress
    if book.read_percent is not None:
        parts.append(f"Your reading progress stands at {book.read_percent:.0f}%.")

    # Rating
    if book.rating and book.rating > 0:
        parts.append(f"You rated it {book.rating} out of 5.")

    # Word count / page count
    if book.word_count and book.word_count > 0:
        parts.append(f"The book contains {book.word_count:,} words.")
    if book.page_turns and book.page_turns > 0:
        parts.append(f"You turned {book.page_turns:,} pages while reading.")

    theme_labels = [t.label for t in themes] if themes else []

    return BookSummary(
        book_id=book.id,
        book_title=book.title,
        summary=" ".join(parts),
        themes=theme_labels,
        highlight_count=len(highlights),
        method="template",
    )


def generate_llm_summary(
    book: Book,
    api_key: str,
    themes: list[ThemeCluster] | None = None,
) -> BookSummary:
    """Generate a summary using OpenAI GPT-4o-mini from the book's highlights."""
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "openai is required for LLM summaries. "
            "Install with: pip install 'konotes[openai]'"
        ) from exc

    highlights = [a for a in book.annotations if a.kind == "highlight"]
    if not highlights:
        return generate_template_summary(book, themes)

    # Build the prompt with highlight texts
    highlight_block = "\n".join(f"- {h.text}" for h in highlights[:50])

    author_part = f" by {book.author}" if book.author else ""
    system_prompt = (
        "You are a reading assistant. Given a reader's highlights from a book, "
        "produce a concise 'what I learned' summary in 2-4 paragraphs. "
        "Focus on the key ideas, recurring themes, and notable insights. "
        "Write in second person ('you'). Do not use emojis."
    )
    user_prompt = (
        f"Book: {book.title}{author_part}\n\n"
        f"Highlights ({len(highlights)} total, showing up to 50):\n{highlight_block}\n\n"
        "Summarise what the reader took away from this book."
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=600,
        temperature=0.7,
    )
    summary_text = response.choices[0].message.content or ""

    theme_labels = [t.label for t in themes] if themes else []

    return BookSummary(
        book_id=book.id,
        book_title=book.title,
        summary=summary_text.strip(),
        themes=theme_labels,
        highlight_count=len(highlights),
        method="llm",
    )


def generate_summary(
    book: Book,
    api_key: str | None = None,
    themes: list[ThemeCluster] | None = None,
) -> BookSummary:
    """Generate a book summary. Uses LLM if api_key is provided, otherwise template."""
    if api_key:
        try:
            return generate_llm_summary(book, api_key, themes)
        except Exception:
            logger.warning("LLM summary failed for %s, falling back to template", book.title)
    return generate_template_summary(book, themes)
