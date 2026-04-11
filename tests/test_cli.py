"""Tests for the CLI (main.py) subcommands."""
from __future__ import annotations

from pathlib import Path

import pytest

from main import main

FIXTURES = Path(__file__).parent / "fixtures"


class TestCLIParse:
    def test_parse_html_fixture(self):
        result = main(["parse", str(FIXTURES / "sample_export.html")])
        assert result == 0

    def test_parse_txt_fixture(self):
        result = main(["parse", str(FIXTURES / "sample_export.txt")])
        assert result == 0

    def test_parse_md_fixture(self):
        result = main(["parse", str(FIXTURES / "sample_export.md")])
        assert result == 0

    def test_parse_missing_file(self):
        result = main(["parse", "/nonexistent/file.html"])
        assert result == 1

    def test_parse_unsupported_format(self, tmp_path):
        bad = tmp_path / "test.pdf"
        bad.write_text("not a pdf")
        result = main(["parse", str(bad)])
        assert result == 1


class TestCLIExport:
    def test_export_markdown(self, tmp_path):
        result = main([
            "export",
            str(FIXTURES / "sample_export.html"),
            "-f", "markdown",
            "-o", str(tmp_path),
        ])
        assert result == 0
        exported = list(tmp_path.glob("*.md"))
        assert len(exported) == 1

    def test_export_json(self, tmp_path):
        result = main([
            "export",
            str(FIXTURES / "sample_export.html"),
            "-f", "json",
            "-o", str(tmp_path),
        ])
        assert result == 0
        exported = list(tmp_path.glob("*.json"))
        assert len(exported) == 1

    def test_export_text(self, tmp_path):
        result = main([
            "export",
            str(FIXTURES / "sample_export.html"),
            "-f", "text",
            "-o", str(tmp_path),
        ])
        assert result == 0
        exported = list(tmp_path.glob("*.txt"))
        assert len(exported) == 1


class TestCLISummary:
    def test_summary(self):
        result = main(["summary", str(FIXTURES / "sample_export.html")])
        assert result == 0


class TestCLINoArgs:
    def test_no_args_shows_help(self):
        result = main([])
        assert result == 0


class TestCLIDetectDevice:
    def test_detect_device_runs(self):
        result = main(["detect-device"])
        assert result == 0
