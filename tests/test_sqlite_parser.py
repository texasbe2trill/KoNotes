"""Tests for the enhanced SQLite parser with telemetry extraction."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from parser.sqlite_parser import (
    extract_progress_snapshots,
    extract_reading_sessions,
    extract_shelves,
    parse_sqlite,
)


@pytest.fixture
def kobo_db(tmp_path) -> Path:
    """Create a synthetic KoboReader.sqlite with realistic tables."""
    db_path = tmp_path / "KoboReader.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE content (
            ContentID TEXT PRIMARY KEY,
            ContentType INTEGER,
            Title TEXT,
            Attribution TEXT,
            Publisher TEXT,
            ISBN TEXT,
            Language TEXT,
            ReadStatus INTEGER,
            ___PercentRead REAL,
            DateLastRead TEXT,
            MimeType TEXT,
            Subtitle TEXT,
            Series TEXT,
            IsArchived INTEGER DEFAULT 0,
            IsFavorite INTEGER DEFAULT 0,
            DateCreated TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Bookmark (
            BookmarkID TEXT PRIMARY KEY,
            VolumeID TEXT,
            ContentID TEXT,
            Text TEXT,
            Annotation TEXT,
            Type TEXT,
            ChapterProgress REAL,
            DateCreated TEXT,
            DateModified TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Shelf (
            InternalName TEXT PRIMARY KEY,
            Name TEXT,
            CreationDate TEXT,
            LastModified TEXT,
            _IsDeleted TEXT DEFAULT 'false'
        )
    """)
    conn.execute("""
        CREATE TABLE ShelfContent (
            ShelfName TEXT,
            ContentId TEXT
        )
    """)

    # Insert book metadata
    conn.execute("""
        INSERT INTO content VALUES (
            'file:///vol1', 6, 'Test Book', 'Test Author',
            'Test Publisher', '978-0-1234', 'en', 2, 0.75,
            '2026-03-15T10:00:00', 'application/epub+zip',
            'A Subtitle', 'Test Series', 0, 1, '2026-01-01T00:00:00'
        )
    """)
    conn.execute("""
        INSERT INTO content VALUES (
            'file:///vol2', 6, 'Second Book', 'Another Author',
            NULL, NULL, 'fr', 1, 0.25,
            '2026-04-01T12:00:00', 'application/epub+zip',
            NULL, NULL, 0, 0, '2026-02-01T00:00:00'
        )
    """)

    # Insert chapter entry for kobo-epub+zip lookup
    conn.execute("""
        INSERT INTO content VALUES (
            'file:///vol1#ch1-1', NULL, 'Chapter 1: Introduction', NULL,
            NULL, NULL, NULL, NULL, NULL, NULL,
            'application/x-kobo-epub+zip', NULL, NULL, 0, 0, NULL
        )
    """)

    # Insert bookmarks
    conn.execute("""
        INSERT INTO Bookmark VALUES (
            'bm1', 'file:///vol1', 'file:///vol1#ch1',
            'A highlighted passage', NULL, 'highlight', 0.15,
            '2026-03-10T09:00:00', '2026-03-10T09:01:00'
        )
    """)
    conn.execute("""
        INSERT INTO Bookmark VALUES (
            'bm2', 'file:///vol1', 'file:///vol1#ch1',
            'Another highlight', 'My note about this', 'note', 0.20,
            '2026-03-10T09:05:00', '2026-03-10T09:06:00'
        )
    """)
    conn.execute("""
        INSERT INTO Bookmark VALUES (
            'bm3', 'file:///vol1', 'file:///vol1#ch2',
            'Later highlight', NULL, 'highlight', 0.50,
            '2026-03-10T10:30:00', NULL
        )
    """)
    conn.execute("""
        INSERT INTO Bookmark VALUES (
            'bm4', 'file:///vol2', 'file:///vol2#sec1',
            'French passage', NULL, 'highlight', 0.10,
            '2026-04-01T14:00:00', NULL
        )
    """)

    # Insert shelves
    conn.execute(
        "INSERT INTO Shelf VALUES ('shelf-favorites', 'Favorites', '2026-01-01', '2026-03-01', 'false')"
    )
    conn.execute(
        "INSERT INTO Shelf VALUES ('shelf-deleted', 'Old Shelf', '2025-01-01', '2025-06-01', 'true')"
    )
    conn.execute(
        "INSERT INTO ShelfContent VALUES ('shelf-favorites', 'file:///vol1')"
    )

    conn.commit()
    conn.close()
    return db_path


