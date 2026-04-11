"""Export service: generate a per-book JSON export."""
from __future__ import annotations

import json
from datetime import datetime

from models.book import Book

_FOOTER = "Made with love for the Kobo community. https://github.com/texasbe2trill/KoNotes"


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
        "source": book.source,
        "exported_at": datetime.now().isoformat(),
        "annotations": [
            {
                "kind": ann.kind,
                "text": ann.text,
                "chapter": ann.chapter,
                "location": ann.location,
                "created_at": ann.created_at.isoformat() if ann.created_at else None,
            }
            for ann in sorted_anns
        ],
        "meta": {
            "publisher": book.publisher,
            "isbn": book.isbn,
            "language": book.language,
            "read_percent": book.read_percent,
            "shelves": book.shelves,
        },
        "footer": _FOOTER,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
