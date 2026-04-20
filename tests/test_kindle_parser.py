"""Tests for the Kindle My Clippings.txt parser."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from parser.export_parsers import get_parser_for_extension
from parser.kindle_parser import KindleClippingsParser, is_kindle_clippings
from parser.normalizer import normalize

FIXTURES = Path(__file__).parent / "fixtures"
CLIPPINGS_FILE = FIXTURES / "kindle_clippings.txt"


@pytest.fixture()
def clippings_content() -> str:
    return CLIPPINGS_FILE.read_text(encoding="utf-8", errors="replace")


@pytest.fixture()
def parsed(clippings_content: str) -> list[dict]:
    return KindleClippingsParser().parse(clippings_content)


# ---------------------------------------------------------------------------
# Detection heuristic
# ---------------------------------------------------------------------------

class TestIsKindleClippings:
    def test_detects_kindle_format(self, clippings_content: str):
        assert is_kindle_clippings(clippings_content)

    def test_rejects_kobo_txt(self):
        kobo = FIXTURES / "sample_export.txt"
        content = kobo.read_text(encoding="utf-8")
        assert not is_kindle_clippings(content)

    def test_rejects_plain_text(self):
        assert not is_kindle_clippings("Just some random text.")

    def test_requires_separator(self):
        # Has metadata line but no separator
        content = "- Your Highlight on page 1 | Location 10 | Added on Monday, January 1, 2024 12:00:00 PM\nsome text"
        assert not is_kindle_clippings(content)


# ---------------------------------------------------------------------------
# Parser pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_auto_detects_kindle_txt(self, clippings_content: str):
        parser = get_parser_for_extension(".txt", content=clippings_content)
        assert isinstance(parser, KindleClippingsParser)

    def test_kobo_txt_falls_through(self):
        kobo = FIXTURES / "sample_export.txt"
        content = kobo.read_text(encoding="utf-8")
        parser = get_parser_for_extension(".txt", content=content)
        assert parser is not None
        assert parser.source_name == "kobo_txt"

    def test_no_content_falls_through(self):
        parser = get_parser_for_extension(".txt")
        assert parser is not None
        assert parser.source_name == "kobo_txt"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class TestKindleClippingsParser:
    def test_source_name(self):
        assert KindleClippingsParser().source_name == "kindle"

    def test_parses_all_entries(self, parsed: list[dict]):
        # 8 entries in fixture: 1 bookmark (skipped), 1 highlight, 1 underline,
        # 1 note, 2 Building Resilient highlights, 1 Data-Driven highlight,
        # 1 duplicate Data-Driven highlight (skipped) → 6 unique
        assert len(parsed) == 6

    def test_extracts_book_title(self, parsed: list[dict]):
        titles = {e["book_title"] for e in parsed}
        assert "The Art of Clear Thinking (Synthetic Press)" in titles
        assert "Building Resilient Systems" in titles
        assert "Data-Driven Decisions" in titles

    def test_extracts_author(self, parsed: list[dict]):
        authors = {e["author"] for e in parsed}
        assert "Torres, David" in authors
        assert "Park, Sonia" in authors
        assert "Nakamura, Kenji" in authors

    def test_highlight_kind(self, parsed: list[dict]):
        highlights = [e for e in parsed if e["kind"] == "highlight"]
        # 1 highlight + 1 underline (→ highlight) + 2 AI Eng + 1 Football = 5
        assert len(highlights) == 5

    def test_note_kind(self, parsed: list[dict]):
        notes = [e for e in parsed if e["kind"] == "note"]
        assert len(notes) == 1
        assert "important for the chapter review" in notes[0]["text"]

    def test_bookmarks_skipped(self, parsed: list[dict]):
        bookmarks = [e for e in parsed if e["kind"] == "bookmark"]
        assert len(bookmarks) == 0

    def test_underline_becomes_highlight(self, parsed: list[dict]):
        underlines = [e for e in parsed if e["kind"] == "underline"]
        assert len(underlines) == 0

    def test_text_not_empty(self, parsed: list[dict]):
        for e in parsed:
            assert e["text"].strip(), "Annotation text should not be empty"

    def test_extracts_page(self, parsed: list[dict]):
        # All entries in fixture have page numbers
        for e in parsed:
            assert e.get("page") is not None

    def test_extracts_location(self, parsed: list[dict]):
        for e in parsed:
            assert e.get("location") is not None

    def test_extracts_timestamp(self, parsed: list[dict]):
        for e in parsed:
            assert isinstance(e.get("created_at"), datetime)

    def test_deduplicates(self, clippings_content: str):
        """The Data-Driven Decisions highlight appears twice — only one should survive."""
        parser = KindleClippingsParser()
        results = parser.parse(clippings_content)
        data_driven = [e for e in results if "Data-Driven" in e["book_title"]]
        assert len(data_driven) == 1

    def test_bom_handling(self):
        """Parser should handle BOM-prefixed lines."""
        content = (
            "\uFEFFSome Book (Author Name)\n"
            "- Your Highlight on page 1 | Location 10-12 | Added on Monday, January 1, 2024 12:00:00 PM\n"
            "\n"
            "Highlighted text here.\n"
            "=========="
        )
        results = KindleClippingsParser().parse(content)
        assert len(results) == 1
        assert results[0]["book_title"] == "Some Book"
        assert results[0]["author"] == "Author Name"

    def test_multiline_highlight(self):
        content = (
            "My Book (Author)\n"
            "- Your Highlight on page 5 | Location 50-55 | Added on Tuesday, February 2, 2024 3:00:00 PM\n"
            "\n"
            "First line of highlight.\n"
            "Second line of highlight.\n"
            "=========="
        )
        results = KindleClippingsParser().parse(content)
        assert len(results) == 1
        assert "First line" in results[0]["text"]
        assert "Second line" in results[0]["text"]

    def test_title_without_author(self):
        content = (
            "Untitled Document\n"
            "- Your Highlight on page 1 | Location 5 | Added on Wednesday, March 3, 2024 1:00:00 PM\n"
            "\n"
            "Some text.\n"
            "=========="
        )
        results = KindleClippingsParser().parse(content)
        assert len(results) == 1
        assert results[0]["book_title"] == "Untitled Document"
        assert results[0]["author"] is None


# ---------------------------------------------------------------------------
# Normalizer integration
# ---------------------------------------------------------------------------

class TestNormalizerIntegration:
    def test_normalizes_to_books(self, parsed: list[dict]):
        books = normalize(parsed, source="kindle")
        assert len(books) == 3  # 3 distinct books

    def test_book_has_annotations(self, parsed: list[dict]):
        books = normalize(parsed, source="kindle")
        for book in books:
            assert len(book.annotations) >= 1

    def test_book_source_is_kindle(self, parsed: list[dict]):
        books = normalize(parsed, source="kindle")
        for book in books:
            assert book.source == "kindle"

    def test_annotation_ids_unique(self, parsed: list[dict]):
        books = normalize(parsed, source="kindle")
        all_ids = [a.id for b in books for a in b.annotations]
        assert len(all_ids) == len(set(all_ids))

    def test_missing_metadata_graceful(self, parsed: list[dict]):
        """Books from Kindle won't have ISBN, publisher, etc."""
        books = normalize(parsed, source="kindle")
        for book in books:
            # These are optional — should be None, not crash
            assert book.isbn is None
            assert book.publisher is None
