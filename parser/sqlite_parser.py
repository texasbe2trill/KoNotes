"""Read-only SQLite parser for KoboReader.sqlite.

Only SELECT queries are executed. The database is opened in read-only mode
using the ``?mode=ro`` URI parameter to prevent accidental writes.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from models.activity import ProgressSnapshot, ReadingSession
from models.shelf import Shelf
from models.vocabulary import WordLookup
from utils.schema import column_exists, table_exists

_RE_KOBO_SUFFIX = re.compile(r"-\d+$")

# Minimum gap (minutes) between events to split reading sessions
_SESSION_GAP_MINUTES = 30


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
    b.DateModified,
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


# Extended metadata columns — may or may not exist on a given firmware
_EXTENDED_META_COLS = [
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

        # Check if DateModified exists in Bookmark table
        has_date_modified = column_exists(conn, "Bookmark", "DateModified")

        cursor = conn.cursor()
        if has_date_modified:
            cursor.execute(_BOOKMARK_QUERY)
        else:
            # Fall back to query without DateModified
            fallback = _BOOKMARK_QUERY.replace("    b.DateModified,\n", "")
            cursor.execute(fallback)

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

            date_modified = _safe_get(row, "DateModified") if has_date_modified else None

            shared = {
                "book_title": row["BookTitle"] or "Unknown Book",
                "author": row["Author"] or None,
                "chapter": chapter,
                "location": _format_progress(row["ChapterProgress"]),
                "source_id": row["BookmarkID"],
                "created_at": row["DateCreated"] or None,
                "modified_at": date_modified,
                # Extended metadata
                "publisher": meta.get("publisher"),
                "isbn": meta.get("isbn"),
                "language": meta.get("language"),
                "read_status": meta.get("read_status"),
                "read_percent": meta.get("read_percent"),
                "date_last_read": meta.get("date_last_read"),
                "shelves": shelf_map.get(volume_id, []),
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

        want = ["InternalName", "Name", "CreationDate", "LastModified"]
        available = [c for c in want if column_exists(conn, "Shelf", c)]
        if "Name" not in available:
            return []

        cols = ", ".join(available)
        sql = f"SELECT {cols} FROM Shelf WHERE _IsDeleted = 'false' OR _IsDeleted IS NULL"  # noqa: S608
        try:
            for row in conn.execute(sql):
                name = row["Name"]
                if not name:
                    continue
                # Count books in this shelf
                count = 0
                internal = _safe_get(row, "InternalName") or name
                if table_exists(conn, "ShelfContent"):
                    try:
                        cur = conn.execute(
                            "SELECT COUNT(*) FROM ShelfContent WHERE ShelfName = ?",
                            (internal,),
                        )
                        count = cur.fetchone()[0]
                    except sqlite3.OperationalError:
                        pass

                shelves.append(Shelf(
                    name=name,
                    internal_name=internal,
                    created_at=_parse_ts(_safe_get(row, "CreationDate")),
                    modified_at=_parse_ts(_safe_get(row, "LastModified")),
                    book_count=count,
                ))
        except sqlite3.OperationalError:
            pass
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

        has_progress = column_exists(conn, "Bookmark", "ChapterProgress")
        progress_col = ", b.ChapterProgress" if has_progress else ""

        sql = (
            f"SELECT b.VolumeID, b.DateCreated{progress_col}, "
            f"bk.Title AS BookTitle "
            f"FROM Bookmark b "
            f"LEFT JOIN content bk ON b.VolumeID = bk.ContentID "
            f"WHERE b.DateCreated IS NOT NULL "
            f"ORDER BY b.VolumeID, b.DateCreated"
        )

        try:
            rows = conn.execute(sql).fetchall()
        except sqlite3.OperationalError:
            return []

        # Group by book and cluster into sessions
        book_events: dict[str, list[tuple[datetime, float | None, str]]] = {}
        for row in rows:
            vid = row["VolumeID"]
            ts = _parse_ts(row["DateCreated"])
            if not ts:
                continue
            progress = row["ChapterProgress"] if has_progress else None
            title = row["BookTitle"] or "Unknown Book"
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
        if not column_exists(conn, "Bookmark", "ChapterProgress"):
            return []

        sql = (
            "SELECT VolumeID, ChapterProgress, DateCreated "
            "FROM Bookmark "
            "WHERE DateCreated IS NOT NULL AND ChapterProgress IS NOT NULL "
            "ORDER BY DateCreated"
        )
        try:
            for row in conn.execute(sql):
                ts = _parse_ts(row["DateCreated"])
                snapshots.append(ProgressSnapshot(
                    book_id=row["VolumeID"],
                    percent=round(row["ChapterProgress"] * 100, 1),
                    recorded_at=ts,
                ))
        except sqlite3.OperationalError:
            pass
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

        # Build title map for readable book names (multiple ID formats)
        title_map: dict[str, str] = {}
        if table_exists(conn, "content"):
            has_book_id = column_exists(conn, "content", "BookID")
            cols = "ContentID, BookID, Title" if has_book_id else "ContentID, Title"
            try:
                for row in conn.execute(
                    f"SELECT {cols} FROM content WHERE ContentType = 6"  # noqa: S608
                ):
                    cid = row["ContentID"]
                    title = row["Title"]
                    if cid and title:
                        title_map[cid] = title
                    # Also map by BookID (file:///mnt/onboard/... path)
                    if has_book_id:
                        bid = _safe_get(row, "BookID")
                        if bid and title:
                            title_map[bid] = title
            except sqlite3.OperationalError:
                pass

        try:
            for row in conn.execute(
                "SELECT Text, VolumeId, DictSuffix, DateCreated "
                "FROM WordList ORDER BY DateCreated"
            ):
                word = row["Text"]
                vid = row["VolumeId"]
                if not word:
                    continue
                lang_suffix = row["DictSuffix"] or ""
                lang = lang_suffix.lstrip("-") if lang_suffix else None
                lookups.append(WordLookup(
                    word=word,
                    book_id=vid or "",
                    book_title=title_map.get(vid) or _title_from_path(vid),
                    language=lang,
                    looked_up_at=_parse_ts(row["DateCreated"]),
                ))
        except sqlite3.OperationalError:
            pass
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
        try:
            for row in conn.execute("SELECT ContentID, Rating FROM ratings"):
                cid = row["ContentID"]
                rating = row["Rating"]
                if cid and rating and isinstance(rating, int) and 1 <= rating <= 5:
                    ratings[cid] = rating
        except sqlite3.OperationalError:
            pass
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
        try:
            for row in conn.execute(
                "SELECT ContentID, EventCount FROM Event WHERE EventType = 46"
            ):
                cid = row["ContentID"]
                count = row["EventCount"] or 0
                if cid:
                    page_turns[cid] = page_turns.get(cid, 0) + count
        except sqlite3.OperationalError:
            pass
    finally:
        conn.close()

    return page_turns


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
    ] + _EXTENDED_META_COLS
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
