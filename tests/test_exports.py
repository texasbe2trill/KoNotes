"""Tests for export services: JSON, TXT, and Markdown footer."""
from __future__ import annotations

import json

import pytest

from models.annotation import Annotation
from models.book import Book
from services.export_json import export_book_json
from services.export_markdown import export_book_markdown
from services.export_text import export_book_text


def _make_book() -> Book:
    return Book(
        id="test123",
        title="Test Book",
        author="Test Author",
        source="test",
        annotations=[
            Annotation(
                id="a1",
                book_id="test123",
                kind="highlight",
                text="Important passage.",
                chapter="Chapter 1",
                location="10%",
                source="test",
            ),
            Annotation(
                id="a2",
                book_id="test123",
                kind="note",
                text="My note about this.",
                chapter="Chapter 2",
                source="test",
            ),
        ],
        shelves=["favorites"],
        publisher="Test Publisher",
        isbn="978-0-123456-78-9",
    )


class TestExportJSON:
    def test_valid_json(self):
        result = export_book_json(_make_book())
        data = json.loads(result)
        assert data["title"] == "Test Book"

    def test_annotations_present(self):
        data = json.loads(export_book_json(_make_book()))
        assert len(data["annotations"]) == 2

    def test_footer_present(self):
        data = json.loads(export_book_json(_make_book()))
        assert "KoNotes" in data["footer"]
        assert "Kobo community" in data["footer"]

    def test_meta_fields(self):
        data = json.loads(export_book_json(_make_book()))
        assert data["meta"]["publisher"] == "Test Publisher"
        assert data["meta"]["isbn"] == "978-0-123456-78-9"
        assert data["meta"]["shelves"] == ["favorites"]

    def test_telemetry_block(self):
        data = json.loads(export_book_json(_make_book()))
        assert "telemetry" in data
        assert data["telemetry"]["total_highlights"] == 1
        assert data["telemetry"]["total_notes"] == 1

    def test_exporter_block(self):
        data = json.loads(export_book_json(_make_book()))
        assert "exporter" in data
        assert data["exporter"]["tool"] == "KoNotes"
        assert data["exporter"]["version"] == "0.5.0"


class TestExportText:
    def test_contains_title(self):
        result = export_book_text(_make_book())
        assert "Test Book" in result

    def test_contains_highlights_section(self):
        result = export_book_text(_make_book())
        assert "HIGHLIGHTS" in result

    def test_contains_notes_section(self):
        result = export_book_text(_make_book())
        assert "NOTES" in result

    def test_footer_present(self):
        result = export_book_text(_make_book())
        assert "Kobo community" in result
        assert "KoNotes" in result


class TestExportMarkdownFooter:
    def test_footer_updated(self):
        result = export_book_markdown(_make_book())
        assert "Kobo community" in result
        assert "KoNotes" in result


class TestExportFooterConsistency:
    """All export formats must use 'Made with love' and include GitHub link."""

    def test_json_footer_love(self):
        data = json.loads(export_book_json(_make_book()))
        assert "Made with love" in data["footer"]
        assert "github.com/texasbe2trill/KoNotes" in data["footer"]

    def test_text_footer_love(self):
        result = export_book_text(_make_book())
        assert "Made with love" in result
        assert "github.com/texasbe2trill/KoNotes" in result

    def test_markdown_footer_love(self):
        result = export_book_markdown(_make_book())
        assert "Made with love" in result
        assert "github.com/texasbe2trill/KoNotes" in result
