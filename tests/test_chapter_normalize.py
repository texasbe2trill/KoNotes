"""Tests for chapter title normalization."""
from __future__ import annotations

import pytest

from parser.chapter_normalize import normalize_chapter


class TestNormalizeChapter:
    def test_none_input(self):
        assert normalize_chapter(None) is None

    def test_empty_string(self):
        assert normalize_chapter("") is None

    def test_whitespace_only(self):
        assert normalize_chapter("   ") is None

    def test_clean_title_preserved(self):
        assert normalize_chapter("Prologue") == "Prologue"

    def test_clean_title_with_spaces_preserved(self):
        assert normalize_chapter("Part One: Dune") == "Part One: Dune"

    # --- Kobo content-ID prefix patterns (real device data) ---

    def test_kobo_au_prefix(self):
        result = normalize_chapter("au Author s Note")
        assert result == "Author's Note"

    def test_kobo_fm_prefix(self):
        result = normalize_chapter("fm Preface")
        assert result == "Preface"

    def test_kobo_ep_prefix(self):
        result = normalize_chapter("ep Epilogue")
        assert result == "Epilogue"

    def test_kobo_in_prefix(self):
        result = normalize_chapter("in Introduction")
        assert result == "Introduction"

    def test_kobo_de_prefix(self):
        result = normalize_chapter("de Dedication")
        assert result == "Dedication"

    # --- Kobo c-numbered chapter prefixes ---

    def test_kobo_c_prefix_chapter(self):
        result = normalize_chapter("c003 Chapter 3 Documents")
        assert result == "Chapter 3 Documents"

    def test_kobo_c_prefix_chapter_2(self):
        result = normalize_chapter("c002 Chapter 2 Stories Un")
        assert result == "Chapter 2 Stories Un"

    def test_kobo_c_prefix_chapter_1(self):
        result = normalize_chapter("c001 Chapter 1 What Is In")
        assert result == "Chapter 1 What Is In"

    # --- xhtml path patterns ---

    def test_xhtml_path_cleaned(self):
        result = normalize_chapter("xhtml/008_pro_Prologue.xhtml")
        assert result is not None
        assert "xhtml" not in result.lower()
        assert ".xhtml" not in result
        assert "Prologue" in result

    def test_oebps_path_cleaned(self):
        result = normalize_chapter("OEBPS/Text/chapter02.xhtml")
        assert result is not None
        assert "OEBPS" not in result
        assert ".xhtml" not in result

    def test_simple_chapter_file(self):
        result = normalize_chapter("part1_ch3.xhtml")
        assert result is not None
        assert ".xhtml" not in result

    def test_numeric_prefix_stripped(self):
        result = normalize_chapter("008_Prologue.xhtml")
        assert result is not None
        assert "Prologue" in result

    def test_camel_case_split(self):
        result = normalize_chapter("theGreatGatsby.xhtml")
        assert result is not None
        assert " " in result

    def test_fallback_when_empty_after_strip(self):
        result = normalize_chapter("001.xhtml")
        assert result is not None

    # --- Contraction restoration ---

    def test_contraction_s(self):
        result = normalize_chapter("au Author s Note")
        assert result is not None
        assert "'" in result

    def test_already_clean_chapter_name(self):
        assert normalize_chapter("Chapter 1 - A Pragmatic Philosophy") == "Chapter 1 - A Pragmatic Philosophy"
