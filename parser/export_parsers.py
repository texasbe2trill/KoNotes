"""Parsers for Kobo-exported annotation files.

Kobo can export annotations in three formats:
  - HTML  (.html / .htm)
  - Plain text (.txt)
  - Markdown (.md)

Each parser implements ``BaseParser`` and returns a list of raw annotation
dicts ready for the normalizer.
"""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from parser.base import BaseParser


# ---------------------------------------------------------------------------
# HTML parser
# ---------------------------------------------------------------------------

class HTMLExportParser(BaseParser):
    """Parse a Kobo HTML annotation export."""

    source_name = "kobo_html"

    def parse(self, content: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(content, "html.parser")
        results: list[dict[str, Any]] = []

        # Kobo HTML exports wrap the book title in an <h1> or the first <title>
        book_title = _extract_book_title_html(soup)
        author = _extract_author_html(soup)

        # Each annotation is typically a <div class="highlight"> or similar
        # We support two common Kobo HTML export layouts.
        annotations = soup.select(".annotation") or soup.select(".highlight-container")

        if annotations:
            for block in annotations:
                kind = _detect_kind_html(block)
                text = _clean_text(block.get_text(separator=" "))
                chapter = _extract_chapter_html(block)
                location = _extract_location_html(block)
                results.append(
                    {
                        "book_title": book_title,
                        "author": author,
                        "kind": kind,
                        "text": text,
                        "chapter": chapter,
                        "location": location,
                    }
                )
        else:
            # Fallback: treat every <p> block as an annotation
            for p in soup.find_all("p"):
                text = _clean_text(p.get_text(separator=" "))
                if not text:
                    continue
                results.append(
                    {
                        "book_title": book_title,
                        "author": author,
                        "kind": "unknown",
                        "text": text,
                        "chapter": None,
                        "location": None,
                    }
                )

        return results


def _extract_book_title_html(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return _clean_text(h1.get_text())
    title_tag = soup.find("title")
    if title_tag:
        return _clean_text(title_tag.get_text())
    return "Unknown Book"


def _extract_author_html(soup: BeautifulSoup) -> str | None:
    author_el = soup.select_one(".author") or soup.select_one(".book-author")
    if author_el:
        return _clean_text(author_el.get_text())
    # meta author tag
    meta = soup.find("meta", attrs={"name": "author"})
    if meta and meta.get("content"):
        return _clean_text(str(meta["content"]))
    return None


def _detect_kind_html(block: Any) -> str:
    classes = " ".join(block.get("class", [])).lower()
    if "note" in classes:
        return "note"
    if "highlight" in classes:
        return "highlight"
    return "unknown"


def _extract_chapter_html(block: Any) -> str | None:
    chapter_el = block.find(class_=re.compile(r"chapter|section", re.I))
    if chapter_el:
        return _clean_text(chapter_el.get_text())
    return None


def _extract_location_html(block: Any) -> str | None:
    loc_el = block.find(class_=re.compile(r"location|loc|page", re.I))
    if loc_el:
        return _clean_text(loc_el.get_text())
    return None


# ---------------------------------------------------------------------------
# Plain-text parser
# ---------------------------------------------------------------------------

class TXTExportParser(BaseParser):
    """Parse a Kobo plain-text annotation export.

    Kobo TXT exports use a loose structure like::

        <Book Title>
        <Author>

        ----------
        Highlight | Chapter X | Location Y
        <text>
        ----------
    """

    source_name = "kobo_txt"

    # Separator pattern used by Kobo TXT exports
    _SEPARATOR = re.compile(r"^[-=]{4,}$", re.MULTILINE)
    _META_LINE = re.compile(
        r"^(highlight|note|bookmark)\s*\|?\s*(.*)$", re.IGNORECASE
    )
    _LOCATION_RE = re.compile(r"location\s+(\S+)", re.IGNORECASE)
    _CHAPTER_RE = re.compile(r"chapter\s+([^\|]+)", re.IGNORECASE)

    def parse(self, content: str) -> list[dict[str, Any]]:
        lines = content.splitlines()
        results: list[dict[str, Any]] = []

        book_title, author = _extract_header_txt(lines)
        blocks = self._SEPARATOR.split(content)

        for block in blocks:
            block = block.strip()
            if not block:
                continue
            raw_lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not raw_lines:
                continue

            kind = "unknown"
            chapter: str | None = None
            location: str | None = None
            text_lines: list[str] = []

            for i, line in enumerate(raw_lines):
                meta_match = self._META_LINE.match(line)
                if meta_match and i == 0:
                    kind = meta_match.group(1).lower()
                    meta_rest = meta_match.group(2)
                    chapter_m = self._CHAPTER_RE.search(meta_rest)
                    loc_m = self._LOCATION_RE.search(meta_rest)
                    if chapter_m:
                        chapter = chapter_m.group(1).strip()
                    if loc_m:
                        location = loc_m.group(1).strip()
                else:
                    text_lines.append(line)

            text = " ".join(text_lines).strip()
            if not text:
                continue

            results.append(
                {
                    "book_title": book_title,
                    "author": author,
                    "kind": kind,
                    "text": text,
                    "chapter": chapter,
                    "location": location,
                }
            )

        return results


def _extract_header_txt(lines: list[str]) -> tuple[str, str | None]:
    """Return (book_title, author | None) from the first non-empty lines."""
    non_empty = [l.strip() for l in lines if l.strip()]
    book_title = non_empty[0] if non_empty else "Unknown Book"
    author: str | None = non_empty[1] if len(non_empty) > 1 else None
    # Avoid treating separator lines as author
    if author and re.match(r"^[-=]{4,}$", author):
        author = None
    return book_title, author


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

class MarkdownExportParser(BaseParser):
    """Parse a Kobo Markdown annotation export.

    Expected structure::

        # Book Title
        **Author:** Author Name

        ## Chapter Name

        > Highlight text

        Note: A personal note.
    """

    source_name = "kobo_md"

    _H1 = re.compile(r"^#\s+(.+)$")
    _H2 = re.compile(r"^##\s+(.+)$")
    _AUTHOR = re.compile(r"^\*\*Author:\*\*\s*(.+)$", re.IGNORECASE)
    _BLOCKQUOTE = re.compile(r"^>\s*(.+)$")
    _NOTE = re.compile(r"^(?:Note|Comment|Annotation):\s*(.+)$", re.IGNORECASE)
    _LOCATION = re.compile(r"^\*?(?:Location|Page|Loc):\*?\s*(.+)$", re.IGNORECASE)

    def parse(self, content: str) -> list[dict[str, Any]]:
        lines = content.splitlines()
        results: list[dict[str, Any]] = []

        book_title = "Unknown Book"
        author: str | None = None
        current_chapter: str | None = None

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()

            h1_m = self._H1.match(line)
            if h1_m:
                book_title = h1_m.group(1).strip()
                i += 1
                continue

            author_m = self._AUTHOR.match(line)
            if author_m:
                author = author_m.group(1).strip()
                i += 1
                continue

            h2_m = self._H2.match(line)
            if h2_m:
                current_chapter = h2_m.group(1).strip()
                i += 1
                continue

            bq_m = self._BLOCKQUOTE.match(line)
            if bq_m:
                # Collect multi-line blockquotes
                text_parts = [bq_m.group(1)]
                j = i + 1
                while j < len(lines):
                    next_bq = self._BLOCKQUOTE.match(lines[j].rstrip())
                    if next_bq:
                        text_parts.append(next_bq.group(1))
                        j += 1
                    else:
                        break
                location: str | None = None
                if j < len(lines):
                    loc_m = self._LOCATION.match(lines[j].rstrip())
                    if loc_m:
                        location = loc_m.group(1).strip()
                        j += 1
                results.append(
                    {
                        "book_title": book_title,
                        "author": author,
                        "kind": "highlight",
                        "text": " ".join(text_parts).strip(),
                        "chapter": current_chapter,
                        "location": location,
                    }
                )
                i = j
                continue

            note_m = self._NOTE.match(line)
            if note_m:
                results.append(
                    {
                        "book_title": book_title,
                        "author": author,
                        "kind": "note",
                        "text": note_m.group(1).strip(),
                        "chapter": current_chapter,
                        "location": None,
                    }
                )
                i += 1
                continue

            i += 1

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Parser registry
# ---------------------------------------------------------------------------

EXTENSION_TO_PARSER: dict[str, BaseParser] = {
    ".html": HTMLExportParser(),
    ".htm": HTMLExportParser(),
    ".txt": TXTExportParser(),
    ".md": MarkdownExportParser(),
    ".markdown": MarkdownExportParser(),
}


def get_parser_for_extension(
    extension: str,
    content: str | None = None,
) -> BaseParser | None:
    """Return the appropriate parser for a file extension, or None.

    For ``.txt`` files, if *content* is provided, auto-detects Kindle
    ``My Clippings.txt`` format and returns the Kindle parser instead.
    """
    from parser.kindle_parser import KindleClippingsParser, is_kindle_clippings

    ext = extension.lower()
    if ext == ".txt" and content is not None and is_kindle_clippings(content):
        return KindleClippingsParser()
    return EXTENSION_TO_PARSER.get(ext)
