"""Tests for the modular insight card presentation helpers."""
from __future__ import annotations

from unittest.mock import patch

from app.components import insight_card as ic
from models.insight import EvidenceItem, InsightCard


def _card(
    *,
    title: str = "Your reading leans toward stoicism",
    summary: str = "You're consistently drawn to passages about resilience.",
    body: str = "",
    evidence: list[EvidenceItem] | None = None,
    recommendation: str = "",
    category: str = "pattern",
    related_books: list[str] | None = None,
) -> InsightCard:
    return InsightCard(
        id="t",
        category=category,
        title=title,
        summary=summary,
        body=body,
        evidence=evidence or [],
        recommendation=recommendation,
        related_books=related_books or [],
        priority_score=1.0,
    )


# ---------------------------------------------------------------------------
# Featured / hero
# ---------------------------------------------------------------------------


def test_render_featured_insight_minimal_does_not_crash() -> None:
    card = _card()
    with patch("app.components.insight_card.st.markdown") as md:
        ic.render_featured_insight(card, color="#6366f1", framing="Key finding")
    html = "".join(call.args[0] for call in md.call_args_list)
    assert "kn-ins-hero" in html
    assert "Share-worthy insight" in html
    assert "Key finding" in html
    assert "Your reading leans toward stoicism" in html


def test_render_featured_insight_includes_evidence_and_rec() -> None:
    card = _card(
        evidence=[
            EvidenceItem(label="Highlights", value="128"),
            EvidenceItem(label="Books", value="4"),
        ],
        recommendation="Try a long-form essay this weekend.",
    )
    with patch("app.components.insight_card.st.markdown") as md:
        ic.render_featured_insight(card, color="#10b981", framing="Deep dive")
    html = "".join(call.args[0] for call in md.call_args_list)
    assert "kn-ins-evidence-pill" in html
    assert "Highlights" in html and "128" in html
    assert "kn-ins-rec" in html
    assert "What to do next" in html
    assert "Try a long-form essay this weekend." in html


def test_render_featured_insight_invokes_share_callback() -> None:
    card = _card()
    calls: list[InsightCard] = []
    with patch("app.components.insight_card.st.markdown"):
        ic.render_featured_insight(
            card,
            color="#6366f1",
            framing="Key finding",
            share_callback=lambda c: calls.append(c),
        )
    assert calls == [card]


# ---------------------------------------------------------------------------
# Supporting card
# ---------------------------------------------------------------------------


def test_render_insight_card_minimal_has_no_expander() -> None:
    card = _card()
    with patch("app.components.insight_card.st.markdown") as md, \
         patch("app.components.insight_card.st.expander") as expander:
        ic.render_insight_card(card, color="#6366f1")
    html = "".join(call.args[0] for call in md.call_args_list)
    assert "kn-ins-card" in html
    assert "Your reading leans toward stoicism" in html
    expander.assert_not_called()


def test_render_insight_card_with_detail_opens_expander() -> None:
    card = _card(
        body="First paragraph.\n\nSecond paragraph.",
        evidence=[EvidenceItem(label="Notes", value="7")],
        recommendation="Follow the thread.",
    )
    with patch("app.components.insight_card.st.markdown"), \
         patch("app.components.insight_card.st.expander") as expander:
        ic.render_insight_card(card, color="#6366f1")
    expander.assert_called_once()
    args, _ = expander.call_args
    assert args[0] == "Details"


def test_render_insight_card_share_suppressed_when_show_share_false() -> None:
    card = _card()
    called: list[InsightCard] = []
    with patch("app.components.insight_card.st.markdown"):
        ic.render_insight_card(
            card,
            color="#6366f1",
            share_renderer=lambda c: called.append(c),
            show_share=False,
        )
    assert called == []


def test_render_insight_card_uses_category_pill_html() -> None:
    card = _card()
    with patch("app.components.insight_card.st.markdown") as md:
        ic.render_insight_card(
            card,
            color="#6366f1",
            category_pill_html='<span class="pill">Pattern</span>',
        )
    html = "".join(call.args[0] for call in md.call_args_list)
    assert '<span class="pill">Pattern</span>' in html


# ---------------------------------------------------------------------------
# Evidence / recommendation block no-ops on empty input
# ---------------------------------------------------------------------------


def test_render_evidence_block_empty_is_noop() -> None:
    with patch("app.components.insight_card.st.markdown") as md:
        ic.render_evidence_block([], color="#6366f1")
    md.assert_not_called()


def test_render_recommendation_block_empty_is_noop() -> None:
    with patch("app.components.insight_card.st.markdown") as md:
        ic.render_recommendation_block("", color="#6366f1")
    md.assert_not_called()


def test_render_recommendation_block_renders_label_and_body() -> None:
    with patch("app.components.insight_card.st.markdown") as md:
        ic.render_recommendation_block(
            "Revisit Meditations this week.", color="#10b981"
        )
    html = md.call_args.args[0]
    assert "What to do next" in html
    assert "Revisit Meditations this week." in html
    assert "#10b981" in html


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------


def test_render_empty_insights_state_defaults() -> None:
    with patch("app.components.insight_card.st.markdown") as md:
        ic.render_empty_insights_state()
    html = md.call_args.args[0]
    assert "kn-empty" in html
    assert "kn-ins-empty" in html
    assert "Insights arrive as you read" in html


def test_render_empty_insights_state_custom_strings() -> None:
    with patch("app.components.insight_card.st.markdown") as md:
        ic.render_empty_insights_state(
            title="Nothing yet",
            body="Import a file to begin.",
            hint=None,
        )
    html = md.call_args.args[0]
    assert "Nothing yet" in html
    assert "Import a file to begin." in html
    assert "kn-empty__hint" not in html
