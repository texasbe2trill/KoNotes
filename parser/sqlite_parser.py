"""Read-only SQLite parser for KoboReader.sqlite.

Only SELECT queries are executed. The database is opened in read-only mode
using the ``?mode=ro`` URI parameter to prevent accidental writes.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


# Tables and columns we care about
_BOOKMARK_QUERY = """
SELECT
    b.BookmarkID,
    b.VolumeID,
    b.Text,
    b.Annotation,
    b.Type,
    b.ChapterProgress,
    b.DateCreated,
    c.Title  AS ChapterTitle,
    bk.Title AS BookTitle,
    bk.Attribution AS Author
FROM Bookmark b
LEFT JOIN content c  ON b.ContentID = c.ContentID
LEFT JOIN content bk ON b.VolumeID  = bk.ContentID
WHERE b.Text IS NOT NULL AND b.Text != ''
ORDER BY bk.Title, b.ChapterProgress
"""


def parse_sqlite(db_path: Path) -> list[dict[str, Any]]:
    """Extract annotations from a KoboReader.sqlite file.

    Parameters
    ----------
    db_path:
        Path to the ``KoboReader.sqlite`` file. Opened read-only.

    Returns
    -------
    list[dict[str, Any]]
        Raw annotation dicts compatible with the normalizer.
    """
    uri = db_path.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as exc:
        raise ValueError(
            f"Could not open KoboReader.sqlite at {db_path}: {exc}"
        ) from exc

    results: list[dict[str, Any]] = []
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(_BOOKMARK_QUERY)
        rows = cursor.fetchall()
        for row in rows:
            kind = _map_bookmark_type(row["Type"])
            # When kind is "note", the actual highlight is in Text and the
            # user's written note is in Annotation.
            text = (row["Text"] or "").strip()
            note_text = (row["Annotation"] or "").strip()

            if kind == "note" and note_text:
                # Emit the user's note as a separate annotation
                results.append(
                    {
                        "book_title": row["BookTitle"] or "Unknown Book",
                        "author": row["Author"] or None,
                        "kind": "note",
                        "text": note_text,
                        "chapter": row["ChapterTitle"] or None,
                        "location": _format_progress(row["ChapterProgress"]),
                        "source_id": row["BookmarkID"],
                        "created_at": row["DateCreated"] or None,
                    }
                )

            if text:
                results.append(
                    {
                        "book_title": row["BookTitle"] or "Unknown Book",
                        "author": row["Author"] or None,
                        "kind": "highlight" if kind in ("highlight", "note") else kind,
                        "text": text,
                        "chapter": row["ChapterTitle"] or None,
                        "location": _format_progress(row["ChapterProgress"]),
                        "source_id": row["BookmarkID"],
                        "created_at": row["DateCreated"] or None,
                    }
                )
    finally:
        conn.close()

    return results


def _map_bookmark_type(raw_type: str | None) -> str:
    if not raw_type:
        return "highlight"
    lower = raw_type.lower()
    if "note" in lower or "annotation" in lower:
        return "note"
    if "highlight" in lower:
        return "highlight"
    return "unknown"


def _format_progress(progress: float | None) -> str | None:
    if progress is None:
        return None
    return f"{progress * 100:.1f}%"
