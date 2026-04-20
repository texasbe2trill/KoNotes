"""Parser for Amazon Kindle's My Clippings.txt file.

Kindle stores all highlights, notes, bookmarks, and underlines in a single
file at the root of the device.  Each entry is separated by ``==========``
and has this structure::

    Book Title (Author Name)
    - Your Highlight on page 42 | Location 639-641 | Added on Monday, March 15, 2024 12:34:56 PM

    The actual highlighted text goes here.
    ==========

This parser handles highlights, underlines (treated as highlights), notes,
and bookmarks.  Duplicate clippings are deduplicated by content hash.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from parser.base import BaseParser


class KindleClippingsParser(BaseParser):
    """Parse an Amazon Kindle ``My Clippings.txt`` export."""

    source_name = "kindle"

    # Separator between Kindle clippings
    _SEPARATOR = "=========="

    # Title line: ``Book Title (Author Name)``
    _TITLE_RE = re.compile(
        r"^\uFEFF?\s*(?P<title>.+?)\s*\((?P<author>[^)]+)\)\s*$"
    )

    # Metadata line examples:
    #   - Your Highlight on page 2 | Location 766-767 | Added on Thursday, April 16, 2026 9:00:54 PM
    #   - Your Bookmark on page xxv | Location 515 | Added on Thursday, April 16, 2026 8:28:18 PM
    #   - Your Note on page 10 | Location 200 | Added on Friday, April 17, 2026 10:00:00 AM
    _META_RE = re.compile(
        r"^-\s*Your\s+(?P<kind>Highlight|Note|Bookmark|Underline)\s+"
        r"on\s+page\s+(?P<page>[^\|]+?)\s*\|\s*"
        r"Location\s+(?P<location>[^\|]+?)\s*\|\s*"
        r"Added\s+on\s+(?P<date>.+)$",
        re.IGNORECASE,
    )

    # Fallback: metadata without page number
    _META_NO_PAGE_RE = re.compile(
        r"^-\s*Your\s+(?P<kind>Highlight|Note|Bookmark|Underline)\s+"
        r"on\s+Location\s+(?P<location>[^\|]+?)\s*\|\s*"
        r"Added\s+on\s+(?P<date>.+)$",
        re.IGNORECASE,
    )

    # Kindle timestamp format: ``Thursday, April 16, 2026 9:00:54 PM``
    _DATE_FORMATS = [
        "%A, %B %d, %Y %I:%M:%S %p",
        "%A, %B %d, %Y %I:%M %p",
    ]

    def parse(self, content: str) -> list[dict[str, Any]]:
        entries = content.split(self._SEPARATOR)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            lines = entry.splitlines()
            if len(lines) < 2:
                continue

            # Line 1: title (author)
            title_line = lines[0].strip().lstrip("\uFEFF")
            title, author = self._parse_title_line(title_line)

            # Line 2: metadata
            meta_line = lines[1].strip()
            meta = self._parse_meta_line(meta_line)
            if meta is None:
                continue

            kind = meta["kind"]

            # Lines 3+: annotation text (skip blank line after metadata)
            text_lines = [l for l in lines[2:] if l.strip()]
            text = "\n".join(l.strip() for l in text_lines).strip()

            # Bookmarks have no text — skip them
            if kind == "bookmark" and not text:
                continue

            # Underlines are functionally highlights
            if kind == "underline":
                kind = "highlight"

            # Deduplicate: Kindle appends on every re-highlight
            dedup_key = f"{title}|{kind}|{text}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            results.append(
                {
                    "book_title": title,
                    "author": author,
                    "kind": kind,
                    "text": text,
                    "chapter": None,
                    "location": meta.get("location"),
                    "created_at": meta.get("date"),
                    "page": meta.get("page"),
                }
            )

        return results

    def _parse_title_line(self, line: str) -> tuple[str, str | None]:
        """Extract book title and author from the first line."""
        m = self._TITLE_RE.match(line)
        if m:
            return m.group("title").strip(), m.group("author").strip()
        # Fallback: entire line is the title, no author
        return line.strip(), None

    def _parse_meta_line(self, line: str) -> dict[str, Any] | None:
        """Parse the metadata line into kind, page, location, date."""
        m = self._META_RE.match(line)
        if not m:
            m = self._META_NO_PAGE_RE.match(line)
            if not m:
                return None
            return {
                "kind": m.group("kind").lower(),
                "page": None,
                "location": m.group("location").strip(),
                "date": self._parse_date(m.group("date").strip()),
            }
        return {
            "kind": m.group("kind").lower(),
            "page": m.group("page").strip(),
            "location": m.group("location").strip(),
            "date": self._parse_date(m.group("date").strip()),
        }

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse Kindle's verbose timestamp format."""
        for fmt in self._DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None


def is_kindle_clippings(content: str) -> bool:
    """Detect whether a .txt file is a Kindle My Clippings export.

    Uses structural heuristics:
    - Contains ``==========`` separators
    - Contains ``- Your Highlight`` or ``- Your Note`` metadata lines
    """
    if "==========" not in content:
        return False
    return bool(re.search(r"^-\s*Your\s+(Highlight|Note|Bookmark|Underline)\b", content, re.MULTILINE))


def parse_kindle_clippings(path: str | Any) -> list[dict[str, Any]]:
    """Convenience function: read a Kindle clippings file and return parsed entries.

    Parameters
    ----------
    path
        Path to the ``My Clippings.txt`` file.

    Returns
    -------
    list[dict]
        Raw annotation dicts ready for the normalizer.
    """
    from pathlib import Path
    p = Path(path)
    content = p.read_text(encoding="utf-8", errors="replace")
    parser = KindleClippingsParser()
    return parser.parse(content)
