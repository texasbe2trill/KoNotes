"""Storyboard / dashboard composition helpers for the Insights page.

These helpers are pure layout primitives — they accept already-computed
data (insight cards, stats, archetype dicts) and arrange them into the
new dashboard structure:

- ``render_hero_row``       — featured insight + quick stats + next action
- ``render_quick_stats_panel``
- ``render_next_action_panel``
- ``render_storyboard_card`` — compact card for the insight grid
- ``render_insight_grid``   — 2-column responsive grid of compact cards
- ``render_analysis_workspace`` — tabbed deep analysis container
- ``render_tools_footer``   — compact bottom row (export + share + star)

All visual treatments live in ``app/assets/styles.css`` section 29.
"""
from __future__ import annotations

import html as _html
from typing import Callable, Iterable

import streamlit as st

from models.insight import EvidenceItem, InsightCard


# ---------------------------------------------------------------------------
# Layer 1 — Hero row
# ---------------------------------------------------------------------------


def render_hero_row(
    *,
    featured_renderer: Callable[[], None],
    quick_stats: list[tuple[str, str, str]] | None = None,
    archetype: dict | None = None,
    next_action: dict | None = None,
) -> None:
    """Render the dashboard hero row.

    Layout:
        [ featured insight (wide, ~7) ] [ stats / next action (~5) ]

    Args:
        featured_renderer: Callable that renders the featured insight in-place
            (the existing ``_render_hero`` style call). Called inside the
            left column.
        quick_stats: Optional list of ``(label, value, color_hex)`` tuples to
            show in the right column's stats panel.
        archetype: Optional archetype dict (from ``_compute_archetype``) used
            to label the stats panel with the reader identity.
        next_action: Optional ``{"title", "body", "cta_label", "cta_callback"}``
            dict. ``cta_callback`` is invoked when the action button is clicked.
    """
    left, right = st.columns([7, 5], gap="large")
    with left:
        st.markdown('<div class="kn-dash-hero-cell">', unsafe_allow_html=True)
        featured_renderer()
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        if quick_stats or archetype:
            render_quick_stats_panel(stats=quick_stats or [], archetype=archetype)
        if next_action:
            render_next_action_panel(**next_action)


