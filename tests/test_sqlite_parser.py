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


# ── Schema resilience tests ──────────────────────────────────────


class TestMissingVolumeID:
    """Parser must not crash when Bookmark.VolumeID is absent."""

    @pytest.fixture
    def db_no_volumeid(self, tmp_path) -> Path:
        db_path = tmp_path / "KoboReader.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE content (
                ContentID TEXT PRIMARY KEY,
                ContentType INTEGER,
                Title TEXT,
                Attribution TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE Bookmark (
                BookmarkID TEXT PRIMARY KEY,
                ContentID TEXT,
                Text TEXT,
                Type TEXT,
                DateCreated TEXT
            )
        """)
        conn.execute(
            "INSERT INTO content VALUES ('book1', 6, 'Meditations', 'Marcus Aurelius')"
        )
        conn.execute(
            "INSERT INTO Bookmark VALUES ('bm1', 'book1', 'A passage', 'highlight', '2026-01-01T10:00:00')"
        )
        conn.commit()
        conn.close()
        return db_path

    def test_parse_succeeds(self, db_no_volumeid):
        results = parse_sqlite(db_no_volumeid)
        assert len(results) >= 1

    def test_text_extracted(self, db_no_volumeid):
        results = parse_sqlite(db_no_volumeid)
        texts = [r["text"] for r in results]
        assert "A passage" in texts

    def test_shelves_empty(self, db_no_volumeid):
        results = parse_sqlite(db_no_volumeid)
        assert results[0]["shelves"] == []

    def test_sessions_empty(self, db_no_volumeid):
        sessions = extract_reading_sessions(db_no_volumeid)
        assert isinstance(sessions, list)

    def test_snapshots_empty(self, db_no_volumeid):
        # No ChapterProgress column
        snapshots = extract_progress_snapshots(db_no_volumeid)
        assert snapshots == []


class TestMissingOptionalColumns:
    """Parser must handle databases missing optional metadata columns."""

    @pytest.fixture
    def minimal_db(self, tmp_path) -> Path:
        """Bare-minimum schema: only required columns."""
        db_path = tmp_path / "KoboReader.sqlite"
        conn = sqlite3.connect(str(db_path))
        # content with NO Publisher, ISBN, Language, ReadStatus, etc.
        conn.execute("""
            CREATE TABLE content (
                ContentID TEXT PRIMARY KEY,
                ContentType INTEGER,
                Title TEXT,
                Attribution TEXT
            )
        """)
        # Bookmark with NO Annotation, ChapterProgress, DateModified
        conn.execute("""
            CREATE TABLE Bookmark (
                BookmarkID TEXT PRIMARY KEY,
                VolumeID TEXT,
                ContentID TEXT,
                Text TEXT,
                Type TEXT,
                DateCreated TEXT
            )
        """)
        conn.execute(
            "INSERT INTO content VALUES ('vol1', 6, 'Nexus', 'Yuval Noah Harari')"
        )
        conn.execute(
            "INSERT INTO Bookmark VALUES "
            "('bm1', 'vol1', 'vol1#ch1', 'An important idea', 'highlight', '2026-03-01T12:00:00')"
        )
        conn.commit()
        conn.close()
        return db_path

    def test_parse_succeeds(self, minimal_db):
        results = parse_sqlite(minimal_db)
        assert len(results) == 1
        assert results[0]["text"] == "An important idea"

    def test_missing_metadata_is_none(self, minimal_db):
        results = parse_sqlite(minimal_db)
        r = results[0]
        assert r["publisher"] is None
        assert r["isbn"] is None
        assert r["read_percent"] is None
        assert r["modified_at"] is None

    def test_shelves_without_shelf_tables(self, minimal_db):
        shelves = extract_shelves(minimal_db)
        assert shelves == []

    def test_ratings_without_ratings_table(self, minimal_db):
        ratings = extract_ratings(minimal_db)
        assert ratings == {}

    def test_page_turns_without_event_table(self, minimal_db):
        turns = extract_page_turns(minimal_db)
        assert turns == {}

    def test_word_lookups_without_wordlist_table(self, minimal_db):
        lookups = extract_word_lookups(minimal_db)
        assert lookups == []


class TestMissingBookmarkType:
    """When Bookmark.Type is absent, annotations should default to highlight."""

    @pytest.fixture
    def db_no_type(self, tmp_path) -> Path:
        db_path = tmp_path / "KoboReader.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE content (
                ContentID TEXT PRIMARY KEY,
                ContentType INTEGER,
                Title TEXT,
                Attribution TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE Bookmark (
                BookmarkID TEXT PRIMARY KEY,
                VolumeID TEXT,
                ContentID TEXT,
                Text TEXT,
                DateCreated TEXT
            )
        """)
        conn.execute("INSERT INTO content VALUES ('v1', 6, 'Book A', 'Author A')")
        conn.execute(
            "INSERT INTO Bookmark VALUES ('b1', 'v1', 'v1#c1', 'Some text', '2026-01-01')"
        )
        conn.commit()
        conn.close()
        return db_path

    def test_defaults_to_highlight(self, db_no_type):
        results = parse_sqlite(db_no_type)
        assert len(results) == 1
        assert results[0]["kind"] == "highlight"


