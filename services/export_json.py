"""Export service: generate a per-book JSON export."""
from __future__ import annotations

import json
from datetime import datetime

from models.book import Book

_FOOTER = (
    "Made with love for the Kobo community. https://github.com/texasbe2trill/KoNotes\n"
    "If this was useful, consider starring KoNotes: https://github.com/texasbe2trill/KoNotes"
)


def export_book_json(book: Book) -> str:
    """Render a :class:`Book` and its annotations as a JSON string."""
    _sentinel = datetime(1970, 1, 1)
    sorted_anns = sorted(
        book.annotations,
        key=lambda a: a.created_at or _sentinel,
    )
    data = {
        "title": book.title,
        "author": book.author,
        "subtitle": book.subtitle,
        "series": book.series,
        "source": book.source,
        "exported_at": datetime.now().isoformat(),
        "annotations": [
            {
                "kind": ann.kind,
                "text": ann.text,
                "chapter": ann.chapter,
                "location": ann.location,
                "created_at": ann.created_at.isoformat() if ann.created_at else None,
                "modified_at": ann.modified_at.isoformat() if ann.modified_at else None,
            }
            for ann in sorted_anns
        ],
        "meta": {
            "publisher": book.publisher,
            "isbn": book.isbn,
            "language": book.language,
            "read_percent": book.read_percent,
            "read_status": book.read_status,
            "date_last_read": book.date_last_read.isoformat() if book.date_last_read else None,
            "shelves": book.shelves,
            "is_archived": book.is_archived,
            "is_favorited": book.is_favorited,
        },
        "telemetry": {
            "total_highlights": sum(1 for a in book.annotations if a.kind == "highlight"),
            "total_notes": sum(1 for a in book.annotations if a.kind == "note"),
            "total_annotations": len(book.annotations),
            "chapters": sorted({a.chapter for a in book.annotations if a.chapter}),
        },
        "exporter": {
            "tool": "KoNotes",
            "version": "0.5.0",
            "url": "https://github.com/texasbe2trill/KoNotes",
        },
        "footer": _FOOTER,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
