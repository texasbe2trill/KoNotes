"""Load the synthetic demo dataset for immediate dashboard preview."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from models.book import Book
from parser.normalizer import normalize
from parser.sqlite_parser import (
    extract_page_turns,
    extract_progress_snapshots,
    extract_ratings,
    extract_reading_sessions,
    extract_shelves,
    extract_word_lookups,
    parse_sqlite,
)

_DEMO_DB = Path(__file__).resolve().parent.parent / "docs" / "KoNotes_synthetic.sqlite"


def demo_db_available() -> bool:
    """Return True if the synthetic database exists on disk."""
    return _DEMO_DB.is_file()


@st.cache_data(show_spinner="Loading demo dataset…")
def _parse_demo() -> dict:
    """Parse the demo database once and cache the result.

    Returns a plain dict so Streamlit's cache serialisation works without
    needing custom hashing for Pydantic models.
    """
    raw = parse_sqlite(_DEMO_DB)
    books = normalize(raw, source="kobo_sqlite")

    sessions = _safe(extract_reading_sessions, _DEMO_DB)
    snapshots = _safe(extract_progress_snapshots, _DEMO_DB)
    shelves = _safe(extract_shelves, _DEMO_DB)
    word_lookups = _safe(extract_word_lookups, _DEMO_DB)
    ratings = _safe(extract_ratings, _DEMO_DB) or {}
    page_turns = _safe(extract_page_turns, _DEMO_DB) or {}

    return {
        "books": books,
        "sessions": sessions,
        "snapshots": snapshots,
        "shelves": shelves,
        "word_lookups": word_lookups,
        "ratings": ratings,
        "page_turns": page_turns,
        "db_path": _DEMO_DB,
    }


def _safe(fn, *args):  # type: ignore[no-untyped-def]
    try:
        return fn(*args)
    except Exception:
        return []


def load_demo_dataset() -> list[Book]:
    """Populate session state with the synthetic demo data.

    Returns the list of books so the caller can branch on a non-empty result.
    """
    data = _parse_demo()
    books: list[Book] = data["books"]

    st.session_state["books"] = books
    st.session_state["sessions"] = data["sessions"]
    st.session_state["snapshots"] = data["snapshots"]
    st.session_state["shelves"] = data["shelves"]
    st.session_state["word_lookups"] = data["word_lookups"]
    st.session_state["db_path"] = data["db_path"]
    st.session_state["using_demo"] = True

    # Enrich books with ratings and page turns (mirrors _load_telemetry)
    _enrich_books(books, data["ratings"], data["page_turns"], data["db_path"])

    return books


def _enrich_books(
    books: list[Book],
    ratings: dict,
    page_turns: dict,
    db_path: Path,
) -> None:
    """Apply ratings and page turns to loaded books."""
    if not ratings and not page_turns:
        return

    import sqlite3

    cid_title: dict[str, tuple[str, str | None]] = {}
    try:
        uri = db_path.as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            "SELECT ContentID, Title, Attribution FROM content WHERE ContentType = 6"
        ):
            cid_title[row["ContentID"]] = (
                row["Title"] or "Unknown Book",
                row["Attribution"] or None,
            )
        conn.close()
    except Exception:
        return

    book_by_title: dict[str, Book] = {}
    for book in books:
        key = str((book.title, book.author))
        book_by_title[key] = book

    for cid, rating in ratings.items():
        info = cid_title.get(cid)
        if info:
            bk = book_by_title.get(str(info))
            if bk:
                bk.rating = rating

    for cid, turns in page_turns.items():
        info = cid_title.get(cid)
        if info:
            bk = book_by_title.get(str(info))
            if bk:
                bk.page_turns = turns
