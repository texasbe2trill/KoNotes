"""Tests for CSV export service."""
from __future__ import annotations

import csv
import io

import pytest

from models.annotation import Annotation
from models.book import Book
from services.export_csv import export_book_csv


def _make_book() -> Book:
    return Book(
        id="csv1",
        title="CSV Test Book",
        author="CSV Author",
        source="test",
        annotations=[
            Annotation(
                id="a1",
                book_id="csv1",
                kind="highlight",
                text="An important passage.",
                chapter="Chapter 1",
                location="10%",
                source="test",
            ),
            Annotation(
                id="a2",
                book_id="csv1",
                kind="note",
                text="My personal note.",
                chapter="Chapter 2",
                source="test",
            ),
        ],
    )


class TestExportCSV:
    def test_valid_csv(self):
        result = export_book_csv(_make_book())
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 3  # header + 2 annotations

    def test_header_row(self):
        result = export_book_csv(_make_book())
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert "title" in header
        assert "author" in header
        assert "kind" in header
        assert "text" in header
        assert "chapter" in header

    def test_annotation_data(self):
        result = export_book_csv(_make_book())
        reader = csv.reader(io.StringIO(result))
        next(reader)  # skip header
        rows = list(reader)
        titles = [r[0] for r in rows]
        assert all(t == "CSV Test Book" for t in titles)
        kinds = [r[2] for r in rows]
        assert "highlight" in kinds
        assert "note" in kinds

    def test_text_preserved(self):
        result = export_book_csv(_make_book())
        assert "An important passage." in result
        assert "My personal note." in result

    def test_empty_annotations(self):
        book = Book(id="empty", title="Empty", source="test", annotations=[])
        result = export_book_csv(book)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1  # header only

    def test_commas_and_quotes_in_text(self):
        book = Book(
            id="special",
            title='Book "With" Quotes',
            author="Author, Jr.",
            source="test",
            annotations=[
                Annotation(
                    id="s1",
                    book_id="special",
                    kind="highlight",
                    text='He said, "hello, world"',
                    source="test",
                ),
            ],
        )
        result = export_book_csv(book)
        reader = csv.reader(io.StringIO(result))
        next(reader)
        row = next(reader)
        assert row[0] == 'Book "With" Quotes'
        assert row[1] == "Author, Jr."
        assert row[3] == 'He said, "hello, world"'

    def test_chapter_and_location(self):
        result = export_book_csv(_make_book())
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        ch_idx = header.index("chapter")
        loc_idx = header.index("location")
        row = next(reader)
        assert row[ch_idx] == "Chapter 1"
        assert row[loc_idx] == "10%"


class TestCSVExportCLI:
    """CSV should be available as a CLI export format."""

    def test_csv_format_in_choices(self):
        from main import _build_parser

        parser = _build_parser()
        export_action = None
        for action in parser._subparsers._group_actions:  # type: ignore[union-attr]
            for name, sub in action.choices.items():  # type: ignore[union-attr]
                if name == "export":
                    for a in sub._actions:
                        if hasattr(a, "choices") and a.dest == "format":
                            export_action = a
                            break
        assert export_action is not None
        assert "csv" in export_action.choices
