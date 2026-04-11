"""Tests for the normalizer: raw dicts → Book / Annotation models."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from models.annotation import Annotation
from models.book import Book
from parser.normalizer import normalize

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(
    book_title: str = "Test Book",
    author: str | None = "Test Author",
    kind: str = "highlight",
    text: str = "Sample text",
    chapter: str | None = None,
    location: str | None = None,
    created_at: str | None = None,
) -> dict:
    return {
        "book_title": book_title,
        "author": author,
        "kind": kind,
        "text": text,
        "chapter": chapter,
        "location": location,
        "created_at": created_at,
    }


# ---------------------------------------------------------------------------
# Basic normalization
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_returns_list_of_books(self):
        raw = [_raw()]
        books = normalize(raw, "test")
        assert isinstance(books, list)
        assert all(isinstance(b, Book) for b in books)

    def test_single_book_produced(self):
        raw = [_raw(), _raw(text="Another highlight")]
        books = normalize(raw, "test")
        assert len(books) == 1

    def test_multiple_books(self):
        raw = [_raw(book_title="Book A"), _raw(book_title="Book B")]
        books = normalize(raw, "test")
        assert len(books) == 2

    def test_book_title_set(self):
        raw = [_raw(book_title="Dune")]
        books = normalize(raw, "test")
        assert books[0].title == "Dune"

    def test_book_author_set(self):
        raw = [_raw(author="Frank Herbert")]
        books = normalize(raw, "test")
        assert books[0].author == "Frank Herbert"

    def test_book_author_none_when_missing(self):
        raw = [_raw(author=None)]
        books = normalize(raw, "test")
        assert books[0].author is None

    def test_source_set(self):
        raw = [_raw()]
        books = normalize(raw, "kobo_html")
        assert books[0].source == "kobo_html"

    def test_annotations_populated(self):
        raw = [_raw(), _raw(text="Second highlight")]
        books = normalize(raw, "test")
        assert len(books[0].annotations) == 2

    def test_empty_input(self):
        books = normalize([], "test")
        assert books == []


# ---------------------------------------------------------------------------
# Annotation model
# ---------------------------------------------------------------------------

class TestAnnotationModel:
    def _get_annotation(self, **kwargs) -> Annotation:
        books = normalize([_raw(**kwargs)], "test")
        return books[0].annotations[0]

    def test_kind_highlight(self):
        ann = self._get_annotation(kind="highlight")
        assert ann.kind == "highlight"

    def test_kind_note(self):
        ann = self._get_annotation(kind="note")
        assert ann.kind == "note"

    def test_unknown_kind_coerced(self):
        ann = self._get_annotation(kind="bookmark")
        assert ann.kind == "unknown"

    def test_text_set(self):
        ann = self._get_annotation(text="Philosophy matters.")
        assert ann.text == "Philosophy matters."

    def test_chapter_set(self):
        ann = self._get_annotation(chapter="Chapter 1")
        assert ann.chapter == "Chapter 1"

    def test_location_set(self):
        ann = self._get_annotation(location="45%")
        assert ann.location == "45%"

    def test_created_at_parsed_from_string(self):
        ann = self._get_annotation(created_at="2024-03-15T10:30:00")
        assert isinstance(ann.created_at, datetime)
        assert ann.created_at.year == 2024

    def test_created_at_none_for_invalid(self):
        ann = self._get_annotation(created_at="not-a-date")
        assert ann.created_at is None

    def test_annotation_id_is_stable(self):
        """Same book + text should always yield the same annotation id."""
        books1 = normalize([_raw(text="Stable text")], "test")
        books2 = normalize([_raw(text="Stable text")], "test")
        assert books1[0].annotations[0].id == books2[0].annotations[0].id

    def test_book_id_is_stable(self):
        books1 = normalize([_raw(book_title="Stable", author="Author")], "test")
        books2 = normalize([_raw(book_title="Stable", author="Author")], "test")
        assert books1[0].id == books2[0].id

    def test_book_id_differs_for_different_books(self):
        books = normalize([_raw(book_title="Book A"), _raw(book_title="Book B")], "test")
        assert books[0].id != books[1].id


# ---------------------------------------------------------------------------
# Integration: parse fixtures → normalize
# ---------------------------------------------------------------------------

class TestNormalizeFromFixtures:
    def test_html_fixture_produces_books(self):
        from parser.export_parsers import HTMLExportParser
        content = (FIXTURES / "sample_export.html").read_text()
        raw = HTMLExportParser().parse(content)
        books = normalize(raw, "kobo_html")
        assert len(books) == 1
        assert books[0].title == "Dune"
        assert len(books[0].annotations) >= 3

    def test_txt_fixture_produces_books(self):
        from parser.export_parsers import TXTExportParser
        content = (FIXTURES / "sample_export.txt").read_text()
        raw = TXTExportParser().parse(content)
        books = normalize(raw, "kobo_txt")
        assert len(books) == 1
        # 4 explicit annotations + 1 parsed from the header block
        assert len(books[0].annotations) >= 4

    def test_md_fixture_produces_books(self):
        from parser.export_parsers import MarkdownExportParser
        content = (FIXTURES / "sample_export.md").read_text()
        raw = MarkdownExportParser().parse(content)
        books = normalize(raw, "kobo_md")
        assert len(books) == 1
        assert books[0].title == "Meditations"
        assert books[0].author == "Marcus Aurelius"
        assert len(books[0].annotations) == 6
