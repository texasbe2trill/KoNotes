"""Export service: generate a per-book Markdown summary."""
from __future__ import annotations

from datetime import datetime

from models.book import Book


def export_book_markdown(book: Book) -> str:
    """Render a :class:`Book` and its annotations as a Markdown string."""
    lines: list[str] = []

    lines.append(f"# {book.title}")
    if book.subtitle:
        lines.append(f"*{book.subtitle}*")
    if book.author:
        lines.append(f"**Author:** {book.author}")
    if book.series:
        lines.append(f"**Series:** {book.series}")
    lines.append(f"**Source:** {book.source}")
    if book.publisher:
        lines.append(f"**Publisher:** {book.publisher}")
    if book.isbn:
        lines.append(f"**ISBN:** {book.isbn}")
    if book.language:
        lines.append(f"**Language:** {book.language}")
    if book.shelves:
        lines.append(f"**Shelves:** {', '.join(book.shelves)}")
    if book.read_percent is not None:
        lines.append(f"**Progress:** {book.read_percent:.0f}%")
    if book.date_last_read:
        lines.append(f"**Last Read:** {book.date_last_read.strftime('%Y-%m-%d')}")
    lines.append(f"**Exported:** {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    _sentinel = datetime(1970, 1, 1)
    highlights = sorted(
        [a for a in book.annotations if a.kind == "highlight"],
        key=lambda a: a.created_at or _sentinel,
    )
    notes = sorted(
        [a for a in book.annotations if a.kind == "note"],
        key=lambda a: a.created_at or _sentinel,
    )
    other = [a for a in book.annotations if a.kind == "unknown"]

    if highlights:
        lines.append(f"## Highlights ({len(highlights)})")
        lines.append("")
        last_chapter: str | None = None
        for ann in highlights:
            if ann.chapter and ann.chapter != last_chapter:
                lines.append(f"### {ann.chapter}")
                lines.append("")
                last_chapter = ann.chapter
            lines.append(f"> {ann.text}")
            meta_parts: list[str] = []
            if ann.location:
                meta_parts.append(f"Location: {ann.location}")
            if ann.created_at:
                meta_parts.append(ann.created_at.strftime("%Y-%m-%d"))
            if meta_parts:
                lines.append(f"*{' · '.join(meta_parts)}*")
            lines.append("")

    if notes:
        lines.append(f"## Notes ({len(notes)})")
        lines.append("")
        last_chapter_n: str | None = None
        for ann in notes:
            if ann.chapter and ann.chapter != last_chapter_n:
                lines.append(f"### {ann.chapter}")
                lines.append("")
                last_chapter_n = ann.chapter
            lines.append(f"**Note:** {ann.text}")
            if ann.location:
                lines.append(f"*Location: {ann.location}*")
            lines.append("")

    if other:
        lines.append(f"## Other Annotations ({len(other)})")
        lines.append("")
        for ann in other:
            lines.append(f"- {ann.text}")
        lines.append("")

    lines.append("---")
    lines.append("*Made with love for the Kobo community. [KoNotes](https://github.com/texasbe2trill/KoNotes)*")
    lines.append("")
    lines.append("*If this was useful, consider starring [KoNotes](https://github.com/texasbe2trill/KoNotes) on GitHub.*")

    return "\n".join(lines)
