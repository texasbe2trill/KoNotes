"""Export service: generate a per-book plain-text export."""
from __future__ import annotations

from datetime import datetime

from models.book import Book

_FOOTER = "Made with love for the Kobo community. https://github.com/texasbe2trill/KoNotes"


def export_book_text(book: Book) -> str:
    """Render a :class:`Book` and its annotations as readable plain text."""
    lines: list[str] = []

    lines.append(book.title)
    if book.author:
        lines.append(f"by {book.author}")
    lines.append(f"Source: {book.source}")
    lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("=" * 60)
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
        lines.append(f"HIGHLIGHTS ({len(highlights)})")
        lines.append("-" * 40)
        last_chapter: str | None = None
        for ann in highlights:
            if ann.chapter and ann.chapter != last_chapter:
                lines.append(f"  [{ann.chapter}]")
                last_chapter = ann.chapter
            lines.append(f'  "{ann.text}"')
            meta_parts: list[str] = []
            if ann.location:
                meta_parts.append(f"Location: {ann.location}")
            if ann.created_at:
                meta_parts.append(ann.created_at.strftime("%Y-%m-%d"))
            if meta_parts:
                lines.append(f"  -- {' | '.join(meta_parts)}")
            lines.append("")

    if notes:
        lines.append(f"NOTES ({len(notes)})")
        lines.append("-" * 40)
        last_chapter_n: str | None = None
        for ann in notes:
            if ann.chapter and ann.chapter != last_chapter_n:
                lines.append(f"  [{ann.chapter}]")
                last_chapter_n = ann.chapter
            lines.append(f"  {ann.text}")
            if ann.location:
                lines.append(f"  -- Location: {ann.location}")
            lines.append("")

    if other:
        lines.append(f"OTHER ({len(other)})")
        lines.append("-" * 40)
        for ann in other:
            lines.append(f"  - {ann.text}")
        lines.append("")

    lines.append("=" * 60)
    lines.append(_FOOTER)

    return "\n".join(lines)
