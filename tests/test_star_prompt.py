"""Tests for star prompt helpers and export attribution."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from services.star_prompt import (
    REPO_URL,
    STAR_LINE,
    STAR_LINE_HTML,
    _CLI_SEEN_FILE,
    _cli_already_seen,
    _mark_cli_seen,
    maybe_show_cli_star_prompt,
)


# ---------------------------------------------------------------------------
# CLI prompt state tracking
# ---------------------------------------------------------------------------

class TestCLIStatePersistence:
    def test_mark_and_check(self, tmp_path, monkeypatch):
        marker = tmp_path / ".star_prompt_seen"
        monkeypatch.setattr("services.star_prompt._STATE_DIR", tmp_path)
        monkeypatch.setattr("services.star_prompt._CLI_SEEN_FILE", marker)

        assert not _cli_already_seen()
        _mark_cli_seen()
        assert _cli_already_seen()

    def test_not_seen_initially(self, tmp_path, monkeypatch):
        marker = tmp_path / ".star_prompt_seen"
        monkeypatch.setattr("services.star_prompt._CLI_SEEN_FILE", marker)
        assert not _cli_already_seen()


# ---------------------------------------------------------------------------
# CLI prompt display logic
# ---------------------------------------------------------------------------

class TestCLIPromptBehavior:
    def test_skipped_when_zero_items(self, tmp_path, monkeypatch, capsys):
        marker = tmp_path / ".star_prompt_seen"
        monkeypatch.setattr("services.star_prompt._STATE_DIR", tmp_path)
        monkeypatch.setattr("services.star_prompt._CLI_SEEN_FILE", marker)

        maybe_show_cli_star_prompt(item_count=0)
        assert not marker.exists()

    def test_shown_once_then_suppressed(self, tmp_path, monkeypatch):
        marker = tmp_path / ".star_prompt_seen"
        monkeypatch.setattr("services.star_prompt._STATE_DIR", tmp_path)
        monkeypatch.setattr("services.star_prompt._CLI_SEEN_FILE", marker)

        with patch("rich.console.Console") as mock_console_cls:
            maybe_show_cli_star_prompt(item_count=5)
            assert marker.exists()
            # Console was used to print
            assert mock_console_cls.return_value.print.called

        # Second call should not print anything
        with patch("rich.console.Console") as mock_console_cls2:
            maybe_show_cli_star_prompt(item_count=5)
            assert not mock_console_cls2.return_value.print.called

    def test_skipped_when_negative_items(self, tmp_path, monkeypatch):
        marker = tmp_path / ".star_prompt_seen"
        monkeypatch.setattr("services.star_prompt._STATE_DIR", tmp_path)
        monkeypatch.setattr("services.star_prompt._CLI_SEEN_FILE", marker)

        maybe_show_cli_star_prompt(item_count=-1)
        assert not marker.exists()


# ---------------------------------------------------------------------------
# Export attribution
# ---------------------------------------------------------------------------

class TestExportAttribution:
    """All export formats include the star line in their output."""

    def _make_book(self):
        from models.annotation import Annotation
        from models.book import Book

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
                    text="A highlight.",
                    source="test",
                ),
            ],
        )

    def test_markdown_star_line(self):
        from services.export_markdown import export_book_markdown

        result = export_book_markdown(self._make_book())
        assert "consider starring" in result.lower()
        assert "github.com/texasbe2trill/KoNotes" in result

    def test_text_star_line(self):
        from services.export_text import export_book_text

        result = export_book_text(self._make_book())
        assert "consider starring" in result.lower()
        assert "github.com/texasbe2trill/KoNotes" in result

    def test_json_star_line(self):
        from services.export_json import export_book_json

        data = json.loads(export_book_json(self._make_book()))
        assert "consider starring" in data["footer"].lower()

    def test_text_preserves_made_with_love(self):
        from services.export_text import export_book_text

        result = export_book_text(self._make_book())
        assert "Made with love" in result

    def test_json_preserves_made_with_love(self):
        from services.export_json import export_book_json

        data = json.loads(export_book_json(self._make_book()))
        assert "Made with love" in data["footer"]

    def test_markdown_preserves_made_with_love(self):
        from services.export_markdown import export_book_markdown

        result = export_book_markdown(self._make_book())
        assert "Made with love" in result


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_repo_url(self):
        assert "github.com/texasbe2trill/KoNotes" in REPO_URL

    def test_star_line_contains_repo(self):
        assert REPO_URL in STAR_LINE

    def test_star_line_html_contains_link(self):
        assert "KoNotes" in STAR_LINE_HTML
        assert "href" in STAR_LINE_HTML
