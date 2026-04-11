"""Read-only SQLite parser for KoboReader.sqlite.

Only SELECT queries are executed. The database is opened in read-only mode
using the ``?mode=ro`` URI parameter to prevent accidental writes.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from utils.schema import column_exists, table_exists

_RE_KOBO_SUFFIX = re.compile(r"-\d+$")


# ---------------------------------------------------------------------------
# Core annotation query
# ---------------------------------------------------------------------------

_BOOKMARK_QUERY = """
SELECT
    b.BookmarkID,
    b.VolumeID,
    b.ContentID,
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
ORDER BY bk.Title, b.DateCreated
"""

# ---------------------------------------------------------------------------
# Optional metadata queries (schema may vary by firmware)
# ---------------------------------------------------------------------------

_SHELF_QUERY = """
SELECT si.ContentId, s.Name AS ShelfName
FROM ShelfContent si
JOIN Shelf s ON si.ShelfName = s.InternalName
"""

_BOOK_META_QUERY = """
SELECT
    ContentID,
    Title,
    Attribution    AS Author,
    Publisher,
    ISBN,
    Language,
    ReadStatus,
    ___PercentRead AS ReadPercent,
    DateLastRead
FROM content
WHERE ContentType = 6
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

        # Gather optional metadata
        book_meta = _load_book_metadata(conn)
        shelf_map = _load_shelf_map(conn)
        chapter_titles = _load_chapter_titles(conn)

        cursor = conn.cursor()
        cursor.execute(_BOOKMARK_QUERY)
        rows = cursor.fetchall()
        for row in rows:
            kind = _map_bookmark_type(row["Type"])
            text = (row["Text"] or "").strip()
            note_text = (row["Annotation"] or "").strip()
            volume_id = row["VolumeID"]
            meta = book_meta.get(volume_id, {})

            # Prefer full chapter title from kobo-epub+zip entries
            content_id = row["ContentID"] if "ContentID" in row.keys() else None
            chapter = chapter_titles.get(content_id) if content_id else None
            if not chapter:
                chapter = row["ChapterTitle"] or None

            shared = {
                "book_title": row["BookTitle"] or "Unknown Book",
                "author": row["Author"] or None,
                "chapter": chapter,
                "location": _format_progress(row["ChapterProgress"]),
                "source_id": row["BookmarkID"],
                "created_at": row["DateCreated"] or None,
                # Extended metadata
                "publisher": meta.get("publisher"),
                "isbn": meta.get("isbn"),
                "language": meta.get("language"),
                "read_status": meta.get("read_status"),
                "read_percent": meta.get("read_percent"),
                "date_last_read": meta.get("date_last_read"),
                "shelves": shelf_map.get(volume_id, []),
            }

            if kind == "note" and note_text:
                results.append({**shared, "kind": "note", "text": note_text})

            if text:
                results.append({
                    **shared,
                    "kind": "highlight" if kind in ("highlight", "note") else kind,
                    "text": text,
                })
    finally:
        conn.close()

    return results


# ---------------------------------------------------------------------------
# Optional metadata loaders (gracefully handle missing tables/columns)
# ---------------------------------------------------------------------------

def _load_book_metadata(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    if not table_exists(conn, "content"):
        return meta
    # Build a safe query based on available columns
    want = [
        "ContentID", "Publisher", "ISBN", "Language",
        "ReadStatus", "___PercentRead", "DateLastRead",
    ]
    available = [c for c in want if column_exists(conn, "content", c)]
    if "ContentID" not in available:
        return meta

    cols = ", ".join(available)
    sql = f"SELECT {cols} FROM content WHERE ContentType = 6"  # noqa: S608
    try:
        for row in conn.execute(sql):
            cid = row["ContentID"]
            meta[cid] = {
                "publisher": _safe_get(row, "Publisher"),
                "isbn": _safe_get(row, "ISBN"),
                "language": _safe_get(row, "Language"),
                "read_status": _safe_get(row, "ReadStatus"),
                "read_percent": _safe_get(row, "___PercentRead"),
                "date_last_read": _safe_get(row, "DateLastRead"),
            }
    except sqlite3.OperationalError:
        pass
    return meta


def _load_shelf_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    shelf_map: dict[str, list[str]] = {}
    if not (table_exists(conn, "Shelf") and table_exists(conn, "ShelfContent")):
        return shelf_map
    try:
        for row in conn.execute(_SHELF_QUERY):
            cid = row["ContentId"]
            shelf_map.setdefault(cid, []).append(row["ShelfName"])
    except sqlite3.OperationalError:
        pass
    return shelf_map


def _load_chapter_titles(conn: sqlite3.Connection) -> dict[str, str]:
    """Build a map from xhtml ContentID to full chapter title.

    Kobo stores full chapter titles (e.g. "Chapter 1: What Is Information?")
    in ``content`` rows with ``MimeType = 'application/x-kobo-epub+zip'``.
    Their ``ContentID`` is the xhtml ContentID with a ``-N`` suffix appended.
    """
    titles: dict[str, str] = {}
    if not table_exists(conn, "content"):
        return titles
    try:
        for row in conn.execute(
            "SELECT ContentID, Title FROM content "
            "WHERE MimeType = 'application/x-kobo-epub+zip' "
            "AND Title IS NOT NULL AND Title != ''"
        ):
            cid = row["ContentID"]
            title = row["Title"]
            # Strip the -N suffix to get the xhtml ContentID
            base = _RE_KOBO_SUFFIX.sub("", cid)
            if base != cid and title:
                titles[base] = title
    except sqlite3.OperationalError:
        pass
    return titles


def _safe_get(row: sqlite3.Row, key: str) -> Any:
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


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
    pct = progress * 100
    if pct == int(pct):
        return f"{int(pct)}%"
    return f"{pct:.1f}%"
