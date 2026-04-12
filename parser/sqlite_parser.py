"""Read-only SQLite parser for KoboReader.sqlite.

Only SELECT queries are executed. The database is opened in read-only mode
using the ``?mode=ro`` URI parameter to prevent accidental writes.

The Kobo database schema varies across device, firmware, and book/source type.
All queries are built adaptively — column and table existence is checked at
runtime so KoNotes never crashes because of missing schema elements.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from models.activity import ProgressSnapshot, ReadingSession
from models.shelf import Shelf
from models.vocabulary import WordLookup
from utils.schema import (
    column_exists,
    get_table_columns,
    inspect_schema,
    safe_execute,
    select_existing_columns,
    table_exists,
)

logger = logging.getLogger(__name__)

_RE_KOBO_SUFFIX = re.compile(r"-\d+$")

# Minimum gap (minutes) between events to split reading sessions
_SESSION_GAP_MINUTES = 30


# ---------------------------------------------------------------------------
# Adaptive query builders
# ---------------------------------------------------------------------------

# Bookmark columns we want, in preference order.
# If a column is missing, it is simply omitted from the query.
_BOOKMARK_WANT = [
    "BookmarkID",
    "VolumeID",
    "ContentID",
    "Text",
    "Annotation",
    "Type",
    "ChapterProgress",
    "DateCreated",
    "DateModified",
]

# Content (book-level) metadata columns — all optional.
_BOOK_META_WANT = [
    "ContentID",
    "Title",
    "Attribution",
    "Publisher",
    "ISBN",
    "Language",
    "ReadStatus",
    "___PercentRead",
    "DateLastRead",
    "Subtitle",
    "Series",
    "ContentType",
    "IsArchived",
    "IsFavorite",
    "DateCreated",
    "TimeSpentReading",
    "TimesStartedReading",
    "LastTimeStartedReading",
    "LastTimeFinishedReading",
    "___NumPages",
    "WordCount",
]


def _build_bookmark_query(conn: sqlite3.Connection) -> tuple[str, list[str]]:
    """Build an adaptive Bookmark SELECT based on available columns.

    Returns ``(sql, available_bookmark_columns)`` or ``("", [])`` when the
    Bookmark table is missing entirely.
    """
    if not table_exists(conn, "Bookmark"):
        return "", []

    bm_cols = select_existing_columns(conn, "Bookmark", _BOOKMARK_WANT)
    if not bm_cols:
        return "", []

    # Build SELECT list with table-qualified names
    select_parts = [f"b.{c}" for c in bm_cols]

    # Optionally join content for chapter title and book title / author
    has_content = table_exists(conn, "content")
    content_cols = get_table_columns(conn, "content") if has_content else set()
    has_volume_id = "VolumeID" in bm_cols

    if has_content and "Title" in content_cols:
        select_parts.append("c.Title AS ChapterTitle")
    if has_content and has_volume_id and "Title" in content_cols:
        select_parts.append("bk.Title AS BookTitle")
    if has_content and has_volume_id and "Attribution" in content_cols:
        select_parts.append("bk.Attribution AS Author")

    sql = f"SELECT {', '.join(select_parts)} FROM Bookmark b"  # noqa: S608

    if has_content and "ContentID" in bm_cols:
        sql += "\nLEFT JOIN content c ON b.ContentID = c.ContentID"
    if has_content and has_volume_id:
        sql += "\nLEFT JOIN content bk ON b.VolumeID = bk.ContentID"

    # Filter to rows with text
    if "Text" in bm_cols:
        sql += "\nWHERE b.Text IS NOT NULL AND b.Text != ''"
    if has_volume_id and "Title" in content_cols:
        sql += "\nORDER BY bk.Title, b.DateCreated" if "DateCreated" in bm_cols else ""

    return sql, bm_cols


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

        # Log detected schema for debugging
        schema = inspect_schema(conn)
        logger.debug(
            "Detected schema: %s",
            {t: len(cols) for t, cols in schema.items()},
        )

        # Gather optional metadata
        book_meta = _load_book_metadata(conn)
        shelf_map = _load_shelf_map(conn)
        chapter_titles = _load_chapter_titles(conn)

        # Build adaptive bookmark query
        sql, bm_cols = _build_bookmark_query(conn)
        if not sql:
            logger.debug("No Bookmark table or no usable columns — returning empty.")
            return []

        rows = safe_execute(conn, sql)
        has_volume_id = "VolumeID" in bm_cols
        has_content_id = "ContentID" in bm_cols
        has_date_modified = "DateModified" in bm_cols
        has_type = "Type" in bm_cols
        has_annotation = "Annotation" in bm_cols
        has_progress = "ChapterProgress" in bm_cols

        for row in rows:
            kind = _map_bookmark_type(_safe_get(row, "Type")) if has_type else "highlight"
            text = (_safe_get(row, "Text") or "").strip()
            note_text = (_safe_get(row, "Annotation") or "").strip() if has_annotation else ""
            volume_id = _safe_get(row, "VolumeID") if has_volume_id else None
            content_id = _safe_get(row, "ContentID") if has_content_id else None
            meta = book_meta.get(volume_id, {}) if volume_id else {}
            if not meta and content_id:
                meta = book_meta.get(content_id, {})

            # Prefer full chapter title from kobo-epub+zip entries
            content_id = _safe_get(row, "ContentID") if has_content_id else None
            chapter = chapter_titles.get(content_id) if content_id else None
            if not chapter:
                chapter = _safe_get(row, "ChapterTitle")

            date_modified = _safe_get(row, "DateModified") if has_date_modified else None

            shared = {
                "book_title": _safe_get(row, "BookTitle") or meta.get("title") or "Unknown Book",
                "author": _safe_get(row, "Author") or meta.get("author") or None,
                "chapter": chapter,
                "location": _format_progress(_safe_get(row, "ChapterProgress")) if has_progress else None,
                "source_id": _safe_get(row, "BookmarkID"),
                "created_at": _safe_get(row, "DateCreated") or None,
                "modified_at": date_modified,
                # Extended metadata
                "publisher": meta.get("publisher"),
                "isbn": meta.get("isbn"),
                "language": meta.get("language"),
                "read_status": meta.get("read_status"),
                "read_percent": meta.get("read_percent"),
                "date_last_read": meta.get("date_last_read"),
                "shelves": shelf_map.get(volume_id, []) if volume_id else shelf_map.get(content_id, []),
                "series": meta.get("series"),
                "subtitle": meta.get("subtitle"),
                "content_type": meta.get("content_type"),
                "is_archived": meta.get("is_archived", False),
                "is_favorited": meta.get("is_favorited", False),
                "date_added": meta.get("date_added"),
                "time_spent_reading": meta.get("time_spent_reading"),
                "times_started_reading": meta.get("times_started_reading"),
                "last_time_started": meta.get("last_time_started"),
                "last_time_finished": meta.get("last_time_finished"),
                "page_count": meta.get("page_count"),
                "word_count": meta.get("word_count"),
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


def extract_shelves(db_path: Path) -> list[Shelf]:
    """Extract shelf (collection) metadata from a KoboReader.sqlite file."""
    uri = db_path.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        return []

    shelves: list[Shelf] = []
    try:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "Shelf"):
            return []

        available = select_existing_columns(
            conn, "Shelf", ["InternalName", "Name", "CreationDate", "LastModified"]
        )
        if "Name" not in available:
            return []

        cols = ", ".join(available)

        # Try filtering by _IsDeleted if the column exists
        has_deleted = column_exists(conn, "Shelf", "_IsDeleted")
        sql = f"SELECT {cols} FROM Shelf"  # noqa: S608
        if has_deleted:
            sql += " WHERE _IsDeleted = 'false' OR _IsDeleted IS NULL"

        for row in safe_execute(conn, sql):
            name = row["Name"]
            if not name:
                continue
            # Count books in this shelf
            count = 0
            internal = _safe_get(row, "InternalName") or name
            if table_exists(conn, "ShelfContent"):
                result = safe_execute(
                    conn,
                    "SELECT COUNT(*) FROM ShelfContent WHERE ShelfName = ?",
                    (internal,),
                )
                if result:
                    count = result[0][0]

            shelves.append(Shelf(
                name=name,
                internal_name=internal,
                created_at=_parse_ts(_safe_get(row, "CreationDate")),
                modified_at=_parse_ts(_safe_get(row, "LastModified")),
                book_count=count,
            ))
    finally:
        conn.close()

    return shelves


def extract_reading_sessions(
    db_path: Path,
    gap_minutes: int = _SESSION_GAP_MINUTES,
) -> list[ReadingSession]:
    """Infer reading sessions from Kobo Event/Analytics timestamps.

    Sessions are inferred from timestamp clustering in the Bookmark table.
    A gap of ``gap_minutes`` or more between events starts a new session.
    """
    uri = db_path.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        return []

    sessions: list[ReadingSession] = []
    try:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "Bookmark"):
            return []

        bm_cols = get_table_columns(conn, "Bookmark")
        if "DateCreated" not in bm_cols:
            return []

        has_volume_id = "VolumeID" in bm_cols
        has_progress = "ChapterProgress" in bm_cols
        has_content = table_exists(conn, "content")

        select_parts = ["b.DateCreated"]
        if has_volume_id:
            select_parts.insert(0, "b.VolumeID")
        if has_progress:
            select_parts.append("b.ChapterProgress")
        if has_content and has_volume_id:
            select_parts.append("bk.Title AS BookTitle")

        sql = f"SELECT {', '.join(select_parts)} FROM Bookmark b"  # noqa: S608
        if has_content and has_volume_id:
            sql += " LEFT JOIN content bk ON b.VolumeID = bk.ContentID"
        sql += " WHERE b.DateCreated IS NOT NULL"
        if has_volume_id:
            sql += " ORDER BY b.VolumeID, b.DateCreated"
        else:
            sql += " ORDER BY b.DateCreated"

        rows = safe_execute(conn, sql)

        # Group by book and cluster into sessions
        book_events: dict[str, list[tuple[datetime, float | None, str]]] = {}
        for row in rows:
            vid = _safe_get(row, "VolumeID") or "unknown"
            ts = _parse_ts(row["DateCreated"])
            if not ts:
                continue
            progress = _safe_get(row, "ChapterProgress") if has_progress else None
            title = _safe_get(row, "BookTitle") or "Unknown Book" if has_content and has_volume_id else "Unknown Book"
            book_events.setdefault(vid, []).append((ts, progress, title))

        for vid, events in book_events.items():
            events.sort(key=lambda e: e[0])
            if not events:
                continue

            session_start = events[0]
            session_end = events[0]

            for i in range(1, len(events)):
                gap = (events[i][0] - session_end[0]).total_seconds() / 60
                if gap > gap_minutes:
                    # Close current session
                    dur = (session_end[0] - session_start[0]).total_seconds() / 60
                    if dur > 0:
                        sessions.append(ReadingSession(
                            book_id=vid,
                            book_title=session_start[2],
                            start_time=session_start[0],
                            end_time=session_end[0],
                            duration_minutes=round(dur, 1),
                            start_percent=session_start[1],
                            end_percent=session_end[1],
                        ))
                    session_start = events[i]
                session_end = events[i]

            # Close last session
            dur = (session_end[0] - session_start[0]).total_seconds() / 60
            if dur > 0:
                sessions.append(ReadingSession(
                    book_id=vid,
                    book_title=session_start[2],
                    start_time=session_start[0],
                    end_time=session_end[0],
                    duration_minutes=round(dur, 1),
                    start_percent=session_start[1],
                    end_percent=session_end[1],
                ))

    finally:
        conn.close()

    sessions.sort(key=lambda s: s.start_time, reverse=True)
    return sessions


def extract_progress_snapshots(db_path: Path) -> list[ProgressSnapshot]:
    """Extract reading progress snapshots from event timestamps."""
    uri = db_path.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        return []

    snapshots: list[ProgressSnapshot] = []
    try:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "Bookmark"):
            return []

        bm_cols = get_table_columns(conn, "Bookmark")
        if not ({"ChapterProgress", "DateCreated"} <= bm_cols):
            return []
        has_volume_id = "VolumeID" in bm_cols

        vid_col = "VolumeID, " if has_volume_id else ""
        sql = (
            f"SELECT {vid_col}ChapterProgress, DateCreated "
            f"FROM Bookmark "
            f"WHERE DateCreated IS NOT NULL AND ChapterProgress IS NOT NULL "
            f"ORDER BY DateCreated"
        )
        for row in safe_execute(conn, sql):
            ts = _parse_ts(row["DateCreated"])
            snapshots.append(ProgressSnapshot(
                book_id=_safe_get(row, "VolumeID") or "unknown" if has_volume_id else "unknown",
                percent=round(row["ChapterProgress"] * 100, 1),
                recorded_at=ts,
            ))
    finally:
        conn.close()

    return snapshots


def extract_word_lookups(db_path: Path) -> list[WordLookup]:
    """Extract vocabulary / dictionary lookups from the WordList table."""
    uri = db_path.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        return []

    lookups: list[WordLookup] = []
    try:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "WordList"):
            return []

        wl_cols = get_table_columns(conn, "WordList")
        if "Text" not in wl_cols:
            return []

        # Build title map for readable book names (multiple ID formats)
        title_map: dict[str, str] = {}
        if table_exists(conn, "content"):
            content_cols = get_table_columns(conn, "content")
            has_book_id = "BookID" in content_cols
            has_content_type = "ContentType" in content_cols
            meta_select = ["ContentID"]
            if has_book_id:
                meta_select.append("BookID")
            meta_select.append("Title")
            cols_str = ", ".join(meta_select)
            sql = f"SELECT {cols_str} FROM content"  # noqa: S608
            if has_content_type:
                sql += " WHERE ContentType = 6"
            for row in safe_execute(conn, sql):
                cid = _safe_get(row, "ContentID")
                title = _safe_get(row, "Title")
                if cid and title:
                    title_map[cid] = title
                if has_book_id:
                    bid = _safe_get(row, "BookID")
                    if bid and title:
                        title_map[bid] = title

        # Build adaptive WordList query
        want = ["Text", "VolumeId", "DictSuffix", "DateCreated"]
        available = select_existing_columns(conn, "WordList", want)
        cols_str = ", ".join(available)
        sql = f"SELECT {cols_str} FROM WordList"  # noqa: S608
        if "DateCreated" in available:
            sql += " ORDER BY DateCreated"

        for row in safe_execute(conn, sql):
            word = row["Text"]
            if not word:
                continue
            vid = _safe_get(row, "VolumeId") or ""
            lang_suffix = _safe_get(row, "DictSuffix") or ""
            lang = lang_suffix.lstrip("-") if lang_suffix else None
            lookups.append(WordLookup(
                word=word,
                book_id=vid,
                book_title=title_map.get(vid) or _title_from_path(vid),
                language=lang,
                looked_up_at=_parse_ts(_safe_get(row, "DateCreated")),
            ))
    finally:
        conn.close()

    return lookups


def extract_ratings(db_path: Path) -> dict[str, int]:
    """Extract user star ratings from the ratings table.

    Returns a mapping of ContentID -> rating (1-5).
    """
    uri = db_path.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        return {}

    ratings: dict[str, int] = {}
    try:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "ratings"):
            return {}
        cols = get_table_columns(conn, "ratings")
        if not ({"ContentID", "Rating"} <= cols):
            return {}

        for row in safe_execute(conn, "SELECT ContentID, Rating FROM ratings"):
            cid = row["ContentID"]
            rating = row["Rating"]
            if cid and rating and isinstance(rating, int) and 1 <= rating <= 5:
                ratings[cid] = rating
    finally:
        conn.close()

    return ratings


def extract_page_turns(db_path: Path) -> dict[str, int]:
    """Extract page-turn counts per book from the Event table.

    Event type 46 represents page-turn aggregations.
    Returns a mapping of ContentID -> total page turns.
    """
    uri = db_path.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        return {}

    page_turns: dict[str, int] = {}
    try:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "Event"):
            return {}
        cols = get_table_columns(conn, "Event")
        if not ({"ContentID", "EventType", "EventCount"} <= cols):
            return {}

        for row in safe_execute(
            conn,
            "SELECT ContentID, EventCount FROM Event WHERE EventType = 46",
        ):
            cid = row["ContentID"]
            count = row["EventCount"] or 0
            if cid:
                page_turns[cid] = page_turns.get(cid, 0) + count
    finally:
        conn.close()

    return page_turns


# ---------------------------------------------------------------------------
# Optional metadata loaders (gracefully handle missing tables/columns)
# ---------------------------------------------------------------------------

def _load_book_metadata(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """Load per-book metadata from the content table.

    Adaptively selects only columns that exist on this database.
    """
    meta: dict[str, dict[str, Any]] = {}
    if not table_exists(conn, "content"):
        return meta

    available = select_existing_columns(conn, "content", _BOOK_META_WANT)
    if "ContentID" not in available:
        return meta

    # Determine content-type filter
    has_content_type = "ContentType" in available
    cols = ", ".join(available)
    sql = f"SELECT {cols} FROM content"  # noqa: S608
    if has_content_type:
        sql += " WHERE ContentType = 6"

    for row in safe_execute(conn, sql):
        cid = row["ContentID"]
        meta[cid] = {
            "title": _safe_get(row, "Title"),
            "author": _safe_get(row, "Attribution"),
            "publisher": _safe_get(row, "Publisher"),
            "isbn": _safe_get(row, "ISBN"),
            "language": _safe_get(row, "Language"),
            "read_status": _safe_get(row, "ReadStatus"),
            "read_percent": _safe_get(row, "___PercentRead"),
            "date_last_read": _safe_get(row, "DateLastRead"),
            "subtitle": _safe_get(row, "Subtitle"),
            "series": _safe_get(row, "Series"),
            "content_type": _safe_get(row, "ContentType"),
            "is_archived": bool(_safe_get(row, "IsArchived")),
            "is_favorited": bool(_safe_get(row, "IsFavorite")),
            "date_added": _safe_get(row, "DateCreated"),
            "time_spent_reading": _safe_get(row, "TimeSpentReading"),
            "times_started_reading": _safe_get(row, "TimesStartedReading"),
            "last_time_started": _safe_get(row, "LastTimeStartedReading"),
            "last_time_finished": _safe_get(row, "LastTimeFinishedReading"),
            "page_count": _safe_positive(row, "___NumPages"),
            "word_count": _safe_positive(row, "WordCount"),
        }
    return meta


def _load_shelf_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Load book→shelf mappings. Returns empty dict if tables are missing."""
    shelf_map: dict[str, list[str]] = {}
    if not (table_exists(conn, "Shelf") and table_exists(conn, "ShelfContent")):
        return shelf_map

    # Verify the columns we need actually exist
    sc_cols = get_table_columns(conn, "ShelfContent")
    shelf_cols = get_table_columns(conn, "Shelf")
    if not ({"ShelfName", "ContentId"} <= sc_cols) or "InternalName" not in shelf_cols:
        # Try alternative column names
        if not ({"ShelfName", "ContentId"} <= sc_cols):
            return shelf_map

    sql = (
        "SELECT si.ContentId, s.Name AS ShelfName "
        "FROM ShelfContent si "
        "JOIN Shelf s ON si.ShelfName = s.InternalName"
    )
    for row in safe_execute(conn, sql):
        cid = _safe_get(row, "ContentId")
        name = _safe_get(row, "ShelfName")
        if cid and name:
            shelf_map.setdefault(cid, []).append(name)
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

    content_cols = get_table_columns(conn, "content")
    if not ({"ContentID", "Title"} <= content_cols):
        return titles

    has_mime = "MimeType" in content_cols
    if has_mime:
        sql = (
            "SELECT ContentID, Title FROM content "
            "WHERE MimeType = 'application/x-kobo-epub+zip' "
            "AND Title IS NOT NULL AND Title != ''"
        )
    else:
        # Without MimeType, fall back to checking for -N suffix in ContentID
        sql = (
            "SELECT ContentID, Title FROM content "
            "WHERE Title IS NOT NULL AND Title != ''"
        )

    for row in safe_execute(conn, sql):
        cid = row["ContentID"]
        title = row["Title"]
        base = _RE_KOBO_SUFFIX.sub("", cid)
        if base != cid and title:
            titles[base] = title
    return titles


