"""Tests for static HTML site exporter."""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from models.activity import ProgressSnapshot, ReadingSession
from models.annotation import Annotation
from models.book import Book
from models.insight import EvidenceItem, InsightCard
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


# ---------------------------------------------------------------------------
# Reading Intelligence in HTML export
# ---------------------------------------------------------------------------


def _sample_cards() -> list[InsightCard]:
    return [
        InsightCard(
            id="card1",
            title="Your Library at a Glance",
            category="Library Overview",
            summary="You have 3 books with 25 highlights across your library.",
            body="This is the detailed body text for the overview card.",
            evidence=[
                EvidenceItem(label="Books loaded", value="3"),
                EvidenceItem(label="Total highlights", value="25"),
            ],
            recommendation="Try exploring a new genre next.",
            priority_score=0.65,
            related_books=["Dune", "Neuromancer"],
        ),
        InsightCard(
            id="card2",
            title="Highlight-Heavy Reader",
            category="Highlight Behavior",
            summary="You highlight more than most readers.",
            priority_score=0.5,
            related_books=["Dune"],
        ),
    ]


class TestInsightsInHtmlExport:
    def test_insights_section_rendered(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert "Reading Intelligence" in content
            assert "Key Takeaways" in content

    def test_insight_cards_rendered(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert "Your Library at a Glance" in content
            assert "Highlight-Heavy Reader" in content

    def test_evidence_rendered(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert "Supporting Evidence" in content
            assert "Books loaded" in content
            assert "Total highlights" in content

    def test_recommendation_rendered(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert "Next Step" in content
            assert "Try exploring a new genre next" in content

    def test_related_books_pills(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert "ri-pill" in content
            assert "Dune" in content

    def test_category_grouping(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert "Library Overview" in content
            assert "Highlight Behavior" in content

    def test_priority_indicators(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert "MEDIUM" in content  # card1 at 0.65

    def test_no_insights_no_section(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=None)
            content = (Path(tmp) / "index.html").read_text()
            # The insight section heading should not appear without cards
            assert "Key Takeaways" not in content
            assert "Evidence-backed insights" not in content

    def test_empty_cards_no_section(self):
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=[])
            content = (Path(tmp) / "index.html").read_text()
            assert "Key Takeaways" not in content
            assert "Evidence-backed insights" not in content

    def test_body_text_rendered(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert "detailed body text for the overview card" in content

    def test_collapsible_details(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert "ri-detail" in content
            assert "View details" in content

    def test_insight_css_present(self):
        books = _make_books()
        cards = _sample_cards()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert ".ri-card" in content
            assert ".ri-takeaway-bar" in content

    def test_html_escapes_in_insights(self):
        books = _make_books()
        cards = [
            InsightCard(
                id="xss",
                title='Test <script>alert("xss")</script>',
                category="Library Overview",
                summary='Quotes "and" <tags> & ampersands',
                priority_score=0.5,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, insight_cards=cards)
            content = (Path(tmp) / "index.html").read_text()
            assert 'alert("xss")' not in content
            assert "&lt;script&gt;" in content

    def test_backward_compatible_without_insights(self):
        """Existing callers passing no insight_cards still work."""
        books = _make_books()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "Dune" in content
            assert "Fear is the mind-killer" in content


# ---------------------------------------------------------------------------
# Reading Activity charts in HTML export
# ---------------------------------------------------------------------------


def _make_books_with_activity():
    """Books with timestamps, sessions, and progress snapshots."""
    now = datetime.now()
    books = [
        Book(
            id="book1",
            title="Dune",
            author="Frank Herbert",
            source="test",
            read_percent=100.0,
            time_spent_reading=7200,
            annotations=[
                Annotation(
                    id="a1",
                    book_id="book1",
                    kind="highlight",
                    text="Fear is the mind-killer.",
                    chapter="Chapter 2",
                    source="test",
                    created_at=now - timedelta(days=5),
                ),
                Annotation(
                    id="a2",
                    book_id="book1",
                    kind="note",
                    text="The litany against fear.",
                    chapter="Chapter 2",
                    source="test",
                    created_at=now - timedelta(days=3),
                ),
                Annotation(
                    id="a3",
                    book_id="book1",
                    kind="highlight",
                    text="He who controls the spice.",
                    chapter="Chapter 5",
                    source="test",
                    created_at=now - timedelta(days=1),
                ),
            ],
        ),
        Book(
            id="book2",
            title="Neuromancer",
            author="William Gibson",
            source="test",
            read_percent=75.0,
            time_spent_reading=3600,
            annotations=[
                Annotation(
                    id="a4",
                    book_id="book2",
                    kind="highlight",
                    text="The sky above the port.",
                    chapter="Chapter 1",
                    source="test",
                    created_at=now - timedelta(days=2),
                ),
            ],
        ),
    ]
    sessions = [
        ReadingSession(
            book_id="book1",
            book_title="Dune",
            start_time=now - timedelta(days=5, hours=2),
            end_time=now - timedelta(days=5, hours=1),
            duration_minutes=60.0,
            start_percent=0.0,
            end_percent=0.3,
        ),
        ReadingSession(
            book_id="book1",
            book_title="Dune",
            start_time=now - timedelta(days=3, hours=1),
            end_time=now - timedelta(days=3),
            duration_minutes=60.0,
            start_percent=0.3,
            end_percent=0.7,
        ),
        ReadingSession(
            book_id="book2",
            book_title="Neuromancer",
            start_time=now - timedelta(days=2, hours=1),
            end_time=now - timedelta(days=2),
            duration_minutes=60.0,
        ),
    ]
    snapshots = [
        ProgressSnapshot(book_id="book1", book_title="Dune", percent=10.0, recorded_at=now - timedelta(days=5)),
        ProgressSnapshot(book_id="book1", book_title="Dune", percent=50.0, recorded_at=now - timedelta(days=3)),
        ProgressSnapshot(book_id="book1", book_title="Dune", percent=100.0, recorded_at=now - timedelta(days=1)),
        ProgressSnapshot(book_id="book2", book_title="Neuromancer", percent=25.0, recorded_at=now - timedelta(days=4)),
        ProgressSnapshot(book_id="book2", book_title="Neuromancer", percent=75.0, recorded_at=now - timedelta(days=2)),
    ]
    return books, sessions, snapshots


class TestActivityInHtmlExport:
    def test_activity_section_rendered(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "Reading Activity" in content

    def test_annotation_timeline_chart(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "Annotation Timeline" in content

    def test_day_of_week_chart(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "Day of Week" in content
            assert "Most active:" in content

    def test_time_of_day_chart(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "Time of Day" in content
            assert "Peak:" in content

    def test_reading_time_by_book_chart(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "Reading Time by Book" in content

    def test_reading_sessions_chart(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "Reading Sessions" in content

    def test_progress_curves_chart(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "Reading Progress Over Time" in content

    def test_activity_insight_text(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "activity-insight" in content
            assert "Average reading time per book" in content

    def test_svg_charts_present(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            # SVG elements from activity charts
            svg_count = content.count("<svg")
            assert svg_count >= 4  # annotation timeline + dow + tod + progress

    def test_no_activity_without_timestamps(self):
        """Books without timestamps produce no activity section."""
        books = [
            Book(
                id="plain",
                title="Plain Book",
                author="Author",
                source="test",
                annotations=[
                    Annotation(id="p1", book_id="plain", kind="highlight",
                               text="No timestamp.", source="test"),
                ],
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "Reading Activity" not in content

    def test_legend_for_sessions(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "legend-row" in content
            assert "legend-dot" in content

    def test_activity_css_present(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert ".activity-section" in content
            assert ".activity-grid" in content
            assert ".activity-insight" in content

    def test_progress_chart_shows_book_titles(self):
        """Progress chart labels should use book titles, not raw IDs."""
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            # Titles from snapshots should appear in chart, not raw IDs
            assert "Dune" in content
            assert "Neuromancer" in content

    def test_notes_per_book_chart(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "Notes per Book" in content

    def test_active_days_hero_stat(self):
        books, sessions, snapshots = _make_books_with_activity()
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "Active Days" in content

    def test_hero_stat_compact_class(self):
        """Long numeric values should get the compact CSS class."""
        books, sessions, snapshots = _make_books_with_activity()
        # Give books large word counts to trigger compact class
        for b in books:
            b.word_count = 1_500_000
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, sessions=sessions, snapshots=snapshots)
            content = (Path(tmp) / "index.html").read_text()
            assert "value compact" in content

    def test_pill_wrapping_css(self):
        """Pill cards have word-break for large numbers."""
        books = [
            Book(
                id="bignum",
                title="Big Book",
                author="Author",
                source="test",
                word_count=1234567,
                page_turns=987654,
                annotations=[
                    Annotation(id="b1", book_id="bignum", kind="highlight",
                               text="test", source="test"),
                ],
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text()
            assert "word-break: break-word" in content
            assert "1,234,567 words" in content
            assert "987,654 pages turned" in content