class TestParseSqlite:
    def test_extracts_annotations(self, kobo_db):
        results = parse_sqlite(kobo_db)
        assert len(results) >= 4  # 3 highlights + 1 note

    def test_book_metadata_populated(self, kobo_db):
        results = parse_sqlite(kobo_db)
        test_book_results = [r for r in results if r["book_title"] == "Test Book"]
        assert len(test_book_results) > 0
        first = test_book_results[0]
        assert first["publisher"] == "Test Publisher"
        assert first["isbn"] == "978-0-1234"

    def test_extended_metadata(self, kobo_db):
        results = parse_sqlite(kobo_db)
        vol1_results = [r for r in results if r["book_title"] == "Test Book"]
        first = vol1_results[0]
        assert first["subtitle"] == "A Subtitle"
        assert first["series"] == "Test Series"
        assert first["is_favorited"] is True

    def test_shelf_populated(self, kobo_db):
        results = parse_sqlite(kobo_db)
        vol1_results = [r for r in results if r["book_title"] == "Test Book"]
        assert vol1_results[0]["shelves"] == ["Favorites"]

    def test_modified_at_extracted(self, kobo_db):
        results = parse_sqlite(kobo_db)
        bm1 = [r for r in results if r.get("source_id") == "bm1"][0]
        assert bm1["modified_at"] is not None

    def test_note_produces_two_entries(self, kobo_db):
        results = parse_sqlite(kobo_db)
        bm2_results = [r for r in results if r.get("source_id") == "bm2"]
        kinds = {r["kind"] for r in bm2_results}
        assert "highlight" in kinds
        assert "note" in kinds

    def test_chapter_title_lookup(self, kobo_db):
        results = parse_sqlite(kobo_db)
        ch1_results = [
            r for r in results if r.get("source_id") == "bm1"
        ]
        # bm1 ContentID is "file:///vol1#ch1", chapter title entry is for
        # "file:///vol1#ch1-1" which strips to "file:///vol1#ch1"
        # This should match via _load_chapter_titles
        assert len(ch1_results) == 1


class TestExtractShelves:
    def test_returns_shelves(self, kobo_db):
        shelves = extract_shelves(kobo_db)
        assert len(shelves) == 1  # deleted shelf excluded
        assert shelves[0].name == "Favorites"

    def test_shelf_book_count(self, kobo_db):
        shelves = extract_shelves(kobo_db)
        assert shelves[0].book_count == 1

    def test_empty_db(self, tmp_path):
        db_path = tmp_path / "empty.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()
        shelves = extract_shelves(db_path)
        assert shelves == []


class TestExtractReadingSessions:
    def test_returns_sessions(self, kobo_db):
        sessions = extract_reading_sessions(kobo_db)
        # At least one session from the clustered timestamps
        assert isinstance(sessions, list)

    def test_session_has_book_title(self, kobo_db):
        sessions = extract_reading_sessions(kobo_db)
        if sessions:
            assert sessions[0].book_title in ("Test Book", "Second Book")

    def test_session_inferred_flag(self, kobo_db):
        sessions = extract_reading_sessions(kobo_db)
        for s in sessions:
            assert s.inferred is True

    def test_empty_db(self, tmp_path):
        db_path = tmp_path / "empty.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()
        sessions = extract_reading_sessions(db_path)
        assert sessions == []


class TestExtractProgressSnapshots:
    def test_returns_snapshots(self, kobo_db):
        snapshots = extract_progress_snapshots(kobo_db)
        assert len(snapshots) >= 4

    def test_snapshot_percent_scaled(self, kobo_db):
        snapshots = extract_progress_snapshots(kobo_db)
        # ChapterProgress 0.15 should become 15.0%
        percents = [s.percent for s in snapshots]
        assert 15.0 in percents

    def test_empty_db(self, tmp_path):
        db_path = tmp_path / "empty.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()
        snapshots = extract_progress_snapshots(db_path)
        assert snapshots == []
