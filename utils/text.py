"""Utility helpers for text manipulation."""
from __future__ import annotations

import re


def slugify(text: str) -> str:
    """Convert text to a lowercase slug suitable for use as an identifier."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


def truncate(text: str, max_length: int = 200) -> str:
    """Return a truncated version of text with an ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "…"
