"""Tests for the stabilization/bug-fix pass.

Covers:
- _parse_ts() numeric timestamp handling
- Template summary paragraph structure
- HTML export vocabulary section
- Torchvision graceful error handling
- Safe device copy helper
"""
from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.annotation import Annotation
from models.book import Book
from models.insight import InsightCard, ThemeCluster
from models.vocabulary import WordLookup
from parser.sqlite_parser import _parse_ts
from services.export_html import export_static_site
from services.summaries import generate_template_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(
    title: str = "Test Book",
    author: str = "Test Author",
    time_spent_reading: int | None = None,
    read_percent: float | None = None,
    rating: int | None = None,
) -> Book:
    return Book(
        id=f"book-{title.lower().replace(' ', '-')}",
        title=title,
        author=author,
        source="test",
        annotations=[
            Annotation(
                id=f"h{i}",
                book_id="book-1",
                kind="highlight",
                text=f"Highlight number {i} about interesting topic {i % 3}",
                chapter=f"Chapter {i // 2 + 1}",
                source="test",
            )
            for i in range(6)
        ],
        time_spent_reading=time_spent_reading,
        read_percent=read_percent,
        rating=rating,
    )


def _make_word_lookups(n: int = 5) -> list[WordLookup]:
    words = ["ephemeral", "ubiquitous", "serendipity", "melancholy", "paradox",
             "quintessence", "luminous", "ethereal", "resonance", "enigma"]
    return [
        WordLookup(
            word=words[i % len(words)],
            book_id="book-1",
            book_title="Test Book",
            language="en",
            looked_up_at=datetime(2024, 6, 1 + i),
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# _parse_ts numeric timestamps
# ---------------------------------------------------------------------------


class TestParseTimestampNumeric:
    def test_integer_epoch(self):
        # 2024-01-15 12:00:00 UTC-ish
        result = _parse_ts(1705320000)
        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2024

    def test_float_epoch(self):
        result = _parse_ts(1705320000.123)
        assert result is not None
        assert isinstance(result, datetime)

    def test_numeric_string_epoch(self):
        result = _parse_ts("1705320000")
        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2024

    def test_numeric_string_with_decimal(self):
        result = _parse_ts("1705320000.5")
        assert result is not None
        assert isinstance(result, datetime)

    def test_zero_returns_none(self):
        result = _parse_ts(0)
        assert result is None

    def test_negative_returns_none(self):
        result = _parse_ts(-100)
        assert result is None

    def test_none_returns_none(self):
        assert _parse_ts(None) is None

    def test_iso_string_still_works(self):
        result = _parse_ts("2024-01-15T12:00:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1

    def test_datetime_passthrough(self):
        dt = datetime(2024, 3, 15)
        assert _parse_ts(dt) is dt


# ---------------------------------------------------------------------------
# Template summary paragraph structure
# ---------------------------------------------------------------------------


class TestTemplateSummaryParagraphs:
    def test_summary_has_paragraph_breaks(self):
        book = _make_book()
        result = generate_template_summary(book)
        assert "\n\n" in result.summary

    def test_summary_multiple_paragraphs(self):
        book = _make_book(time_spent_reading=7200, read_percent=85.0, rating=4)
        themes = [
            ThemeCluster(
                label="Technology",
                size=3,
                representative_text="AI and machine learning advances",
                highlight_ids=["h0", "h1", "h2"],
            )
        ]
        result = generate_template_summary(book, themes=themes)
        paragraphs = result.summary.split("\n\n")
        assert len(paragraphs) >= 3  # opening + themes + engagement at minimum

    def test_summary_includes_highlight_quotes(self):
        book = _make_book()
        result = generate_template_summary(book)
        assert "Notable highlights" in result.summary

    def test_summary_method_is_template(self):
        book = _make_book()
        result = generate_template_summary(book)
        assert result.method == "template"

    def test_summary_opening_mentions_book(self):
        book = _make_book(title="Dune")
        result = generate_template_summary(book)
        assert "Dune" in result.summary

    def test_summary_with_themes(self):
        book = _make_book()
        themes = [
            ThemeCluster(
                label="Nature",
                size=2,
                representative_text="The forest canopy",
                highlight_ids=["h0", "h1"],
            )
        ]
        result = generate_template_summary(book, themes=themes)
        assert "Key themes" in result.summary
        assert "Nature" in result.themes

    def test_summary_with_reading_time(self):
        book = _make_book(time_spent_reading=3700)
        result = generate_template_summary(book)
        assert "1h" in result.summary

    def test_summary_with_rating(self):
        book = _make_book(rating=5)
        result = generate_template_summary(book)
        assert "5 out of 5" in result.summary


# ---------------------------------------------------------------------------
# HTML export vocabulary section
# ---------------------------------------------------------------------------


class TestExportHtmlVocabulary:
    def test_vocabulary_section_rendered(self):
        books = [_make_book()]
        lookups = _make_word_lookups(8)
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, word_lookups=lookups)
            content = (Path(tmp) / "index.html").read_text(encoding="utf-8")
            assert "Vocabulary" in content
            assert "Total Lookups" in content
            assert "Unique Words" in content

    def test_vocabulary_top_words_chart(self):
        books = [_make_book()]
        lookups = _make_word_lookups(10)
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, word_lookups=lookups)
            content = (Path(tmp) / "index.html").read_text(encoding="utf-8")
            assert "Most Looked Up Words" in content

    def test_no_vocabulary_when_empty(self):
        books = [_make_book()]
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp, word_lookups=[])
            content = (Path(tmp) / "index.html").read_text(encoding="utf-8")
            assert "vocab-section" not in content

    def test_no_vocabulary_when_none(self):
        books = [_make_book()]
        with tempfile.TemporaryDirectory() as tmp:
            export_static_site(books, tmp)
            content = (Path(tmp) / "index.html").read_text(encoding="utf-8")
            assert "vocab-section" not in content


