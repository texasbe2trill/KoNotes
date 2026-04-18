"""Export service: generate a per-book CSV export."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from models.book import Book


def export_book_csv(book: Book) -> str:
    """Render a :class:`Book` and its annotations as CSV.

    Each row represents one annotation, with book metadata repeated on
    every row so the file is self-contained and easy to work with in
    spreadsheets or data-analysis tools.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)

    _sentinel = datetime(1970, 1, 1)

    header = [
        "title",
        "author",
        "kind",
        "text",
        "chapter",
        "location",
        "created_at",
        "modified_at",
        "source",
    ]
    writer.writerow(header)

    sorted_anns = sorted(
        book.annotations,
        key=lambda a: a.created_at or _sentinel,
    )

    for ann in sorted_anns:
        writer.writerow([
            book.title,
            book.author or "",
            ann.kind,
            ann.text,
            ann.chapter or "",
            ann.location or "",
            ann.created_at.isoformat() if ann.created_at else "",
            ann.modified_at.isoformat() if ann.modified_at else "",
            ann.source,
        ])

    return buf.getvalue()
