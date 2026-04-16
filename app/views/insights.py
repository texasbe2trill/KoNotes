"""Reading Intelligence — personalized insights from your Kobo library.

Surfaces structured, personable insights from reading data through
computed analytics. Optional on-device AI analysis (theme detection,
cross-book clustering, semantic search) enhances the experience but
is never required — KoNotes works beautifully without it.
"""
from __future__ import annotations

import html as html_mod
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import streamlit as st

from models.book import Book
from models.insight import INSIGHT_CATEGORIES, EvidenceItem, InsightCard

if TYPE_CHECKING:
    from models.annotation import Annotation
    from models.insight import BookSummary, HighlightSimilarity, ThemeCluster

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
_BLUE = "#3b82f6"
_GREEN = "#22c55e"
_AMBER = "#f59e0b"
_PURPLE = "#a855f7"
_ROSE = "#f43f5e"
_CYAN = "#06b6d4"
_TEAL = "#14b8a6"
_INDIGO = "#6366f1"
_COLORS = [_BLUE, _GREEN, _AMBER, _PURPLE, _ROSE, _CYAN, _TEAL, _INDIGO]

_CATEGORY_COLORS: dict[str, str] = {
    "Library Overview": _BLUE,
    "Most Engaged Books": _GREEN,
    "Highlight Behavior": _AMBER,
    "Reading Patterns": _INDIGO,
    "Books in Progress": _CYAN,
    "Vocabulary Activity": _TEAL,
    "Reading Momentum": _GREEN,
    "Forgotten Insights": _ROSE,
    "Deep Reading Signals": _PURPLE,
    "Cross-Book Themes": _PURPLE,
    "Book Summary": _BLUE,
}

# Insight sections — group card categories into reader-friendly stories
_INSIGHT_SECTIONS = [
    {
        "key": "engaged",
        "title": "Books That Captivated You",
        "icon": "📖",
        "categories": {"Most Engaged Books", "Deep Reading Signals"},
        "description": "Where you invested the most thought, time, and attention",
    },
    {
        "key": "patterns",
        "title": "Your Reading Habits",
        "icon": "📊",
        "categories": {"Reading Patterns", "Highlight Behavior", "Reading Momentum"},
        "description": "The patterns that make your reading style unique",
    },
    {
        "key": "revisit",
        "title": "Worth Coming Back To",
        "icon": "🔄",
        "categories": {"Forgotten Insights", "Books in Progress"},
        "description": "Annotations and books that deserve a second look",
    },
    {
        "key": "vocabulary",
        "title": "Your Vocabulary Journey",
        "icon": "📝",
        "categories": {"Vocabulary Activity"},
        "description": "Words that caught your curiosity",
    },
]

# Hero boosts
_HERO_BOOSTS: dict[str, float] = {
    "Deep Reading Signals": 0.20,
    "Cross-Book Themes": 0.15,
    "Forgotten Insights": 0.12,
    "Most Engaged Books": 0.10,
}

_HERO_FRAMINGS: dict[str, str] = {
    "Deep Reading Signals": "Your deepest engagement",
    "Most Engaged Books": "Your reading spotlight",
    "Forgotten Insights": "Worth revisiting",
    "Reading Momentum": "Your reading rhythm",
    "Cross-Book Themes": "Ideas that connect",
    "Highlight Behavior": "How you annotate",
    "Reading Patterns": "Your reading habits",
    "Library Overview": "Your reading story",
    "Books in Progress": "Still on your shelf",
    "Vocabulary Activity": "Words you explored",
}

