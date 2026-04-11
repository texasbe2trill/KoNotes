"""Normalizer: converts raw parser output into typed Book / Annotation models."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Literal

from models.annotation import Annotation
from models.book import Book
from utils.text import slugify


def normalize(raw_annotations: list[dict[str, Any]], source: str) -> list[Book]:
    """Convert a list of raw annotation dicts into a list of :class:`Book` objects.

    Parameters
    ----------
    raw_annotations:
        Output from any ``BaseParser.parse()`` or ``parse_sqlite()``.
    source:
        A short label identifying the input origin (e.g. ``"kobo_md"``).

    Returns
    -------
    list[Book]
        Deduplicated list of books, each with its annotations populated.
    """
    books: dict[str, Book] = {}

    for raw in raw_annotations:
        book_title = (raw.get("book_title") or "Unknown Book").strip()
        author = raw.get("author") or None
        book_id = _make_book_id(book_title, author)

        if book_id not in books:
            books[book_id] = Book(
                id=book_id,
                title=book_title,
                author=author,
                source=source,
                annotations=[],
            )

        annotation = _build_annotation(raw, book_id, source)
        books[book_id].annotations.append(annotation)

    return list(books.values())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_book_id(title: str, author: str | None) -> str:
    key = f"{slugify(title)}|{slugify(author or '')}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def _build_annotation(raw: dict[str, Any], book_id: str, source: str) -> Annotation:
    text = (raw.get("text") or "").strip()
    kind = _coerce_kind(raw.get("kind"))
    created_at = _parse_datetime(raw.get("created_at"))
    ann_id = _make_annotation_id(book_id, text)

    return Annotation(
        id=ann_id,
        book_id=book_id,
        kind=kind,
        text=text,
        created_at=created_at,
        chapter=raw.get("chapter") or None,
        location=raw.get("location") or None,
        source=source,
    )


def _coerce_kind(value: Any) -> Literal["highlight", "note", "unknown"]:
    if isinstance(value, str):
        lower = value.lower()
        if lower == "highlight":
            return "highlight"
        if lower == "note":
            return "note"
    return "unknown"


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def _make_annotation_id(book_id: str, text: str) -> str:
    key = f"{book_id}|{text[:100]}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]
