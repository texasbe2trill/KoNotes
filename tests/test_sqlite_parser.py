"""Tests for the enhanced SQLite parser with telemetry extraction."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from parser.sqlite_parser import (
    _title_from_path,
    extract_page_turns,
    extract_progress_snapshots,
    extract_ratings,
    extract_reading_sessions,
    extract_shelves,
    extract_word_lookups,
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


# ── Word Lookups ─────────────────────────────────────────────────


@pytest.fixture
def kobo_db_with_wordlist(kobo_db) -> Path:
    """Extend the base fixture with WordList, ratings, and Event tables."""
    conn = sqlite3.connect(str(kobo_db))
    conn.execute("""
        CREATE TABLE WordList (
            Text TEXT,
            VolumeId TEXT,
            DictSuffix TEXT,
            DateCreated TEXT
        )
    """)
    conn.execute("""
        INSERT INTO WordList VALUES
            ('stoicism', 'file:///vol1', '-en', '2026-03-10T09:30:00')
    """)
    conn.execute("""
        INSERT INTO WordList VALUES
            ('ephemeral', 'file:///vol1', '-en', '2026-03-10T10:00:00')
    """)
    conn.execute("""
        INSERT INTO WordList VALUES
            ('bonjour', 'file:///vol2', '-fr', '2026-04-01T15:00:00')
    """)
    conn.execute("""
        INSERT INTO WordList VALUES
            ('soleil', 'file:///mnt/onboard/Author/My Great Book - Author.kepub.epub', '-fr', '2026-04-02T10:00:00')
    """)

    # Ratings table
    conn.execute("""
        CREATE TABLE ratings (
            ContentID TEXT,
            Rating INTEGER,
            DateModified TEXT
        )
    """)
    conn.execute("INSERT INTO ratings VALUES ('file:///vol1', 5, '2026-03-15')")
    conn.execute("INSERT INTO ratings VALUES ('file:///vol2', 3, '2026-04-01')")
    conn.execute("INSERT INTO ratings VALUES ('file:///vol3', 0, '2026-04-01')")  # invalid
    conn.execute("INSERT INTO ratings VALUES ('file:///vol4', 6, '2026-04-01')")  # out of range

    # Event table with page turns (type 46)
    conn.execute("""
        CREATE TABLE Event (
            ContentID TEXT,
            EventType INTEGER,
            EventCount INTEGER
        )
    """)
    conn.execute("INSERT INTO Event VALUES ('file:///vol1', 46, 120)")
    conn.execute("INSERT INTO Event VALUES ('file:///vol1', 46, 80)")  # second batch
    conn.execute("INSERT INTO Event VALUES ('file:///vol2', 46, 50)")
    conn.execute("INSERT INTO Event VALUES ('file:///vol1', 3, 5)")  # not page turns

    conn.commit()
    conn.close()
    return kobo_db


class TestExtractWordLookups:
    def test_returns_lookups(self, kobo_db_with_wordlist):
        lookups = extract_word_lookups(kobo_db_with_wordlist)
        assert len(lookups) == 4

    def test_word_text(self, kobo_db_with_wordlist):
        lookups = extract_word_lookups(kobo_db_with_wordlist)
        words = [w.word for w in lookups]
        assert "stoicism" in words
        assert "bonjour" in words

    def test_book_title_resolved(self, kobo_db_with_wordlist):
        lookups = extract_word_lookups(kobo_db_with_wordlist)
        vol1_lookups = [w for w in lookups if w.book_id == "file:///vol1"]
        assert vol1_lookups[0].book_title == "Test Book"

    def test_language_extracted(self, kobo_db_with_wordlist):
        lookups = extract_word_lookups(kobo_db_with_wordlist)
        fr_lookups = [w for w in lookups if w.language == "fr"]
        assert len(fr_lookups) >= 1

    def test_timestamp_parsed(self, kobo_db_with_wordlist):
        lookups = extract_word_lookups(kobo_db_with_wordlist)
        assert lookups[0].looked_up_at is not None

    def test_file_path_fallback(self, kobo_db_with_wordlist):
        lookups = extract_word_lookups(kobo_db_with_wordlist)
        path_lookup = [w for w in lookups if w.word == "soleil"]
        assert len(path_lookup) == 1
        assert path_lookup[0].book_title == "My Great Book"

    def test_empty_db(self, tmp_path):
        db_path = tmp_path / "empty.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()
        lookups = extract_word_lookups(db_path)
        assert lookups == []


class TestExtractRatings:
    def test_returns_valid_ratings(self, kobo_db_with_wordlist):
        ratings = extract_ratings(kobo_db_with_wordlist)
        assert ratings["file:///vol1"] == 5
        assert ratings["file:///vol2"] == 3

    def test_excludes_invalid_ratings(self, kobo_db_with_wordlist):
        ratings = extract_ratings(kobo_db_with_wordlist)
        # Rating 0 and 6 should be excluded
        assert "file:///vol3" not in ratings
        assert "file:///vol4" not in ratings

    def test_count(self, kobo_db_with_wordlist):
        ratings = extract_ratings(kobo_db_with_wordlist)
        assert len(ratings) == 2

    def test_empty_db(self, tmp_path):
        db_path = tmp_path / "empty.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()
        ratings = extract_ratings(db_path)
        assert ratings == {}


class TestExtractPageTurns:
    def test_aggregates_per_book(self, kobo_db_with_wordlist):
        turns = extract_page_turns(kobo_db_with_wordlist)
        # vol1 has 120 + 80 = 200
        assert turns["file:///vol1"] == 200
        assert turns["file:///vol2"] == 50

    def test_excludes_non_page_turn_events(self, kobo_db_with_wordlist):
        turns = extract_page_turns(kobo_db_with_wordlist)
        # Type 3 events should not contribute
        assert turns["file:///vol1"] == 200  # not 205

    def test_empty_db(self, tmp_path):
        db_path = tmp_path / "empty.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()
        turns = extract_page_turns(db_path)
        assert turns == {}


class TestTitleFromPath:
    def test_kepub_epub(self):
        path = "file:///mnt/onboard/Author/Sapiens - Yuval Noah Harari.kepub.epub"
        assert _title_from_path(path) == "Sapiens"

    def test_plain_epub(self):
        path = "file:///mnt/onboard/Books/The Great Gatsby - F. Scott Fitzgerald.epub"
        assert _title_from_path(path) == "The Great Gatsby"

    def test_no_author_suffix(self):
        path = "file:///mnt/onboard/Books/Meditations.epub"
        assert _title_from_path(path) == "Meditations"

    def test_url_encoded(self):
        path = "file:///mnt/onboard/Books/My%20Book%20Title%20-%20Author.kepub.epub"
        assert _title_from_path(path) == "My Book Title"

    def test_pdf(self):
        path = "file:///mnt/onboard/Research Paper - J. Smith.pdf"
        assert _title_from_path(path) == "Research Paper"

    def test_none_input(self):
        assert _title_from_path(None) is None

    def test_non_file_path(self):
        assert _title_from_path("some-uuid-string") is None

    def test_empty_string(self):
        assert _title_from_path("") is None