def render_quick_stats_panel(
    *,
    stats: list[tuple[str, str, str]],
    archetype: dict | None = None,
) -> None:
    """Compact reader identity + key stat tiles."""
    badge_html = ""
    desc_html = ""
    if archetype:
        emoji = _html.escape(str(archetype.get("emoji", "")))
        name = _html.escape(str(archetype.get("name", "")))
        color = archetype.get("color", "#3b82f6")
        desc = _html.escape(str(archetype.get("description", "")))
        badge_html = (
            f'<div class="kn-dash-identity">'
            f'<span class="kn-dash-identity__emoji">{emoji}</span>'
            f'<span class="kn-dash-identity__name" style="color:{color};">{name}</span>'
            f"</div>"
        )
        if desc:
            desc_html = f'<div class="kn-dash-identity__desc">{desc}</div>'

    tiles_html = ""
    for label, value, color in stats:
        tiles_html += (
            '<div class="kn-dash-tile">'
            f'<div class="kn-dash-tile__val" style="color:{color};">'
            f"{_html.escape(value)}</div>"
            f'<div class="kn-dash-tile__lbl">{_html.escape(label)}</div>'
            "</div>"
        )

    st.markdown(
        '<div class="kn-dash-side kn-dash-stats">'
        f"{badge_html}"
        f"{desc_html}"
        f'<div class="kn-dash-tile-row">{tiles_html}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def render_next_action_panel(
    *,
    title: str,
    body: str,
    cta_label: str,
    cta_callback: Callable[[], None] | None = None,
    cta_key: str = "kn_dash_next_action",
    color: str = "#a855f7",
) -> None:
    """Compact 'what to do next' callout with one primary action."""
    st.markdown(
        '<div class="kn-dash-side kn-dash-next">'
        f'<div class="kn-dash-next__eyebrow" style="color:{color};">'
        "Next best action</div>"
        f'<div class="kn-dash-next__title">{_html.escape(title)}</div>'
        f'<div class="kn-dash-next__body">{_html.escape(body)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    if cta_callback is not None:
        if st.button(cta_label, key=cta_key, type="secondary", use_container_width=True):
            cta_callback()


# ---------------------------------------------------------------------------
# Layer 2 — Storyboard insight grid
# ---------------------------------------------------------------------------


def render_storyboard_card(
    card: InsightCard,
    *,
    color: str,
    category_label: str | None = None,
    on_open: Callable[[InsightCard], None] | None = None,
    open_key: str | None = None,
) -> None:
    """Render a single compact card for the insight grid.

    Concise by default (chip + title + 1-2 sentence summary + 2-4 evidence
    chips). The optional ``on_open`` callback drives an "Open details"
    action — typically used to seed a session-state key consumed by an
    inline expander/drawer.
    """
    label = category_label or card.category
    chips_html = _evidence_chips_html(card.evidence[:4], color=color)

    st.markdown(
        '<div class="kn-story-card">'
        f'<div class="kn-story-card__cat" style="color:{color};">'
        f"{_html.escape(label)}</div>"
        f'<div class="kn-story-card__title">{_html.escape(card.title)}</div>'
        f'<div class="kn-story-card__summary">{_html.escape(card.summary)}</div>'
        f"{chips_html}"
        "</div>",
        unsafe_allow_html=True,
    )

    if on_open is not None and (card.body or card.evidence or card.recommendation):
        if st.button(
            "Open details",
            key=open_key or f"kn_story_open_{card.id}",
            type="tertiary",
            use_container_width=False,
        ):
            on_open(card)


def render_insight_grid(
    cards: Iterable[InsightCard],
    *,
    columns: int = 2,
    color_for: Callable[[InsightCard], str],
    label_for: Callable[[InsightCard], str] | None = None,
    on_open: Callable[[InsightCard], None] | None = None,
) -> None:
    """Render an arbitrary list of insight cards in an N-column grid."""
    items = list(cards)
    if not items:
        return

    columns = max(1, columns)
    for row_start in range(0, len(items), columns):
        row = items[row_start : row_start + columns]
        cols = st.columns(columns, gap="medium")
        for offset, card in enumerate(row):
            with cols[offset]:
                render_storyboard_card(
                    card,
                    color=color_for(card),
                    category_label=label_for(card) if label_for else None,
                    on_open=on_open,
                    open_key=f"kn_story_open_{row_start + offset}_{card.id}",
                )
        # Pad empty cells so the grid keeps even rhythm
        for offset in range(len(row), columns):
            with cols[offset]:
                st.markdown(
                    '<div class="kn-story-card kn-story-card--ghost"></div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Layer 3 — Deep analysis workspace
# ---------------------------------------------------------------------------


def render_analysis_workspace(
    *,
    intro: str,
    tabs: list[tuple[str, Callable[[], None]]],
    actions_renderer: Callable[[], None] | None = None,
) -> None:
    """Render the tabbed deep-analysis workspace.

    Args:
        intro: A single short sentence shown above the tabs.
        tabs: List of ``(label, renderer)`` tuples. Each renderer is invoked
            inside its own tab.
        actions_renderer: Optional callable that renders compact action
            buttons above the tabs (e.g. "Run Full Analysis" / per-feature
            buttons). When supplied, it is given an aligned, lighter row.
    """
    st.markdown(
        '<div class="kn-dash-workspace">'
        '<div class="kn-dash-workspace__head">'
        '<div class="kn-dash-workspace__title">Deep Analysis</div>'
        f'<div class="kn-dash-workspace__intro">{_html.escape(intro)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    if actions_renderer is not None:
        st.markdown('<div class="kn-dash-workspace__actions">', unsafe_allow_html=True)
        actions_renderer()
        st.markdown("</div>", unsafe_allow_html=True)

    if tabs:
        labels = [label for label, _ in tabs]
        renderers = [r for _, r in tabs]
        tab_objs = st.tabs(labels)
        for tab_obj, renderer in zip(tab_objs, renderers):
            with tab_obj:
                renderer()

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Layer 4 — Tools footer
# ---------------------------------------------------------------------------


def render_tools_footer(
    *,
    export_renderer: Callable[[], None] | None = None,
    extra_renderers: list[tuple[str, Callable[[], None]]] | None = None,
) -> None:
    """Compact footer row for utility actions (export, etc.).

    Args:
        export_renderer: Callable that renders export controls.
        extra_renderers: Optional list of ``(title, renderer)`` tuples
            rendered as additional compact tools side-by-side.
    """
    panels: list[tuple[str, Callable[[], None]]] = []
    if export_renderer is not None:
        panels.append(("Export", export_renderer))
    if extra_renderers:
        panels.extend(extra_renderers)
    if not panels:
        return

    st.markdown('<div class="kn-dash-tools">', unsafe_allow_html=True)
    cols = st.columns(len(panels), gap="medium")
    for col, (title, renderer) in zip(cols, panels):
        with col:
            st.markdown(
                f'<div class="kn-dash-tools__title">{_html.escape(title)}</div>',
                unsafe_allow_html=True,
            )
            renderer()
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _evidence_chips_html(evidence: list[EvidenceItem], *, color: str) -> str:
    if not evidence:
        return ""
    chips = []
    for ev in evidence:
        chips.append(
            '<span class="kn-story-chip">'
            f'<span class="kn-story-chip__lbl">{_html.escape(ev.label)}</span>'
            f'<span class="kn-story-chip__val" style="color:{color};">'
            f"{_html.escape(ev.value)}</span>"
            "</span>"
        )
    return '<div class="kn-story-chip-row">' + "".join(chips) + "</div>"


__all__ = [
    "render_hero_row",
    "render_quick_stats_panel",
    "render_next_action_panel",
    "render_storyboard_card",
    "render_insight_grid",
    "render_analysis_workspace",
    "render_tools_footer",
]
