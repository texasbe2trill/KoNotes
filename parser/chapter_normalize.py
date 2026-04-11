"""Chapter title normalization for Kobo chapter references.

Kobo stores chapter titles in various formats:
    xhtml/008_pro_Prologue.xhtml       (xhtml path)
    OEBPS/Text/chapter02.xhtml         (OEBPS path)
    au Author s Note                    (abbreviated type prefix)
    fm Preface                          (abbreviated type prefix)
    c003 Chapter 3 Documents            (numbered chapter with c-prefix)
    c001 Chapter 1 What Is In           (may be truncated)
    Prologue                            (already clean)

This module cleans those into human-readable chapter names.
"""
from __future__ import annotations

import re


# Patterns stripped from chapter path components
_XHTML_SUFFIX = re.compile(r"\.(xhtml|html|htm)$", re.IGNORECASE)
_PATH_PREFIX = re.compile(r"^.*/")  # everything up to (and including) last /
_UNDERSCORE_SEP = re.compile(r"[_]+")
_CAMEL_SPLIT = re.compile(r"(?<=[a-z])(?=[A-Z])")

# Kobo internal content-ID prefixes (e.g. "au Author s Note", "fm Preface",
# "c003 Chapter 3 Documents"). These are 2-4 char abbreviations followed by
# a space and the actual title fragment.
_KOBO_CONTENT_PREFIX = re.compile(
    r"^(?:au|bm|co|de|ep|fm|hw|in|pt|sm|toc)\s+",
    re.IGNORECASE,
)
# Numbered chapter prefix: "c001 ", "c003 ", etc.
_KOBO_CHAPTER_NUM = re.compile(r"^c\d{2,4}\s+", re.IGNORECASE)

# For xhtml-style filenames after path/ext stripping
_NUMERIC_PREFIX = re.compile(r"^\d+[_\-.]?\s*")
_CODED_PREFIX = re.compile(
    r"^(ch(apter)?|pt|part|sec(tion)?|pro(logue)?|epi(logue)?|app(endix)?)"
    r"[_\-.]?\s*",
    re.IGNORECASE,
)


def normalize_chapter(raw: str | None) -> str | None:
    """Convert a raw chapter reference into a human-readable title.

    Returns ``None`` if the input is empty or produces an empty result.
    """
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # --- Handle xhtml paths first ---
    if "/" in text or _XHTML_SUFFIX.search(text):
        text = _PATH_PREFIX.sub("", text)
        text = _XHTML_SUFFIX.sub("", text)
        text = _UNDERSCORE_SEP.sub(" ", text)
        text = text.replace("-", " ")
        text = _NUMERIC_PREFIX.sub("", text)
        text = _CODED_PREFIX.sub("", text)
        text = _CAMEL_SPLIT.sub(" ", text)
        text = text.strip()
        if not text:
            return raw.strip()
        # After xhtml cleanup, the result may still have Kobo prefixes
        # e.g. "au Author s Note" or "c002 Chapter 2 Stories Un"
        # Fall through to the prefix handlers below

    # --- Handle Kobo content-ID abbreviation prefixes ---
    # "c003 Chapter 3 Documents" -> "Chapter 3 Documents"
    cleaned = _KOBO_CHAPTER_NUM.sub("", text)
    if cleaned != text:
        text = cleaned.strip()
        if text:
            return text
        return raw.strip()

    # "au Author s Note" -> "Author's Note"
    # "fm Preface" -> "Preface"
    cleaned = _KOBO_CONTENT_PREFIX.sub("", text)
    if cleaned != text:
        text = cleaned.strip()
        if text:
            # Try to restore common contractions broken by Kobo's splitting
            text = _restore_contractions(text)
            return text
        return raw.strip()

    # --- Already clean (has spaces, no file markers) ---
    # Title-case if fully lowercase (common after xhtml path cleanup)
    if text == text.lower():
        text = text.title()
    return text


def _restore_contractions(text: str) -> str:
    """Fix common contractions broken by space-separated Kobo titles.

    e.g. 'Author s Note' -> \"Author's Note\"
    """
    # Pattern: word boundary + single letter 's' surrounded by spaces
    # "Author s Note" -> "Author's Note"
    text = re.sub(r"\b(\w+)\s+s\s+", r"\1's ", text)
    # "Don t" -> "Don't"
    text = re.sub(r"\b(\w+)\s+t\b", r"\1't", text)
    # "I m" -> "I'm", "I ll" -> "I'll", "I ve" -> "I've"
    text = re.sub(r"\b(I)\s+(m|ll|ve|d)\b", r"\1'\2", text)
    # "We re" -> "We're", "They re" -> "They're"
    text = re.sub(r"\b(\w+)\s+re\b", r"\1're", text)
    return text
