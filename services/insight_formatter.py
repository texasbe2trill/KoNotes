"""Insight formatter -- post-process raw LLM/AI output into structured sections.

Provides helpers for:
- Splitting monolithic AI text into discrete insight cards
- Extracting titles/summaries from raw text
- Wrapping long text into readable chunks
- Parsing structured sections from messy output
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime

from models.insight import EvidenceItem, InsightCard


def _card_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def split_llm_output(text: str, book_title: str = "") -> list[InsightCard]:
    """Split a monolithic LLM summary into discrete InsightCard objects.

    Handles common LLM output patterns:
    - Numbered lists (1. ... 2. ...)
    - Markdown headings (## ...)
    - Paragraph breaks with topic sentences
    """
    if not text or not text.strip():
        return []

    sections = _split_into_sections(text)
    cards: list[InsightCard] = []

    for i, section in enumerate(sections):
        title = _extract_title(section) or f"Insight {i + 1}"
        # Remove the title from the body if we extracted it
        body = _remove_title(section, title)
        summary = _extract_summary(body)

        cards.append(InsightCard(
            id=_card_id("llm", book_title, str(i)),
            title=title,
            category="Book Summary",
            summary=summary,
            body=body.strip(),
            related_books=[book_title] if book_title else [],
            source="llm",
            created_at=datetime.now(),
            priority_score=0.5 + (0.1 if i == 0 else 0),
        ))

    return cards


def _split_into_sections(text: str) -> list[str]:
    """Split text into sections by headings or numbered items."""
    # Try markdown headings first
    heading_splits = re.split(r'\n(?=#{1,3}\s)', text.strip())
    if len(heading_splits) > 1:
        return [s.strip() for s in heading_splits if s.strip()]

    # Try numbered list items: "1. ...", "2. ..." etc.
    numbered_splits = re.split(r'\n(?=\d+\.\s)', text.strip())
    if len(numbered_splits) > 1:
        return [s.strip() for s in numbered_splits if s.strip()]

    # Fall back to paragraph breaks
    paragraphs = text.strip().split('\n\n')
    # Merge very short paragraphs back together
    merged: list[str] = []
    buffer = ""
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if buffer and len(buffer) + len(p) < 300:
            buffer += "\n\n" + p
        else:
            if buffer:
                merged.append(buffer)
            buffer = p
    if buffer:
        merged.append(buffer)

    return merged if merged else [text.strip()]


def _extract_title(section: str) -> str:
    """Extract a title from a section of text."""
    lines = section.strip().split('\n')
    first = lines[0].strip()

    # Markdown heading
    match = re.match(r'^#{1,3}\s+(.+)', first)
    if match:
        return match.group(1).strip()

    # Numbered item: "1. Title" or "1) Title"
    match = re.match(r'^\d+[.)]\s+(.+)', first)
    if match:
        return match.group(1).strip()

    # Bold text: **Title**
    match = re.match(r'^\*\*(.+?)\*\*', first)
    if match:
        return match.group(1).strip()

    # If first line is short enough to be a title
    if len(first) <= 80 and first.endswith((':',)):
        return first.rstrip(':').strip()

    # Fallback: use first sentence if short enough
    sentences = re.split(r'(?<=[.!?])\s+', first)
    if sentences and len(sentences[0]) <= 80:
        return sentences[0].rstrip('.')

    return ""


def _remove_title(section: str, title: str) -> str:
    """Remove the extracted title from the section body."""
    if not title:
        return section
    lines = section.strip().split('\n')
    first = lines[0].strip()

    # Check if first line contains the title
    cleaned_first = re.sub(r'^#{1,3}\s+', '', first)
    cleaned_first = re.sub(r'^\d+[.)]\s+', '', cleaned_first)
    cleaned_first = re.sub(r'^\*\*(.+?)\*\*\s*', r'\1', cleaned_first)

    if title in cleaned_first and len(lines) > 1:
        return '\n'.join(lines[1:]).strip()

    return section.strip()


def _extract_summary(body: str) -> str:
    """Extract the first 1-2 sentences as a summary."""
    if not body:
        return ""
    sentences = re.split(r'(?<=[.!?])\s+', body.strip())
    summary_parts = []
    for s in sentences:
        summary_parts.append(s)
        if len(' '.join(summary_parts)) > 120:
            break
        if len(summary_parts) >= 2:
            break
    return ' '.join(summary_parts)


def format_long_text(text: str, max_preview: int = 200) -> tuple[str, str]:
    """Split long text into a preview and full body.

    Returns (preview, full_text).
    """
    text = text.strip()
    if len(text) <= max_preview:
        return text, text

    # Find a natural break point near max_preview
    break_point = text.rfind('. ', 0, max_preview)
    if break_point == -1:
        break_point = text.rfind(' ', 0, max_preview)
    if break_point == -1:
        break_point = max_preview

    preview = text[:break_point + 1].strip()
    if not preview.endswith('.'):
        preview += "..."

    return preview, text


def normalize_ai_insights(
    raw_text: str,
    book_title: str = "",
    themes: list | None = None,
) -> list[InsightCard]:
    """Normalize raw AI/LLM output into structured InsightCard objects.

    This is the primary entry point for converting messy LLM output
    into the structured insight feed format.
    """
    cards = split_llm_output(raw_text, book_title)

    # Attach theme evidence if available
    if themes:
        for card in cards:
            for theme in themes[:5]:
                label = getattr(theme, "label", str(theme))
                size = getattr(theme, "size", 0)
                if size:
                    card.evidence.append(
                        EvidenceItem(label=f"Theme: {label}", value=f"{size} highlights")
                    )

    return cards