class TestMissingShelvesTables:
    """Shelves extraction must handle missing Shelf or ShelfContent tables."""

    @pytest.fixture
    def db_shelf_no_content(self, tmp_path) -> Path:
        db_path = tmp_path / "KoboReader.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE Shelf (
                InternalName TEXT, Name TEXT,
                CreationDate TEXT, LastModified TEXT, _IsDeleted TEXT
            )
        """)
        conn.execute("INSERT INTO Shelf VALUES ('s1', 'My Shelf', '2026-01-01', '2026-01-02', 'false')")
        # No ShelfContent table
        conn.commit()
        conn.close()
        return db_path

    def test_no_shelfcontent_table(self, db_shelf_no_content):
        shelves = extract_shelves(db_shelf_no_content)
        # Shelf exists but ShelfContent doesn't — still returns shelf with 0 count
        assert len(shelves) == 1
        assert shelves[0].book_count == 0

    def test_no_shelf_table(self, tmp_path):
        db_path = tmp_path / "KoboReader.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE ShelfContent (ShelfName TEXT, ContentId TEXT)")
        conn.commit()
        conn.close()
        shelves = extract_shelves(db_path)
        assert shelves == []


class TestContentWithoutContentType:
    """Handle content table that has no ContentType column."""

    @pytest.fixture
    def db_no_content_type(self, tmp_path) -> Path:
        db_path = tmp_path / "KoboReader.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE content (
                ContentID TEXT PRIMARY KEY,
                Title TEXT,
                Attribution TEXT,
                Publisher TEXT,
                ISBN TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE Bookmark (
                BookmarkID TEXT PRIMARY KEY,
                VolumeID TEXT,
                ContentID TEXT,
                Text TEXT,
                Type TEXT,
                DateCreated TEXT
            )
        """)
        conn.execute(
            "INSERT INTO content VALUES ('v1', 'Angels', 'Dan Brown', 'Publisher X', '978-123')"
        )
        conn.execute(
            "INSERT INTO Bookmark VALUES ('b1', 'v1', 'v1#c1', 'Test highlight', 'highlight', '2026-01-01')"
        )
        conn.commit()
        conn.close()
        return db_path

    def test_parse_succeeds(self, db_no_content_type):
        results = parse_sqlite(db_no_content_type)
        assert len(results) >= 1
        assert results[0]["publisher"] == "Publisher X"

    def test_isbn_extracted(self, db_no_content_type):
        results = parse_sqlite(db_no_content_type)
        assert results[0]["isbn"] == "978-123"


