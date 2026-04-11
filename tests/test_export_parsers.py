"""Tests for export file parsers (HTML, TXT, Markdown)."""
from __future__ import annotations

from pathlib import Path

import pytest

from parser.export_parsers import (
    HTMLExportParser,
    MarkdownExportParser,
    TXTExportParser,
    get_parser_for_extension,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# HTML parser
# ---------------------------------------------------------------------------

class TestHTMLExportParser:
    parser = HTMLExportParser()

    def test_extracts_book_title(self):
        content = (FIXTURES / "sample_export.html").read_text()
        results = self.parser.parse(content)
        assert results, "Expected at least one annotation"
        assert results[0]["book_title"] == "Dune"

    def test_extracts_author(self):
        content = (FIXTURES / "sample_export.html").read_text()
        results = self.parser.parse(content)
        assert results[0]["author"] == "Frank Herbert"

    def test_highlight_kind(self):
        content = (FIXTURES / "sample_export.html").read_text()
        results = self.parser.parse(content)
        highlights = [r for r in results if r["kind"] == "highlight"]
        assert len(highlights) >= 2

    def test_note_kind(self):
        content = (FIXTURES / "sample_export.html").read_text()
        results = self.parser.parse(content)
        notes = [r for r in results if r["kind"] == "note"]
        assert len(notes) >= 1

    def test_text_not_empty(self):
        content = (FIXTURES / "sample_export.html").read_text()
        results = self.parser.parse(content)
        for r in results:
            assert r["text"].strip(), "Annotation text should not be empty"

    def test_fallback_on_plain_html(self):
        """Parser should fall back gracefully for minimal HTML."""
        minimal = "<html><head><title>My Book</title></head><body><p>A highlight.</p></body></html>"
        results = self.parser.parse(minimal)
        assert any(r["text"] == "A highlight." for r in results)


# ---------------------------------------------------------------------------
# TXT parser
# ---------------------------------------------------------------------------

class TestTXTExportParser:
    parser = TXTExportParser()

    def test_extracts_book_title(self):
        content = (FIXTURES / "sample_export.txt").read_text()
        results = self.parser.parse(content)
        assert results[0]["book_title"] == "The Pragmatic Programmer"

    def test_extracts_author(self):
        content = (FIXTURES / "sample_export.txt").read_text()
        results = self.parser.parse(content)
        assert results[0]["author"] == "Andrew Hunt and David Thomas"

    def test_highlight_count(self):
        content = (FIXTURES / "sample_export.txt").read_text()
        results = self.parser.parse(content)
        highlights = [r for r in results if r["kind"] == "highlight"]
        assert len(highlights) == 3

    def test_note_count(self):
        content = (FIXTURES / "sample_export.txt").read_text()
        results = self.parser.parse(content)
        notes = [r for r in results if r["kind"] == "note"]
        assert len(notes) == 1

    def test_chapter_extracted(self):
        content = (FIXTURES / "sample_export.txt").read_text()
        results = self.parser.parse(content)
        assert any(r.get("chapter") for r in results)

    def test_location_extracted(self):
        content = (FIXTURES / "sample_export.txt").read_text()
        results = self.parser.parse(content)
        assert any(r.get("location") for r in results)


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

class TestMarkdownExportParser:
    parser = MarkdownExportParser()

    def test_extracts_book_title(self):
        content = (FIXTURES / "sample_export.md").read_text()
        results = self.parser.parse(content)
        assert results[0]["book_title"] == "Meditations"

    def test_extracts_author(self):
        content = (FIXTURES / "sample_export.md").read_text()
        results = self.parser.parse(content)
        assert results[0]["author"] == "Marcus Aurelius"

    def test_highlight_kind(self):
        content = (FIXTURES / "sample_export.md").read_text()
        results = self.parser.parse(content)
        highlights = [r for r in results if r["kind"] == "highlight"]
        assert len(highlights) == 4

    def test_note_kind(self):
        content = (FIXTURES / "sample_export.md").read_text()
        results = self.parser.parse(content)
        notes = [r for r in results if r["kind"] == "note"]
        assert len(notes) == 2

    def test_chapter_set(self):
        content = (FIXTURES / "sample_export.md").read_text()
        results = self.parser.parse(content)
        assert results[0]["chapter"] == "Book Two"

    def test_location_extracted(self):
        content = (FIXTURES / "sample_export.md").read_text()
        results = self.parser.parse(content)
        highlights = [r for r in results if r["kind"] == "highlight"]
        assert any(r.get("location") for r in highlights)


# ---------------------------------------------------------------------------
# Parser registry
# ---------------------------------------------------------------------------

class TestGetParserForExtension:
    def test_html_extension(self):
        assert isinstance(get_parser_for_extension(".html"), HTMLExportParser)

    def test_htm_extension(self):
        assert isinstance(get_parser_for_extension(".htm"), HTMLExportParser)

    def test_txt_extension(self):
        assert isinstance(get_parser_for_extension(".txt"), TXTExportParser)

    def test_md_extension(self):
        assert isinstance(get_parser_for_extension(".md"), MarkdownExportParser)

    def test_unknown_extension(self):
        assert get_parser_for_extension(".pdf") is None

    def test_case_insensitive(self):
        assert get_parser_for_extension(".HTML") is not None