def _safe_get(row: sqlite3.Row, key: str) -> Any:
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


def _safe_positive(row: sqlite3.Row, key: str) -> int | None:
    """Return a positive integer value or None (Kobo uses -1 for unknown)."""
    val = _safe_get(row, key)
    if val is not None and isinstance(val, (int, float)) and val > 0:
        return int(val)
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


def _title_from_path(path: str | None) -> str | None:
    """Extract a human-readable book title from a file:///mnt/onboard/... path."""
    if not path or not path.startswith("file:///"):
        return None
    # e.g. file:///mnt/onboard/Author/Title - Author.kepub.epub
    from urllib.parse import unquote
    decoded = unquote(path.split("/")[-1])
    # Strip common epub extensions
    for ext in (".kepub.epub", ".epub", ".cbz", ".pdf"):
        if decoded.lower().endswith(ext):
            decoded = decoded[: -len(ext)]
            break
    # Often formatted as "Title - Author"; take just the title part
    if " - " in decoded:
        decoded = decoded.split(" - ")[0].strip()
    return decoded or None


def _format_progress(progress: float | None) -> str | None:
    if progress is None:
        return None
    pct = progress * 100
    if pct == int(pct):
        return f"{int(pct)}%"
    return f"{pct:.1f}%"


def _parse_ts(value: Any) -> datetime | None:
    """Parse a Kobo timestamp string into a datetime."""
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
