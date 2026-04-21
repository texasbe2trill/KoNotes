"""Presentation components for the Insights page.

Reusable card renderers that keep the Insights page's visual language
consistent and easy to evolve. All helpers are pure presentation — they
accept already-computed :class:`~models.insight.InsightCard` objects
and render HTML/Streamlit widgets. No analytics or business logic.
"""
from __future__ import annotations

import html as _html
from typing import Callable, Iterable

import streamlit as st

from models.insight import EvidenceItem, InsightCard


# ---------------------------------------------------------------------------
# Evidence + recommendation sub-blocks
# ---------------------------------------------------------------------------


def _evidence_pills_html(evidence: Iterable[EvidenceItem], color: str) -> str:
    """Render evidence as compact labeled pills (label · value)."""
    pills: list[str] = []
    for ev in evidence:
        label = _html.escape(ev.label)
        value = _html.escape(ev.value)
        pills.append(
            '<span class="kn-ins-evidence-pill">'
            f'<span class="kn-ins-evidence-pill__label">{label}</span>'
            f'<span class="kn-ins-evidence-pill__value" '
            f'style="color:{color};">{value}</span>'
            "</span>"
        )
    return '<div class="kn-ins-evidence-row">' + "".join(pills) + "</div>"


def render_evidence_block(
    evidence: list[EvidenceItem],
    color: str,
    *,
    label: str = "Why KoNotes thinks this",
) -> None:
    """Render the evidence-pill strip with an optional eyebrow label."""
    if not evidence:
        return
    st.markdown(
        f'<div class="kn-ins-evidence">'
        f'<div class="kn-ins-evidence__label">{_html.escape(label)}</div>'
        f"{_evidence_pills_html(evidence, color)}"
        "</div>",
        unsafe_allow_html=True,
    )


def render_recommendation_block(
    text: str,
    color: str,
    *,
    label: str = "What to do next",
) -> None:
    """Render the 'What to do next' callout inside a card."""
    if not text:
        return
    st.markdown(
        f'<div class="kn-ins-rec" style="border-color:{color};">'
        f'<div class="kn-ins-rec__label" style="color:{color};">'
        f"{_html.escape(label)}</div>"
        f'<div class="kn-ins-rec__body">{_html.escape(text)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Featured / hero insight card
# ---------------------------------------------------------------------------


def render_featured_insight(
    card: InsightCard,
    *,
    color: str,
    framing: str,
    share_callback: Callable[[InsightCard], None] | None = None,
) -> None:
    """Render the single top-of-page hero insight.

    Args:
        card: The insight to feature.
        color: Accent colour (hex) for the left bar and highlights.
        framing: Small uppercase label shown above the title
            (e.g. "Strongest signal", "Your deepest engagement").
        share_callback: Optional function invoked to render share
            actions under the card. Invoked with ``card``.
    """
    title = _html.escape(card.title)
    summary = _html.escape(card.summary)

    st.markdown(
        f'<div class="kn-ins-hero" style="--kn-accent:{color};">'
        '<div class="kn-ins-hero__topline">'
        f'<span class="kn-ins-hero__eyebrow">{_html.escape(framing)}</span>'
        '<span class="kn-ins-hero__badge">Share-worthy insight</span>'
        "</div>"
        f'<h3 class="kn-ins-hero__title">{title}</h3>'
        f'<p class="kn-ins-hero__summary">{summary}</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    if card.evidence:
        render_evidence_block(card.evidence, color)

    if card.recommendation:
        render_recommendation_block(card.recommendation, color)

    if share_callback is not None:
        share_callback(card)


# ---------------------------------------------------------------------------
# Supporting insight card
# ---------------------------------------------------------------------------


def render_insight_card(
    card: InsightCard,
    *,
    color: str,
    category_pill_html: str | None = None,
    detail_renderer: Callable[[InsightCard], None] | None = None,
    share_renderer: Callable[[InsightCard], None] | None = None,
    show_share: bool = True,
) -> None:
    """Render a non-hero insight card with consistent hierarchy.

    Collapsed state stays concise: category chip, title, summary.
    Expanded state reveals body (when available), evidence pills, and a
    recommendation callout, followed by share actions.

    Args:
        card: The insight card to render.
        color: Accent colour (hex) for title and accents.
        category_pill_html: Optional pre-rendered HTML for the category chip.
        detail_renderer: Optional override for the expanded body. When
            supplied, it replaces the default body paragraphs rendering.
        share_renderer: Optional callable invoked to render share actions.
        show_share: When False, share actions are suppressed even if a
            renderer is provided (used for low-signal cards).
    """
    title = _html.escape(card.title)
    summary = _html.escape(card.summary)

    parts: list[str] = ['<div class="kn-ins-card">']
    if category_pill_html:
        parts.append(
            f'<div class="kn-ins-card__chip">{category_pill_html}</div>'
        )
    parts.append(
        f'<div class="kn-ins-card__title" style="color:{color};">{title}</div>'
    )
    parts.append(
        f'<div class="kn-ins-card__summary">{summary}</div>'
    )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)

    has_detail = bool(card.body or card.evidence or card.recommendation)
    if has_detail:
        with st.expander("Details", expanded=False):
            if detail_renderer is not None:
                detail_renderer(card)
            elif card.body:
                for paragraph in _split_paragraphs(card.body):
                    st.markdown(
                        f'<div class="kn-ins-card__body">{_html.escape(paragraph)}</div>',
                        unsafe_allow_html=True,
                    )
            if card.evidence:
                render_evidence_block(card.evidence, color)
            if card.recommendation:
                render_recommendation_block(card.recommendation, color)

    if show_share and share_renderer is not None:
        share_renderer(card)


def _split_paragraphs(body: str) -> list[str]:
    """Split a body string into paragraphs, preserving non-empty content."""
    parts = body.split("\n\n") if "\n\n" in body else [body]
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Empty / low-data state
# ---------------------------------------------------------------------------


def render_empty_insights_state(
    *,
    title: str = "Insights arrive as you read",
    body: str = (
        "Add a few more highlights or notes to unlock deeper patterns. "
        "KoNotes grows more personal with every passage you mark."
    ),
    hint: str | None = "Tip: a dozen highlights is usually enough to surface the first themes.",
) -> None:
    """Render a warm, reader-friendly empty/low-data state for Insights."""
    parts = [
        '<div class="kn-empty kn-ins-empty">',
        '<div class="kn-empty__icon">📖</div>',
        f'<div class="kn-empty__title">{_html.escape(title)}</div>',
        f'<div class="kn-empty__body">{_html.escape(body)}</div>',
    ]
    if hint:
        parts.append(
            f'<div class="kn-empty__hint">{_html.escape(hint)}</div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


__all__ = [
    "render_featured_insight",
    "render_insight_card",
    "render_evidence_block",
    "render_recommendation_block",
    "render_empty_insights_state",
]
