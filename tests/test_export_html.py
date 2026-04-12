"""Tests for static HTML site exporter."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from models.annotation import Annotation
from models.book import Book
from services.export_html import export_static_site


def _make_books() -> list[Book]:
    return [
        Book(
            id="book1",
            title="Dune",
            author="Frank Herbert",
            source="test",
            read_percent=100.0,
            shelves=["sci-fi"],
            publisher="Ace Books",
            isbn="978-0-441-17271-9",
            annotations=[
                Annotation(
                    id="a1",
                    book_id="book1",
                    kind="highlight",
                    text="Fear is the mind-killer.",
                    chapter="Chapter 2",
                    source="test",
                ),
                Annotation(
                    id="a2",
                    book_id="book1",
                    kind="note",
                    text="The litany against fear is a powerful concept.",
                    chapter="Chapter 2",
                    source="test",
                ),
                Annotation(
                    id="a3",
                    book_id="book1",
                    kind="highlight",
                    text="He who controls the spice controls the universe.",
                    chapter="Chapter 5",
                    source="test",
                ),
            ],
        ),
        Book(
            id="book2",
            title="Neuromancer",
            author="William Gibson",
            source="test",
            read_percent=75.0,
            annotations=[
                Annotation(
                    id="a4",
                    book_id="book2",
                    kind="highlight",
                    text="The sky above the port was the color of television, tuned to a dead channel.",
                    chapter="Chapter 1",
                    source="test",
                ),
            ],
        ),
    ]


class TestExportStaticSite:
    def test_creates_index(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            index = Path(tmp) / "index.html"
            assert index.exists()
            content = index.read_text()
            assert "KoNotes" in content
            assert "Dune" in content
            assert "Neuromancer" in content

    def test_single_file_output(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            files = list(Path(tmp).rglob("*.html"))
            assert len(files) == 1
            assert files[0].name == "index.html"

    def test_page_contains_annotations(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "Fear is the mind-killer" in content
            assert "Chapter 2" in content
            assert "Chapter 5" in content

    def test_index_has_stats(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            # 2 books, 4 annotations, 3 highlights
            assert ">2<" in content  # books count
            assert ">4<" in content  # annotations
            assert ">3<" in content  # highlights

    def test_page_has_metadata(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "Frank Herbert" in content
            assert "Ace Books" in content
            assert "978-0-441-17271-9" in content
            assert "100%" in content
            assert "sci-fi" in content

    def test_footer_present(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "Made with love for the Kobo community" in content

    def test_table_of_contents(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "Table of Contents" in content
            assert 'href="#dune"' in content
            assert 'href="#neuromancer"' in content

    def test_back_to_top_links(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert 'href="#top"' in content

    def test_empty_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site([], tmp)
            index = Path(tmp) / "index.html"
            assert index.exists()
            content = index.read_text()
            assert ">0<" in content  # 0 books

    def test_book_no_annotations(self):
        books = [
            Book(id="empty", title="Empty Book", author="Nobody", source="test", annotations=[])
        ]
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "No annotations for this book" in content

    def test_html_escapes_special_chars(self):
        books = [
            Book(
                id="xss",
                title='Book <script>alert("xss")</script>',
                author="O'Brien & Co.",
                source="test",
                annotations=[
                    Annotation(
                        id="x1",
                        book_id="xss",
                        kind="highlight",
                        text='He said "hello" & <goodbye>',
                        source="test",
                    )
                ],
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            # User-supplied XSS payload must be escaped
            assert 'alert("xss")' not in content
            assert "&lt;script&gt;" in content

    def test_returns_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = export_static_site([], tmp)
            assert result == Path(tmp)

    def test_notes_rendered_separately(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "Highlights (2)" in content
            assert "Notes (1)" in content
            assert "litany against fear" in content

    def test_hero_stats_section(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "hero-stat" in content
            assert "Highlights" in content
            assert "Notes" in content
            assert "Annotations" in content

    def test_progress_bar_rendered(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "progress-bar" in content
            assert "100% read" in content
            assert "75% read" in content

    def test_book_stat_pills(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "pill hl" in content
            assert "pill note" in content
            assert "pill shelf" in content

    def test_reading_time_display(self):
        books = [
            Book(
                id="b1",
                title="Timed Book",
                author="Author",
                source="test",
                time_spent_reading=7200,
                annotations=[
                    Annotation(id="a1", book_id="b1", kind="highlight", text="test", source="test"),
                ],
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "2h" in content
            assert "Reading Time" in content

    def test_donut_chart_rendered(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "<svg" in content
            assert "Annotation Breakdown" in content

    def test_star_rating_pill(self):
        books = [
            Book(
                id="rated",
                title="Rated Book",
                author="Author",
                source="test",
                rating=4,
                annotations=[
                    Annotation(id="r1", book_id="rated", kind="highlight", text="good stuff", source="test"),
                ],
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            # 4 filled + 1 empty star
            assert "★★★★☆" in content

    def test_toc_highlight_count_badges(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "hl-count" in content


class TestExportCLI:
    def test_export_html_subcommand(self):
        """Verify the CLI parser recognises the export-html subcommand."""
        from main import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["export-html", "fake.sqlite", "-o", "/tmp/out"])
        assert args.command == "export-html"
        assert args.output == Path("/tmp/out")