# Reader archetypes
_ARCHETYPES = {
    "deep_thinker": {
        "name": "Deep Thinker",
        "emoji": "🧠",
        "color": _PURPLE,
        "description": (
            "You don't just read — you think on the page. "
            "Your notes aren't summaries; they're conversations with the author."
        ),
    },
    "avid_annotator": {
        "name": "Avid Annotator",
        "emoji": "✨",
        "color": _AMBER,
        "description": (
            "You see something worth saving on almost every page. "
            "Your highlights are a personal anthology of ideas that moved you."
        ),
    },
    "focused_scholar": {
        "name": "Focused Scholar",
        "emoji": "🔬",
        "color": _INDIGO,
        "description": (
            "Fewer books, deeper dives. You'd rather understand one book completely "
            "than skim ten."
        ),
    },
    "broad_explorer": {
        "name": "Broad Explorer",
        "emoji": "🌍",
        "color": _CYAN,
        "description": (
            "Your library is a map of your curiosity. "
            "You read widely because everything is connected."
        ),
    },
    "vocabulary_builder": {
        "name": "Vocabulary Builder",
        "emoji": "📚",
        "color": _TEAL,
        "description": (
            "You treat every unknown word as a door worth opening. "
            "Your dictionary lookups are a record of your growing mind."
        ),
    },
    "active_reader": {
        "name": "Active Reader",
        "emoji": "🔥",
        "color": _GREEN,
        "description": (
            "You're in the zone right now — multiple books, recent reads, "
            "ideas flowing. Ride this wave."
        ),
    },
    "balanced_reader": {
        "name": "Engaged Reader",
        "emoji": "📘",
        "color": _BLUE,
        "description": (
            "A healthy reading practice with a good mix of curiosity and commitment. "
            "Your library reflects someone who reads with intention."
        ),
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ai_available() -> bool:
    try:
        import numpy  # noqa: F401
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


def _get_provider():
    from services.embeddings import get_provider
    try:
        return get_provider()
    except ImportError as exc:
        st.error(str(exc))
        return None


def _format_time(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60}m"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m}m" if m else f"{h}h"


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"


def _pill(text: str, color: str) -> str:
    return (
        f'<span style="display:inline-block; font-size:0.68rem; padding:0.12rem 0.5rem; '
        f'border-radius:20px; border:1px solid {color}; color:{color}; '
        f'background:rgba(255,255,255,0.02); margin:0.1rem 0.05rem; white-space:nowrap;">'
        f"{html_mod.escape(text)}</span>"
    )


def _category_pill(category: str) -> str:
    color = _CATEGORY_COLORS.get(category, _BLUE)
    return (
        f'<span style="display:inline-block; font-size:0.62rem; padding:0.1rem 0.45rem; '
        f"border-radius:4px; background:rgba({_hex_to_rgb(color)},0.12); color:{color}; "
        f'font-weight:600; text-transform:uppercase; letter-spacing:0.04em;">'
        f"{html_mod.escape(category)}</span>"
    )


# ---------------------------------------------------------------------------
# Reader profile
# ---------------------------------------------------------------------------


def _compute_archetype(books: list[Book], word_lookups: list) -> dict:
    """Determine reader archetype from library data."""
    total_hl = sum(
        sum(1 for a in b.annotations if a.kind == "highlight") for b in books
    )
    total_notes = sum(
        sum(1 for a in b.annotations if a.kind == "note") for b in books
    )
    annotated = [b for b in books if b.annotations]

    note_ratio = total_notes / total_hl if total_hl > 0 else 0
    annotation_density = (
        (total_hl + total_notes) / len(annotated) if annotated else 0
    )

    now = datetime.now()
    recent = [
        b
        for b in books
        if b.date_last_read and b.date_last_read >= now - timedelta(days=30)
    ]

    if note_ratio > 0.25 and total_notes >= 5:
        key = "deep_thinker"
    elif len(books) <= 5 and annotation_density > 15:
        key = "focused_scholar"
    elif total_hl > 150:
        key = "avid_annotator"
    elif word_lookups and len(word_lookups) > 20:
        key = "vocabulary_builder"
    elif len(recent) >= 3:
        key = "active_reader"
    elif len(books) > 15 and annotation_density < 8:
        key = "broad_explorer"
    else:
        key = "balanced_reader"

    return _ARCHETYPES[key]


# ---------------------------------------------------------------------------
# Rediscover — surface a random highlight (no AI needed)
# ---------------------------------------------------------------------------


def _pick_rediscover(books: list[Book]) -> tuple[str, str, str] | None:
    """Pick a random highlight worth resurfacing.

    Returns (text, book_title, age_label) or None.
    """
    candidates: list[tuple[str, str, datetime | None]] = []
    for b in books:
        for a in b.annotations:
            if a.kind == "highlight" and a.text.strip() and 30 <= len(a.text) <= 500:
                candidates.append((a.text, b.title, a.created_at))

    if not candidates:
        return None

    # Prefer older highlights — more likely to be forgotten
    now = datetime.now()
    old = [
        c for c in candidates
        if c[2] and c[2] < now - timedelta(days=60)
    ]
    pool = old if old else candidates

    text, title, date = random.choice(pool)
    if date:
        days_ago = (now - date).days
        if days_ago > 365:
            age = f"Over {days_ago // 365} year{'s' if days_ago >= 730 else ''} ago"
        elif days_ago > 30:
            age = f"{days_ago // 30} month{'s' if days_ago >= 60 else ''} ago"
        else:
            age = "Recently"
    else:
        age = ""

    return text, title, age


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------


def _inject_css() -> None:
    st.markdown(
        """<style>
/* --- Reading Intelligence page --- */
.kn-ri-page { max-width: 820px; }

/* Profile strip */
.kn-profile {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.1rem 1.3rem;
    border-radius: 12px;
    border: 1px solid rgba(150,150,150,0.1);
    background: rgba(255,255,255,0.015);
    margin-bottom: 1.25rem;
    flex-wrap: wrap;
}
.kn-profile-badge {
    padding: 0.35rem 0.85rem;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.82rem;
    white-space: nowrap;
}
.kn-profile-desc {
    font-size: 0.85rem;
    color: #94a3b8;
    line-height: 1.55;
    flex: 1;
    min-width: 200px;
}
.kn-profile-stats {
    display: flex;
    gap: 1.25rem;
    flex-shrink: 0;
}
.kn-profile-stat { text-align: center; }
.kn-profile-stat-val {
    font-size: 1.1rem;
    font-weight: 700;
    line-height: 1.2;
}
.kn-profile-stat-lbl {
    font-size: 0.62rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

/* Rediscover quote block */
.kn-rediscover {
    border-left: 4px solid #a855f7;
    border-radius: 0 12px 12px 0;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
    background: rgba(168,85,247,0.03);
}
.kn-rediscover-eyebrow {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #a855f7;
    margin-bottom: 0.5rem;
}
.kn-rediscover-quote {
    font-size: 1.05rem;
    font-style: italic;
    line-height: 1.7;
    color: #e2e8f0;
    margin-bottom: 0.5rem;
}
.kn-rediscover-source {
    font-size: 0.78rem;
    color: #64748b;
}

/* Hero insight */
.kn-hero-insight {
    border-left: 4px solid;
    border-radius: 0 12px 12px 0;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
    background: rgba(255,255,255,0.02);
}
.kn-hero-eyebrow {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.4rem;
}
.kn-hero-title {
    font-size: 1.15rem;
    font-weight: 700;
    line-height: 1.35;
    margin-bottom: 0.35rem;
}
.kn-hero-summary {
    font-size: 0.9rem;
    color: #94a3b8;
    line-height: 1.65;
}
.kn-hero-rec {
    margin-top: 0.5rem;
    font-size: 0.82rem;
    color: #3b82f6;
}

/* Takeaway bar */
.kn-takeaway-bar {
    border: 1px solid rgba(139,92,246,0.15);
    border-radius: 12px;
    padding: 1rem 1.3rem;
    background: rgba(139,92,246,0.03);
    margin-bottom: 1.25rem;
}
.kn-takeaway-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #a855f7;
    margin-bottom: 0.55rem;
}
.kn-takeaway-item {
    font-size: 0.85rem;
    color: #cbd5e1;
    padding: 0.25rem 0;
    line-height: 1.55;
    border-bottom: 1px solid rgba(150,150,150,0.05);
}
.kn-takeaway-item:last-child { border-bottom: none; }
.kn-takeaway-num {
    display: inline-block;
    width: 18px;
    height: 18px;
    line-height: 18px;
    border-radius: 50%;
    background: rgba(168,85,247,0.15);
    color: #a855f7;
    text-align: center;
    font-size: 0.62rem;
    font-weight: 700;
    margin-right: 0.5rem;
}

/* Section header */
.kn-section {
    margin-top: 1.75rem;
    margin-bottom: 0.75rem;
}
.kn-section-title {
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: -0.01em;
}
.kn-section-desc {
    font-size: 0.78rem;
    color: #64748b;
    margin-top: 0.1rem;
}

/* Insight card */
.kn-card {
    border: 1px solid rgba(150,150,150,0.1);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    background: rgba(255,255,255,0.01);
    transition: border-color 0.15s;
}
.kn-card:hover {
    border-color: rgba(59,130,246,0.18);
}
.kn-card-title {
    font-weight: 700;
    font-size: 0.92rem;
    line-height: 1.35;
    margin-bottom: 0.2rem;
}
.kn-card-summary {
    font-size: 0.85rem;
    line-height: 1.6;
    color: #94a3b8;
}
.kn-card-evidence {
    list-style: none;
    padding: 0;
    margin: 0.5rem 0 0;
}
.kn-card-evidence li {
    font-size: 0.8rem;
    color: #94a3b8;
    padding: 0.15rem 0;
}
.kn-card-evidence li::before {
    content: "·";
    font-weight: 700;
    margin-right: 0.5rem;
}
.kn-card-evidence .kn-ev-val {
    color: #cbd5e1;
    font-weight: 500;
}
.kn-card-rec {
    font-size: 0.82rem;
    color: #3b82f6;
    margin-top: 0.4rem;
}
.kn-card-rec::before {
    content: "→ ";
    font-weight: 700;
}

/* Theme card */
.kn-theme-card {
    border-left: 3px solid;
    padding: 0.65rem 1rem;
    margin-bottom: 0.5rem;
    background: rgba(255,255,255,0.015);
    border-radius: 0 8px 8px 0;
}
.kn-theme-card:hover { background: rgba(255,255,255,0.035); }
.kn-theme-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
}
.kn-theme-label { font-weight: 700; font-size: 0.87rem; }
.kn-theme-quote {
    font-size: 0.82rem;
    color: #94a3b8;
    line-height: 1.6;
    font-style: italic;
}

/* Connection card */
.kn-conn-card {
    border: 1px solid rgba(168,85,247,0.18);
    border-radius: 10px;
    padding: 0.85rem 1.1rem;
    margin-bottom: 0.6rem;
    background: rgba(168,85,247,0.02);
}
.kn-conn-card:hover { border-color: rgba(168,85,247,0.3); }
.kn-conn-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.35rem;
    flex-wrap: wrap;
    gap: 0.3rem;
}
.kn-conn-label { font-weight: 700; font-size: 0.88rem; color: #a855f7; }
.kn-conn-badge {
    font-size: 0.6rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.04em; padding: 0.1rem 0.4rem; border-radius: 4px;
    background: rgba(168,85,247,0.12); color: #a855f7;
}
.kn-conn-quote {
    font-size: 0.82rem; color: #94a3b8; line-height: 1.6;
    font-style: italic; margin-bottom: 0.4rem;
}

/* Summary card */
.kn-summary-card {
    border: 1px solid rgba(150,150,150,0.1);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
    background: rgba(255,255,255,0.015);
}
.kn-summary-card:hover { border-color: rgba(59,130,246,0.2); }
.kn-summary-title { font-size: 0.95rem; font-weight: 700; margin-bottom: 0.3rem; }
.kn-summary-author { font-weight: 400; font-size: 0.82rem; color: #64748b; margin-left: 0.25rem; }
.kn-summary-stats { margin-bottom: 0.55rem; }
.kn-summary-body { font-size: 0.85rem; line-height: 1.7; color: #cbd5e1; }
.kn-summary-body p { margin: 0 0 0.4rem; }
.kn-summary-themes {
    margin-top: 0.5rem; padding-top: 0.4rem;
    border-top: 1px solid rgba(150,150,150,0.06);
}

/* Search */
.kn-search-result {
    border-left: 3px solid; padding: 0.65rem 1rem;
    margin-bottom: 0.5rem; background: rgba(255,255,255,0.02);
    border-radius: 0 8px 8px 0;
}
.kn-search-result:hover { background: rgba(255,255,255,0.035); }
.kn-search-quote { line-height: 1.65; font-size: 0.88rem; color: #e2e8f0; }
.kn-search-meta {
    display: flex; align-items: center; gap: 0.75rem; margin-top: 0.35rem;
}
.kn-search-book { font-size: 0.75rem; color: #94a3b8; }
.kn-search-bar-bg {
    flex: 1; max-width: 100px; height: 4px;
    background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden;
}
.kn-search-bar-fill { height: 100%; border-radius: 2px; }
.kn-search-score { font-size: 0.7rem; font-weight: 600; }

/* AI analysis panel */
.kn-ai-panel {
    border: 1px solid rgba(139,92,246,0.15);
    border-radius: 12px;
    padding: 1.25rem 1.4rem;
    background: rgba(139,92,246,0.02);
    margin-top: 1.5rem;
}
.kn-ai-panel-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.6rem;
}
.kn-ai-panel-title {
    font-size: 1.05rem;
    font-weight: 700;
}
.kn-ai-panel-desc {
    font-size: 0.82rem;
    color: #94a3b8;
    line-height: 1.55;
    margin-bottom: 0.75rem;
}
.kn-ai-panel-note {
    font-size: 0.72rem;
    color: #64748b;
    margin-top: 0.6rem;
}

/* Expander tweaks */
.kn-ri-page details { border: none !important; }
.kn-ri-page summary { font-weight: 600; }

/* Empty state */
.kn-empty {
    text-align: center; padding: 1.5rem 1rem;
    color: #64748b; font-size: 0.85rem; line-height: 1.6;
}
</style>""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Hero insight
# ---------------------------------------------------------------------------


def _pick_hero(cards: list[InsightCard]) -> InsightCard | None:
    if not cards:
        return None
    scored = []
    for c in cards:
        boost = _HERO_BOOSTS.get(c.category, 0.0)
        scored.append((c, c.priority_score + boost))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


def _render_hero(card: InsightCard) -> None:
    color = _CATEGORY_COLORS.get(card.category, _BLUE)
    framing = _HERO_FRAMINGS.get(card.category, "Key finding")

    rec_html = ""
    if card.recommendation:
        rec_html = (
            f'<div class="kn-hero-rec">'
            f"\u2192 {html_mod.escape(card.recommendation)}</div>"
        )

    st.markdown(
        f'<div class="kn-hero-insight" style="border-left-color:{color};">'
        f'<div class="kn-hero-eyebrow" style="color:{color};">'
        f"{html_mod.escape(framing)}</div>"
        f'<div class="kn-hero-title">{html_mod.escape(card.title)}</div>'
        f'<div class="kn-hero-summary">{html_mod.escape(card.summary)}</div>'
        f"{rec_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Reader profile strip
# ---------------------------------------------------------------------------


def _render_profile(books: list[Book], word_lookups: list) -> None:
    archetype = _compute_archetype(books, word_lookups)
    color = archetype["color"]
    rgb = _hex_to_rgb(color)
    emoji = archetype.get("emoji", "")

    total_hl = sum(
        sum(1 for a in b.annotations if a.kind == "highlight") for b in books
    )
    total_notes = sum(
        sum(1 for a in b.annotations if a.kind == "note") for b in books
    )
    total_time = sum(b.time_spent_reading or 0 for b in books)

    stats_html = (
        f'<div class="kn-profile-stat">'
        f'<div class="kn-profile-stat-val" style="color:{_BLUE};">{len(books)}</div>'
        f'<div class="kn-profile-stat-lbl">Books</div></div>'
        f'<div class="kn-profile-stat">'
        f'<div class="kn-profile-stat-val" style="color:{_AMBER};">{total_hl}</div>'
        f'<div class="kn-profile-stat-lbl">Highlights</div></div>'
        f'<div class="kn-profile-stat">'
        f'<div class="kn-profile-stat-val" style="color:{_PURPLE};">{total_notes}</div>'
        f'<div class="kn-profile-stat-lbl">Notes</div></div>'
    )
    if total_time > 0:
        stats_html += (
            f'<div class="kn-profile-stat">'
            f'<div class="kn-profile-stat-val" style="color:{_GREEN};">'
            f"{_format_time(total_time)}</div>"
            f'<div class="kn-profile-stat-lbl">Reading</div></div>'
        )

    st.markdown(
        f'<div class="kn-profile">'
        f'<div class="kn-profile-badge" style="background:rgba({rgb},0.12); color:{color};">'
        f'{emoji} {html_mod.escape(archetype["name"])}</div>'
        f'<div class="kn-profile-desc">'
        f'{html_mod.escape(archetype["description"])}</div>'
        f'<div class="kn-profile-stats">{stats_html}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Rediscover block
# ---------------------------------------------------------------------------


def _render_rediscover(books: list[Book]) -> None:
    """Show a random forgotten highlight from the reader's library."""
    # Use session_state to keep the same quote until refresh is clicked
    if "rediscover_quote" not in st.session_state:
        pick = _pick_rediscover(books)
        if pick:
            st.session_state["rediscover_quote"] = pick

    pick = st.session_state.get("rediscover_quote")
    if not pick:
        return

    text, title, age = pick
    age_html = f' · <span>{html_mod.escape(age)}</span>' if age else ""

    st.markdown(
        f'<div class="kn-rediscover">'
        f'<div class="kn-rediscover-eyebrow">Rediscover</div>'
        f'<div class="kn-rediscover-quote">'
        f"&ldquo;{html_mod.escape(text)}&rdquo;</div>"
        f'<div class="kn-rediscover-source">'
        f"— {html_mod.escape(title)}{age_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if st.button("Show another highlight", key="rediscover_refresh", type="tertiary"):
        new_pick = _pick_rediscover(books)
        if new_pick:
            st.session_state["rediscover_quote"] = new_pick
            st.rerun()


# ---------------------------------------------------------------------------
# Takeaway bar
# ---------------------------------------------------------------------------


def _render_takeaway_bar(takeaways: list[str]) -> None:
    if not takeaways:
        return
    items_html = ""
    for i, t in enumerate(takeaways, 1):
        items_html += (
            f'<div class="kn-takeaway-item">'
            f'<span class="kn-takeaway-num">{i}</span>'
            f"{html_mod.escape(t)}"
            f"</div>"
        )
    st.markdown(
        f'<div class="kn-takeaway-bar">'
        f'<div class="kn-takeaway-title">What Your Reading Data Says</div>'
        f"{items_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Insight card
# ---------------------------------------------------------------------------


def _render_card(card: InsightCard) -> None:
    color = _CATEGORY_COLORS.get(card.category, _BLUE)

    html_parts = [
        '<div class="kn-card">',
        f'<div style="margin-bottom:0.25rem;">{_category_pill(card.category)}</div>',
        f'<div class="kn-card-title" style="color:{color};">'
        f"{html_mod.escape(card.title)}</div>",
        f'<div class="kn-card-summary">{html_mod.escape(card.summary)}</div>',
    ]

    if card.related_books:
        pills = "".join(_pill(b, color) for b in card.related_books[:5])
        html_parts.append(f'<div style="margin-top:0.3rem;">{pills}</div>')

    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)

    has_detail = card.body or card.evidence or card.recommendation
    if has_detail:
        with st.expander("Details", expanded=False):
            if card.body:
                paragraphs = (
                    card.body.split("\n\n") if "\n\n" in card.body else [card.body]
                )
                for p in paragraphs:
                    if p.strip():
                        st.markdown(
                            f'<div style="font-size:0.85rem; line-height:1.7; '
                            f'color:#cbd5e1; margin-bottom:0.4rem;">'
                            f"{html_mod.escape(p.strip())}</div>",
                            unsafe_allow_html=True,
                        )
            if card.evidence:
                items = "".join(
                    f"<li>{html_mod.escape(ev.label)} — "
                    f'<span class="kn-ev-val">{html_mod.escape(ev.value)}</span></li>'
                    for ev in card.evidence
                )
                st.markdown(
                    f'<ul class="kn-card-evidence">{items}</ul>',
                    unsafe_allow_html=True,
                )
            if card.recommendation:
                st.markdown(
                    f'<div class="kn-card-rec">'
                    f"{html_mod.escape(card.recommendation)}</div>",
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# AI Analysis — opt-in, user-triggered
# ---------------------------------------------------------------------------


def _run_ai_analysis(books: list[Book]) -> tuple[list, list, list]:
    """Run full AI analysis: themes, clusters, summaries."""
    provider = _get_provider()
    if provider is None:
        return [], [], []

    from services.insights import cluster_highlights_across_books, detect_themes
    from services.summaries import generate_summary

    all_themes: list[ThemeCluster] = []
    for book in books:
        bh = [
            a for a in book.annotations
            if a.kind == "highlight" and a.text.strip()
        ]
        if len(bh) >= 3:
            all_themes.extend(detect_themes(book, provider))

    clusters = cluster_highlights_across_books(books, provider)

    summaries: list[BookSummary] = []
    for book in books:
        if book.annotations:
            book_themes = [t for t in all_themes if book.title in t.book_titles]
            summaries.append(generate_summary(book, themes=book_themes))

    st.session_state["ai_themes"] = all_themes
    st.session_state["ai_clusters"] = clusters
    st.session_state["ai_summaries"] = summaries
    total_ann = sum(len(b.annotations) for b in books)
    st.session_state["_ai_cache_key"] = f"ai_{len(books)}_{total_ann}"

    return all_themes, clusters, summaries


def _render_themes(themes: list[ThemeCluster], books: list[Book]) -> None:
    if not themes:
        return

    book_themes: dict[str, list[ThemeCluster]] = {}
    for theme in themes:
        book_title = theme.book_titles[0] if theme.book_titles else "Unknown"
        book_themes.setdefault(book_title, []).append(theme)

    for book_title, theme_list in book_themes.items():
        top_themes = sorted(theme_list, key=lambda t: t.size, reverse=True)[:5]
        total_hl = sum(t.size for t in top_themes)
        extra = len(theme_list) - len(top_themes)

        with st.expander(
            f"**{book_title}** — {len(top_themes)} themes \u00b7 {total_hl} highlights"
            + (f" (+{extra} more)" if extra > 0 else ""),
            expanded=len(book_themes) <= 3,
        ):
            for i, theme in enumerate(top_themes):
                color = _COLORS[i % len(_COLORS)]
                rep = html_mod.escape(theme.representative_text)
                if len(theme.representative_text) > 220:
                    rep = (
                        html_mod.escape(
                            theme.representative_text[:220].rsplit(" ", 1)[0]
                        )
                        + "\u2026"
                    )
                st.markdown(
                    f'<div class="kn-theme-card" style="border-left-color:{color};">'
                    f'<div class="kn-theme-header">'
                    f'<span class="kn-theme-label" style="color:{color};">'
                    f"{html_mod.escape(theme.label)}</span>"
                    f'{_pill(f"{theme.size} highlights", color)}'
                    f"</div>"
                    f'<div class="kn-theme-quote">&ldquo;{rep}&rdquo;</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )


def _render_connections(clusters: list[ThemeCluster]) -> None:
    cross_book = [c for c in clusters if len(c.book_titles) > 1]
    single_book = [c for c in clusters if len(c.book_titles) <= 1]

    if not cross_book and not single_book:
        return

    if cross_book:
        st.markdown(
            f'<div style="font-size:0.78rem; color:{_PURPLE}; font-weight:600; '
            f'margin-bottom:0.6rem;">'
            f'{len(cross_book)} idea{"s" if len(cross_book) != 1 else ""} '
            f"shared across multiple books</div>",
            unsafe_allow_html=True,
        )
        for cluster in cross_book:
            books_pills = "".join(
                _pill(t, _PURPLE) for t in cluster.book_titles[:5]
            )
            rep = html_mod.escape(cluster.representative_text)
            if len(cluster.representative_text) > 220:
                rep = (
                    html_mod.escape(
                        cluster.representative_text[:220].rsplit(" ", 1)[0]
                    )
                    + "\u2026"
                )
            st.markdown(
                f'<div class="kn-conn-card">'
                f'<div class="kn-conn-header">'
                f'<span class="kn-conn-label">'
                f"{html_mod.escape(cluster.label)}</span>"
                f"<div>"
                f'{_pill(f"{cluster.size} highlights", _PURPLE)} '
                f'<span class="kn-conn-badge">CROSS-BOOK</span></div>'
                f"</div>"
                f'<div class="kn-conn-quote">&ldquo;{rep}&rdquo;</div>'
                f"<div>{books_pills}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    if single_book:
        with st.expander(
            f"{len(single_book)} single-book cluster"
            f'{"s" if len(single_book) != 1 else ""}',
            expanded=False,
        ):
            for i, cluster in enumerate(single_book):
                color = _COLORS[i % len(_COLORS)]
                books_pills = "".join(
                    _pill(t, color) for t in cluster.book_titles[:3]
                )
                rep = html_mod.escape(cluster.representative_text)
                if len(cluster.representative_text) > 220:
                    rep = (
                        html_mod.escape(
                            cluster.representative_text[:220].rsplit(" ", 1)[0]
                        )
                        + "\u2026"
                    )
                st.markdown(
                    f'<div class="kn-card">'
                    f'<div class="kn-card-title" style="color:{color};">'
                    f"{html_mod.escape(cluster.label)}</div>"
                    f'<div class="kn-conn-quote">&ldquo;{rep}&rdquo;</div>'
                    f"<div>{books_pills} "
                    f'{_pill(f"{cluster.size} highlights", color)}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )


def _render_summaries(summaries: list[BookSummary], books: list[Book]) -> None:
    if not summaries:
        return

    book_map = {b.title: b for b in books}

    for i, s in enumerate(summaries):
        color = _COLORS[i % len(_COLORS)]
        book = book_map.get(s.book_title)

        stats: list[str] = [
            f"{s.highlight_count} highlight{'s' if s.highlight_count != 1 else ''}"
        ]
        if book:
            note_count = sum(1 for a in book.annotations if a.kind == "note")
            if note_count:
                stats.append(f"{note_count} note{'s' if note_count != 1 else ''}")
            if book.time_spent_reading and book.time_spent_reading > 0:
                stats.append(_format_time(book.time_spent_reading))
            if book.read_percent is not None:
                stats.append(f"{book.read_percent:.0f}% read")
            if book.rating and book.rating > 0:
                stats.append(f"Rated {book.rating}/5")

        stats_pills = "".join(_pill(st_text, color) for st_text in stats)
        theme_pills = (
            "".join(_pill(t, _PURPLE) for t in s.themes[:5]) if s.themes else ""
        )

        author = (
            f" by {html_mod.escape(book.author)}" if book and book.author else ""
        )

        paragraphs = (
            s.summary.split("\n\n") if "\n\n" in s.summary else [s.summary]
        )
        body_html = ""
        for p in paragraphs:
            if p.strip():
                body_html += f"<p>{html_mod.escape(p.strip())}</p>"

        themes_block = (
            f'<div class="kn-summary-themes">{theme_pills}</div>'
            if theme_pills
            else ""
        )

        st.markdown(
            f'<div class="kn-summary-card">'
            f'<div class="kn-summary-title" style="color:{color};">'
            f"{html_mod.escape(s.book_title)}"
            f'<span class="kn-summary-author">{author}</span></div>'
            f'<div class="kn-summary-stats">{stats_pills}</div>'
            f'<div class="kn-summary-body">{body_html}</div>'
            f"{themes_block}"
            f"</div>",
            unsafe_allow_html=True,
        )


def _render_search(books: list[Book]) -> None:
    st.markdown(
        '<div style="font-size:0.82rem; color:#64748b; margin-bottom:0.75rem;">'
        "Paste a highlight or type an idea to find similar passages across your library."
        "</div>",
        unsafe_allow_html=True,
    )
    query = st.text_input(
        "Search query",
        placeholder="Paste a highlight or type an idea\u2026",
        key="sim_search_query",
    )
    if query and st.button(
        "Find similar highlights", key="sim_search_btn", type="primary"
    ):
        provider = _get_provider()
        if provider is None:
            return
        from services.insights import find_similar_highlights

        with st.spinner("Searching\u2026"):
            results = find_similar_highlights(query, books, provider)
            st.session_state["sim_results"] = results

    if "sim_results" in st.session_state:
        results: list[HighlightSimilarity] = st.session_state["sim_results"]
        if not results:
            st.info("No similar highlights found above the similarity threshold.")
        else:
            st.markdown(
                f'<div style="font-size:0.72rem; color:#64748b; margin-bottom:0.5rem;">'
                f'{len(results)} match{"es" if len(results) != 1 else ""} found</div>',
                unsafe_allow_html=True,
            )
            for r in results:
                score_pct = f"{r.score * 100:.0f}%"
                score_color = (
                    _GREEN
                    if r.score >= 0.7
                    else _AMBER if r.score >= 0.5 else _BLUE
                )
                bar_w = r.score * 100
                st.markdown(
                    f'<div class="kn-search-result" style="border-left-color:{score_color};">'
                    f'<div class="kn-search-quote">'
                    f"&ldquo;{html_mod.escape(r.match_text)}&rdquo;</div>"
                    f'<div class="kn-search-meta">'
                    f'<span class="kn-search-book">'
                    f"{html_mod.escape(r.match_book)}</span>"
                    f'<div class="kn-search-bar-bg">'
                    f'<div class="kn-search-bar-fill" style="width:{bar_w:.0f}%; '
                    f'background:{score_color};"></div></div>'
                    f'<span class="kn-search-score" style="color:{score_color};">'
                    f"{score_pct}</span></div></div>",
                    unsafe_allow_html=True,
                )
    elif not query:
        st.markdown(
            '<div class="kn-empty">'
            '<div style="font-weight:600; margin-bottom:0.25rem;">'
            "Semantic highlight search</div>"
            "Type a phrase or idea above and click "
            "<strong>Find similar highlights</strong> "
            "to discover related passages across your entire library."
            "</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _render_export(cards: list[InsightCard]) -> None:
    if not cards:
        return

    from services.insight_export import export_insights_markdown, export_insights_text

    with st.expander("Export Insights", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            md = export_insights_markdown(cards)
            st.download_button(
                "Download Markdown",
                data=md,
                file_name="konotes-insights.md",
                mime="text/markdown",
                key="dl_insights_md",
            )
        with col2:
            txt = export_insights_text(cards)
            st.download_button(
                "Download Plain Text",
                data=txt,
                file_name="konotes-insights.txt",
                mime="text/plain",
                key="dl_insights_txt",
            )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def render_insights(books: list[Book]) -> None:
    """Render the Reading Intelligence page."""

    _inject_css()

    st.markdown('<div class="kn-ri-page">', unsafe_allow_html=True)

    # Title
    st.markdown(
        '<div style="margin-bottom:0.25rem;">'
        '<span style="font-size:1.6rem; font-weight:800; letter-spacing:-0.02em;">'
        "Reading Intelligence</span>"
        '<div style="font-size:0.85rem; color:#64748b; margin-top:0.15rem;">'
        "What your reading data says about you</div></div>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # 1. Build Insight Feed (computed — instant, no AI)
    # ------------------------------------------------------------------
    from services.insight_feed import build_feed, extract_takeaways

    word_lookups = st.session_state.get("word_lookups", [])
    all_cards = build_feed(books, word_lookups=word_lookups)

    # ------------------------------------------------------------------
    # 2. Reader Profile
    # ------------------------------------------------------------------
    _render_profile(books, word_lookups)

    # ------------------------------------------------------------------
    # 3. Rediscover — surface a forgotten highlight
    # ------------------------------------------------------------------
    _render_rediscover(books)

    # ------------------------------------------------------------------
    # 4. Hero Insight
    # ------------------------------------------------------------------
    hero = _pick_hero(all_cards)
    if hero:
        _render_hero(hero)

    # ------------------------------------------------------------------
    # 5. Key Findings
    # ------------------------------------------------------------------
    takeaways = extract_takeaways(all_cards)
    _render_takeaway_bar(takeaways)

    # ------------------------------------------------------------------
    # 6. Insight Sections (computed cards)
    # ------------------------------------------------------------------
    for section in _INSIGHT_SECTIONS:
        section_cards = [
            c
            for c in all_cards
            if c.category in section["categories"] and c != hero
        ]
        if not section_cards:
            continue

        st.markdown(
            f'<div class="kn-section">'
            f'<div class="kn-section-title">'
            f'{section["icon"]} {section["title"]}</div>'
            f'<div class="kn-section-desc">{section["description"]}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

        if len(section_cards) <= 3:
            for card in section_cards:
                _render_card(card)
        else:
            for card in section_cards[:2]:
                _render_card(card)
            with st.expander(
                f"{len(section_cards) - 2} more insight"
                f'{"s" if len(section_cards) - 2 != 1 else ""}',
                expanded=False,
            ):
                for card in section_cards[2:]:
                    _render_card(card)

    # Library Overview (standalone)
    overview_cards = [
        c for c in all_cards if c.category == "Library Overview" and c != hero
    ]
    for card in overview_cards:
        _render_card(card)

    # ------------------------------------------------------------------
    # 7. AI Deep Analysis — opt-in, user's choice
    # ------------------------------------------------------------------
    ai_on = _ai_available()
    highlights = [
        a
        for book in books
        for a in book.annotations
        if a.kind == "highlight" and a.text.strip()
    ]

    if ai_on and len(highlights) >= 3:
        themes: list[ThemeCluster] = st.session_state.get("ai_themes", [])
        clusters: list[ThemeCluster] = st.session_state.get("ai_clusters", [])
        summaries: list[BookSummary] = st.session_state.get("ai_summaries", [])
        has_results = bool(themes or clusters or summaries)

        st.markdown(
            '<div class="kn-ai-panel">'
            '<div class="kn-ai-panel-header">'
            '<span style="font-size:1.3rem;">🔬</span>'
            '<div class="kn-ai-panel-title">Deep Analysis</div>'
            "</div>"
            '<div class="kn-ai-panel-desc">'
            "Go deeper with on-device AI. Discover semantic themes in your highlights, "
            "find ideas that connect across different books, and generate reading summaries. "
            "All processing runs locally on your machine."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown("")

        # Action buttons
        col_all, col_t, col_c, col_s = st.columns([2.5, 1, 1, 1])
        with col_all:
            run_all = st.button(
                "Run Full Analysis",
                type="primary",
                key="ai_run_all",
            )
        with col_t:
            run_themes = st.button("Themes", key="ai_run_themes")
        with col_c:
            run_clusters = st.button("Connections", key="ai_run_clusters")
        with col_s:
            run_summaries = st.button("Summaries", key="ai_run_summaries")

        # Execute on button click
        if run_all:
            with st.spinner("Analyzing your reading patterns\u2026"):
                themes, clusters, summaries = _run_ai_analysis(books)

        if (run_themes or run_all) and not run_all:
            provider = _get_provider()
            if provider is not None:
                from services.insights import detect_themes
                with st.spinner("Detecting themes\u2026"):
                    all_themes_list: list[ThemeCluster] = []
                    for book in books:
                        bh = [a for a in book.annotations if a.kind == "highlight" and a.text.strip()]
                        if len(bh) >= 3:
                            all_themes_list.extend(detect_themes(book, provider))
                    st.session_state["ai_themes"] = all_themes_list
                    themes = all_themes_list

        if (run_clusters or run_all) and not run_all:
            provider = _get_provider()
            if provider is not None:
                from services.insights import cluster_highlights_across_books
                with st.spinner("Finding connections\u2026"):
                    result_clusters = cluster_highlights_across_books(books, provider)
                    st.session_state["ai_clusters"] = result_clusters
                    clusters = result_clusters

        if (run_summaries or run_all) and not run_all:
            from services.summaries import generate_summary
            with st.spinner("Generating summaries\u2026"):
                result_summaries: list[BookSummary] = []
                for book in books:
                    if book.annotations:
                        book_themes = [t for t in themes if book.title in t.book_titles]
                        result_summaries.append(generate_summary(book, themes=book_themes))
                st.session_state["ai_summaries"] = result_summaries
                summaries = result_summaries

        # Show results if we have any
        if themes or clusters or summaries:
            tabs = []
            tab_labels = []
            if themes:
                tab_labels.append(f"Themes ({len(themes)})")
            if clusters:
                tab_labels.append(f"Connections ({len(clusters)})")
            if summaries:
                tab_labels.append(f"Summaries ({len(summaries)})")
            tab_labels.append("Semantic Search")

            tabs = st.tabs(tab_labels)
            tab_idx = 0

            if themes:
                with tabs[tab_idx]:
                    st.markdown(
                        '<div class="kn-section">'
                        '<div class="kn-section-title">\U0001f4da Your Reading Themes</div>'
                        '<div class="kn-section-desc">'
                        "Semantic patterns detected in your highlights</div></div>",
                        unsafe_allow_html=True,
                    )
                    _render_themes(themes, books)
                tab_idx += 1

            if clusters:
                with tabs[tab_idx]:
                    st.markdown(
                        '<div class="kn-section">'
                        '<div class="kn-section-title">\U0001f517 Ideas Across Books</div>'
                        '<div class="kn-section-desc">'
                        "Highlights that echo across different titles</div></div>",
                        unsafe_allow_html=True,
                    )
                    _render_connections(clusters)
                tab_idx += 1

            if summaries:
                with tabs[tab_idx]:
                    st.markdown(
                        '<div class="kn-section">'
                        '<div class="kn-section-title">\U0001f4d6 Book Summaries</div>'
                        '<div class="kn-section-desc">'
                        "What you captured from each book</div></div>",
                        unsafe_allow_html=True,
                    )
                    _render_summaries(summaries, books)
                tab_idx += 1

            with tabs[tab_idx]:
                _render_search(books)
        else:
            # No results yet — just show search
            st.markdown("")
            _render_search(books)

    elif ai_on and len(highlights) < 3:
        st.markdown(
            '<div class="kn-empty">'
            '<div style="font-weight:600; margin-bottom:0.25rem;">'
            "Deep analysis needs more data</div>"
            "Keep reading and highlighting — once you have at least "
            "3 highlights, AI analysis will be available here."
            "</div>",
            unsafe_allow_html=True,
        )

    elif not ai_on:
        st.markdown("")
        st.markdown(
            '<div class="kn-ai-panel">'
            '<div class="kn-ai-panel-header">'
            '<span style="font-size:1.3rem;">🔬</span>'
            '<div class="kn-ai-panel-title">Want to Go Deeper?</div>'
            "</div>"
            '<div class="kn-ai-panel-desc">'
            "Install the optional AI package to discover semantic themes, "
            "find unexpected connections across books, generate reading summaries, "
            "and search your highlights by meaning."
            "<br><br>"
            "<code>pip install '.[ai]'</code>"
            "</div>"
            '<div class="kn-ai-panel-note">'
            "100% on-device \u2014 no API keys, no cloud, no data sharing."
            "</div></div>",
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # 8. Export
    # ------------------------------------------------------------------
    st.divider()
    _render_export(all_cards)

    # Soft star nudge — only if insights were rendered
    if all_cards:
        st.markdown(
            '<div style="text-align:center; font-size:0.78rem; color:#94a3b8; '
            'margin:1.5rem 0 0.5rem;">'
            "If these insights surprised you, consider "
            '<a href="https://github.com/texasbe2trill/KoNotes" '
            'style="color:#94a3b8; text-decoration:underline;">'
            "starring KoNotes</a> — it helps others find it."
            "</div>",
            unsafe_allow_html=True,
        )

    # Footer
    st.markdown(
        '<div class="kn-footer">'
        "Made with love for the Kobo community.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
