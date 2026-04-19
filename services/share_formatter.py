"""Share formatting for insights — turns InsightCard objects into shareable text.

Provides three share styles:
- Social post (concise, for Bluesky / #booksky)
- Copy/share (slightly richer, for chat / notes)
- Markdown (suitable for note apps or README snippets)
"""
from __future__ import annotations

from models.insight import InsightCard

APP_PUBLIC_URL = "https://konotes.streamlit.app/"

# Maximum length for Bluesky posts (300 graphemes).
_BLUESKY_TARGET = 300


def _truncate(text: str, limit: int) -> str:
    """Truncate *text* to *limit* characters with an ellipsis if needed."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


def is_shareworthy(card: InsightCard) -> bool:
    """Return True if an insight is meaningful enough to surface share actions.

    Strict criteria — only the most personal, interesting insights should
    be surfaced for sharing.  Requires high priority AND interpretive depth.
    """
    if card.priority_score < 0.7:
        return False
    # Must have genuine interpretive content, not just stats
    has_substance = len(card.body) > 80 and card.recommendation is not None
    has_personal_touch = len(card.related_books) >= 1
    return has_substance and has_personal_touch


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_insight_for_bluesky(
    card: InsightCard,
    app_url: str = APP_PUBLIC_URL,
) -> str:
    """Compose a natural first-person Bluesky post from card data.

    Instead of mechanically converting the second-person UI summary,
    builds a fresh, personal post from the card's structured fields
    (related books, category, evidence, recommendation).
    """
    books = card.related_books
    book_ref = f'"{books[0]}"' if books else ""

    # Category-aware first-person post composition
    cat = card.category
    if cat == "Most Engaged Books" and book_ref:
        post = f"{book_ref} left the biggest mark on my reading — the kind of book I keep coming back to"
    elif cat == "Library Overview":
        ann_count = _evidence_val(card, "Annotated books") or _evidence_val(card, "Total annotations")
        if ann_count:
            post = f"Built a personal library of ideas across {ann_count} annotated books — my reading story so far"
        else:
            post = "Built a personal library of ideas worth keeping — my reading story so far"
    elif cat == "Highlight Behavior" and book_ref:
        post = f"Something about {book_ref} kept stopping me in my tracks — had to highlight it"
    elif cat == "Highlight Behavior":
        post = "Some chapters just hit different — the highlights tell the story"
    elif cat == "Reading Patterns":
        post = "Interesting pattern in my reading data — the books reveal more than I expected"
    elif cat == "Books in Progress" and book_ref:
        post = f"Still working through {book_ref} — the journey continues"
    elif cat == "Books in Progress":
        post = "Still have a few books in progress — the journey continues"
    elif cat == "Vocabulary Activity":
        word_count = _evidence_val(card, "Unique words")
        if word_count and book_ref:
            post = f"Looked up {word_count} unique words while reading {book_ref} — curiosity in action"
        elif word_count:
            post = f"Looked up {word_count} unique words across my reading — curiosity in action"
        else:
            post = "My vocabulary lookups tell a story about what caught my attention"
    elif cat == "Reading Momentum":
        streak = _evidence_val(card, "Current streak") or _evidence_val(card, "Streak")
        if streak:
            post = f"On a {streak}-day reading streak — momentum builds on itself"
        else:
            post = "Building reading momentum — every session counts"
    elif cat == "Forgotten Insights" and book_ref:
        post = f"Rediscovered some highlights from {book_ref} that I'd forgotten — still resonant"
    elif cat == "Deep Reading Signals" and book_ref:
        post = f"Deep reading in {book_ref} — the kind of engagement that leaves a mark"
    elif book_ref:
        post = f"{book_ref} — a reading insight worth sharing"
    else:
        post = "A reading insight worth sharing"

    footer = f"Discover your reading insights with #KoNotes #booksky {app_url}"
    text = f"{post}\n\n{footer}"
    return _truncate(text, _BLUESKY_TARGET)


def _evidence_val(card: InsightCard, label: str) -> str | None:
    """Extract a value from card evidence by label prefix."""
    for e in card.evidence:
        if e.label.lower().startswith(label.lower()):
            return e.value
    return None


def format_insight_for_copy(
    card: InsightCard,
    app_url: str = APP_PUBLIC_URL,
) -> str:
    """Slightly richer format suitable for pasting into chat / notes."""
    parts: list[str] = []

    parts.append(f"{card.title}\n{card.summary}")

    if card.body:
        # Use the first paragraph only to keep it compact
        first_para = card.body.split("\n\n")[0].strip()
        if first_para and first_para != card.summary:
            parts.append(first_para)

    if card.recommendation:
        parts.append(f"Recommendation: {card.recommendation}")

    if card.related_books:
        books = ", ".join(card.related_books[:5])
        parts.append(f"Books: {books}")

    parts.append(f"Shared via KoNotes\n{app_url}")

    return "\n\n".join(parts)


def format_insight_for_markdown(
    card: InsightCard,
    app_url: str = APP_PUBLIC_URL,
) -> str:
    """Markdown format suitable for note apps or export snippets."""
    lines: list[str] = []

    lines.append(f"### {card.title}")
    lines.append("")
    lines.append(f"> {card.summary}")
    lines.append("")

    if card.body:
        first_para = card.body.split("\n\n")[0].strip()
        if first_para and first_para != card.summary:
            lines.append(first_para)
            lines.append("")

    if card.recommendation:
        lines.append(f"**Recommendation:** {card.recommendation}")
        lines.append("")

    if card.related_books:
        books = ", ".join(f"*{b}*" for b in card.related_books[:5])
        lines.append(f"**Books:** {books}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Shared via [KoNotes]({app_url})*")

    return "\n".join(lines)