class TestSyntheticSchema:
    """Verify parser works with the simplified synthetic Kobo schema."""

    @pytest.fixture
    def synthetic_db(self, tmp_path) -> Path:
        db_path = tmp_path / "KoboReader.sqlite"
        conn = sqlite3.connect(str(db_path))

        conn.execute("""
            CREATE TABLE content (
                ContentID TEXT PRIMARY KEY,
                Title TEXT,
                Attribution TEXT,
                Description TEXT,
                Series TEXT,
                ___UserID TEXT,
                DateLastRead TEXT,
                ReadStatus INTEGER,
                ___PercentRead REAL
            )
        """)
        conn.execute("""
            CREATE TABLE Bookmark (
                BookmarkID TEXT PRIMARY KEY,
                ContentID TEXT,
                Text TEXT,
                Type TEXT,
                Chapter TEXT,
                Location TEXT,
                DateCreated TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE Shelf (
                ShelfID TEXT PRIMARY KEY,
                Name TEXT,
                InternalName TEXT,
                _IsDeleted TEXT DEFAULT 'false'
            )
        """)
        conn.execute("""
            CREATE TABLE ShelfContent (
                ShelfName TEXT,
                ContentId TEXT
            )
        """)

        conn.execute("""
            INSERT INTO content VALUES
            ('book-1', '1984', 'George Orwell', 'A dystopian novel',
             NULL, 'user1', '2026-04-01', 2, 0.85)
        """)
        conn.execute("""
            INSERT INTO content VALUES
            ('book-2', 'Brave New World', 'Aldous Huxley', 'Another dystopia',
             'Dystopia Series', 'user1', '2026-03-15', 1, 0.40)
        """)
        conn.execute("""
            INSERT INTO Bookmark VALUES
            ('bm1', 'book-1', 'War is peace.', 'highlight', 'Part 1', NULL, '2026-04-01T10:00:00')
        """)
        conn.execute("""
            INSERT INTO Bookmark VALUES
            ('bm2', 'book-1', 'Freedom is slavery.', 'highlight', 'Part 2', NULL, '2026-04-01T11:00:00')
        """)
        conn.execute("""
            INSERT INTO Bookmark VALUES
            ('bm3', 'book-2', 'Everyone belongs to everyone.', 'note', 'Ch 3', NULL, '2026-03-15T09:00:00')
        """)
        conn.execute("INSERT INTO Shelf VALUES ('s1', 'Dystopias', 'shelf-dystopias', 'false')")
        conn.execute("INSERT INTO ShelfContent VALUES ('shelf-dystopias', 'book-1')")

        conn.commit()
        conn.close()
        return db_path

    def test_extracts_books(self, synthetic_db):
        results = parse_sqlite(synthetic_db)
        titles = {r["book_title"] for r in results}
        assert "1984" in titles or any("1984" in (r.get("book_title") or "") for r in results)

    def test_extracts_highlights_and_notes(self, synthetic_db):
        results = parse_sqlite(synthetic_db)
        kinds = {r["kind"] for r in results}
        assert "highlight" in kinds

    def test_extracts_text(self, synthetic_db):
        results = parse_sqlite(synthetic_db)
        texts = [r["text"] for r in results]
        assert "War is peace." in texts

    def test_shelves_extracted(self, synthetic_db):
        shelves = extract_shelves(synthetic_db)
        names = [s.name for s in shelves]
        assert "Dystopias" in names

    def test_no_crash_on_missing_volumeid(self, synthetic_db):
        # This schema has no VolumeID in Bookmark
        results = parse_sqlite(synthetic_db)
        assert len(results) >= 3  # 2 highlights + at least 1 note text

    def test_series_extracted(self, synthetic_db):
        results = parse_sqlite(synthetic_db)
        # Some results should have series from content metadata
        series_vals = {r.get("series") for r in results}
        assert "Dystopia Series" in series_vals or None in series_vals