# ---------------------------------------------------------------------------
# Torchvision graceful error handling
# ---------------------------------------------------------------------------


class TestTorchvisionGraceful:
    def test_torch_import_error_mentions_torchvision(self):
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers is required"):
                from services.embeddings import LocalEmbeddingProvider
                LocalEmbeddingProvider()

    def test_torchvision_import_error_caught(self):
        """If the ImportError message mentions torchvision, we get a helpful message."""
        fake_st = MagicMock()
        fake_st.SentenceTransformer = MagicMock
        err = ImportError("No module named 'torchvision'")

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            # Simulate torchvision-related import failure
            with patch("builtins.__import__", side_effect=err):
                with pytest.raises(ImportError, match="torch|torchvision"):
                    from services.embeddings import LocalEmbeddingProvider
                    LocalEmbeddingProvider()


# ---------------------------------------------------------------------------
# Safe device copy
# ---------------------------------------------------------------------------


class TestSafeDeviceCopy:
    def test_copies_file_to_temp(self, tmp_path):
        """_safe_device_copy should create a temp copy of the database."""
        # Create a fake database file
        fake_db = tmp_path / "KoboReader.sqlite"
        fake_db.write_bytes(b"fake sqlite content")

        from app.app import _safe_device_copy

        tmp_copy = _safe_device_copy(fake_db)
        try:
            assert tmp_copy.exists()
            assert tmp_copy != fake_db
            assert tmp_copy.read_bytes() == b"fake sqlite content"
        finally:
            tmp_copy.unlink(missing_ok=True)

    def test_original_unchanged(self, tmp_path):
        """Original file should remain untouched."""
        fake_db = tmp_path / "KoboReader.sqlite"
        fake_db.write_bytes(b"original data")

        from app.app import _safe_device_copy

        tmp_copy = _safe_device_copy(fake_db)
        try:
            assert fake_db.read_bytes() == b"original data"
        finally:
            tmp_copy.unlink(missing_ok=True)
