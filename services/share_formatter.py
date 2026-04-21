"""Share formatting for insights — turns InsightCard objects into shareable text.

Provides three share styles:
- Social post (concise, for Bluesky / #booksky)
- Copy/share (slightly richer, for chat / notes)
- Markdown (suitable for note apps or README snippets)
"""
from __future__ import annotations

from models.insight import InsightCard
from models.recommendation import Recommendation
from services.hero_insight_engine import HeroInsight

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


# ---------------------------------------------------------------------------
# Hero insight Bluesky formatter
# ---------------------------------------------------------------------------


# Introspective, first-person bodies for each hero pattern.  Kept short so the
# total post (body + URL + hashtag) fits inside Bluesky's 300-char limit.
_HERO_BODIES: dict[str, str] = {
    "deep_reader": (
        "I realized I don't read just to highlight \u2014 I read to understand.\n\n"
        "My notes show where things got difficult\u2026 and where I actually slowed down to think.\n\n"
        "That's where my best thinking happens."
    ),
    "pattern_seeker": (
        "Looking back at my highlights, I'm not really finishing books \u2014 I'm chasing an idea across them.\n\n"
        "The same kinds of passages keep catching my eye.\n\n"
        "Turns out I read like I'm following a thread."
    ),
    "selective_thinker": (
        "I highlight a lot in passing, but I only write a note when something genuinely stops me.\n\n"
        "Those few notes are the ones that earned the page.\n\n"
        "That's the shortlist I should actually revisit."
    ),
    "friction_reader": (
        "I noticed I don't skim past hard words \u2014 I stop and look them up.\n\n"
        "That small bit of friction is where the vocabulary actually sticks.\n\n"
        "Slowing down has been the real upgrade."
    ),
    "focused_deep_dive": (
        "Most of my reading energy went into one book.\n\n"
        "That kind of single-book focus is rare \u2014 and apparently it's how I read when something really lands.\n\n"
        "Worth writing down what I took from it."
    ),
}


def format_hero_for_bluesky(
    insight: HeroInsight,
    app_url: str = APP_PUBLIC_URL,
) -> str:
    """Compose an introspective, first-person Bluesky post from a HeroInsight.

    Falls back to the insight's own summary if the pattern isn't recognized
    (e.g. the sparse-data fallback or a future pattern).  Always ends with the
    app URL and a single ``#booksky`` tag \u2014 no marketing copy.
    """
    body = _HERO_BODIES.get(insight.pattern)
    if body is None:
        body = insight.summary.strip()

    text = f"{body}\n\n{app_url}\n\n#booksky"
    return _truncate(text, _BLUESKY_TARGET)


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


# ---------------------------------------------------------------------------
# Recommendation formatters
# ---------------------------------------------------------------------------


_KIND_BLUESKY_OPENERS: dict[str, str] = {
    "revisit": "There\u2019s a book in my library I need to return to \u2014 my notes there are some of my best thinking.",
    "finish": "Still working through a book that already has a lot of my attention captured in it.",
    "export": "Realized I have a book full of notes that deserve to live somewhere permanent.",
    "forgotten_gem": "Just rediscovered a book I engaged with deeply \u2014 somehow I forgot it existed.",
    "deepest_thinking": "The book with the most of my own words in it might be the one worth re-reading most carefully.",
    "compare": "Two books in my library drew almost identical levels of engagement from me \u2014 probably not a coincidence.",
}


def format_recommendation_for_bluesky(
    rec: Recommendation,
    app_url: str = APP_PUBLIC_URL,
) -> str:
    """Compose a concise, personal Bluesky post from a Recommendation.

    Uses kind-specific opener text so posts feel natural, not templated.
    Always ends with the app URL and ``#booksky``.  Guaranteed <= 300 chars.
    """
    opener = _KIND_BLUESKY_OPENERS.get(rec.kind, rec.summary)
    footer = f"{app_url}\n\n#booksky"
    text = f"{opener}\n\n{footer}"
    return _truncate(text, _BLUESKY_TARGET)


def format_recommendation_for_markdown(
    rec: Recommendation,
    app_url: str = APP_PUBLIC_URL,
) -> str:
    """Markdown export suitable for note apps or README snippets."""
    lines: list[str] = []

    lines.append(f"### {rec.title}")
    lines.append("")
    lines.append(f"> {rec.summary}")
    lines.append("")
    lines.append(f"**Why:** {rec.reason}")
    lines.append("")

    if rec.evidence:
        lines.append("**Evidence:**")
        for item in rec.evidence:
            lines.append(f"- {item}")
        lines.append("")

    if rec.recommended_action:
        lines.append(f"**Next step:** {rec.recommended_action}")
        lines.append("")

    if rec.related_books:
        books = ", ".join(f"*{b}*" for b in rec.related_books[:5])
        lines.append(f"**Books:** {books}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by [KoNotes]({app_url})*")

    return "\n".join(lines)
