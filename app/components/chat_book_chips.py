"""Render small book-cover chips for books referenced in a chat message.

Used by the Chat view to make assistant replies visual when they mention
specific books from the user's library. Matching is bounded to titles that
already exist in the user's data, so we never render chips for arbitrary
strings or hallucinated titles.
"""
from __future__ import annotations

import re
from html import escape

import streamlit as st

from app.components.book_cover import cover_html_fragment
from models.book import Book

_MAX_CHIPS = 4
_MIN_TITLE_LEN = 4   # ignore very short titles ("It", "1Q84") to avoid false hits


def find_referenced_books(text: str, books: list[Book]) -> list[Book]:
    """Return books from *books* whose title appears as a substring of *text*.

    - Case-insensitive.
    - Longest titles matched first so a mention of "The Hobbit" doesn't also
      match a book titled "Hobbit".
    - Each book returned at most once, in the order they appear in *text*.
    - Capped at :data:`_MAX_CHIPS` results.
    """
    if not text or not books:
        return []

    haystack = text.lower()
    candidates = [b for b in books if b.title and len(b.title) >= _MIN_TITLE_LEN]
    candidates.sort(key=lambda b: len(b.title), reverse=True)

    matches: list[tuple[int, Book]] = []
    matched_ids: set[str] = set()
    consumed_spans: list[tuple[int, int]] = []

    for book in candidates:
        needle = book.title.lower()
        # Word-boundary-ish search so "Dune" doesn't match "Dunes"
        for m in re.finditer(re.escape(needle), haystack):
            start, end = m.start(), m.end()
            # Skip if this span is already covered by a longer earlier match
            if any(s <= start and end <= e for s, e in consumed_spans):
                continue
            if book.id in matched_ids:
                continue
            matches.append((start, book))
            matched_ids.add(book.id)
            consumed_spans.append((start, end))
            break

    matches.sort(key=lambda pair: pair[0])
    return [b for _, b in matches[:_MAX_CHIPS]]


def render_chat_book_chips(text: str, books: list[Book]) -> None:
    """Render cover chips for any books from *books* mentioned in *text*.

    No-op when no matches are found, so chat messages without book mentions
    look unchanged.
    """
    referenced = find_referenced_books(text, books)
    if not referenced:
        return

    chip_html_parts: list[str] = []
    for book in referenced:
        cover_frag = cover_html_fragment(
            book,
            css_class="kn-chat-chip-cover",
        )
        title_attr = escape(book.title)
        author_text = escape(book.author or "")
        chip_html_parts.append(
            f'<div class="kn-chat-chip" title="{title_attr}">'
            f'  <div class="kn-chat-chip-cover">{cover_frag}</div>'
            f'  <div class="kn-chat-chip-meta">'
            f'    <div class="kn-chat-chip-title">{title_attr}</div>'
            f'    <div class="kn-chat-chip-author">{author_text}</div>'
            f'  </div>'
            f'</div>'
        )

    st.markdown(
        '<div class="kn-chat-chips">' + "".join(chip_html_parts) + "</div>",
        unsafe_allow_html=True,
    )
