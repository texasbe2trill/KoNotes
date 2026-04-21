"""Reusable UI helpers for a cohesive KoNotes design system.

These helpers centralise the visual language for page headers, section
titles, chips/badges, metric pills, and empty states so every view
feels like part of one intentionally-designed product instead of a
collection of default Streamlit widgets.

All helpers render HTML via ``st.markdown(..., unsafe_allow_html=True)``.
They are pure presentation; no business logic lives here.
"""
from __future__ import annotations

import html as _html
from typing import Iterable

import streamlit as st


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------


def render_page_header(
    title: str,
    subtitle: str | None = None,
    *,
    eyebrow: str | None = None,
    meta: Iterable[str] | None = None,
    icon: str | None = None,
) -> None:
    """Render a polished, consistent page header.

    Args:
        title: Primary page title (rendered as an H2-sized heading).
        subtitle: Optional one-line description of what the page shows.
        eyebrow: Optional small uppercase label above the title.
        meta: Optional list of short metadata chips displayed under the
            subtitle (e.g. counts, filters, scope).
        icon: Optional emoji/character rendered inline beside the title.
    """
    parts: list[str] = ['<div class="kn-page-header">']

    if eyebrow:
        parts.append(
            f'<div class="kn-page-header__eyebrow">{_html.escape(eyebrow)}</div>'
        )

    title_html = _html.escape(title)
    if icon:
        title_html = (
            f'<span class="kn-page-header__icon">{_html.escape(icon)}</span>'
            f'{title_html}'
        )
    parts.append(f'<h2 class="kn-page-header__title">{title_html}</h2>')

    if subtitle:
        parts.append(
            f'<p class="kn-page-header__subtitle">{_html.escape(subtitle)}</p>'
        )

    meta_list = [m for m in (meta or []) if m]
    if meta_list:
        chips = "".join(
            f'<span class="kn-page-header__chip">{_html.escape(m)}</span>'
            for m in meta_list
        )
        parts.append(f'<div class="kn-page-header__meta">{chips}</div>')

    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------


def render_section_header(title: str, subtitle: str | None = None) -> None:
    """Render a section heading with optional one-line subtitle."""
    parts = [
        '<div class="kn-section">',
        f'<div class="kn-section__title">{_html.escape(title)}</div>',
    ]
    if subtitle:
        parts.append(
            f'<div class="kn-section__subtitle">{_html.escape(subtitle)}</div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chip / metric pill
# ---------------------------------------------------------------------------

_CHIP_TONES = {"neutral", "blue", "green", "amber", "purple", "rose", "cyan"}


def chip_html(label: str, tone: str = "neutral") -> str:
    """Return the HTML fragment for a small chip/tag."""
    tone = tone if tone in _CHIP_TONES else "neutral"
    return (
        f'<span class="kn-chip kn-chip--{tone}">{_html.escape(label)}</span>'
    )


def render_chip(label: str, tone: str = "neutral") -> None:
    """Render a single chip inline."""
    st.markdown(chip_html(label, tone), unsafe_allow_html=True)


def render_metric_pill(
    label: str,
    value: str,
    tone: str = "blue",
    sub: str | None = None,
) -> None:
    """Render a compact metric pill (label + big value + optional subtext)."""
    tone = tone if tone in _CHIP_TONES else "blue"
    parts = [
        f'<div class="kn-metric-pill kn-metric-pill--{tone}">',
        f'<div class="kn-metric-pill__value">{_html.escape(value)}</div>',
        f'<div class="kn-metric-pill__label">{_html.escape(label)}</div>',
    ]
    if sub:
        parts.append(
            f'<div class="kn-metric-pill__sub">{_html.escape(sub)}</div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------


def render_empty_state(
    title: str,
    body: str | None = None,
    *,
    icon: str = "📖",
    hint: str | None = None,
) -> None:
    """Render a warm, calm empty-state block.

    Used when a view has no data to show — gives the user a clear next
    step instead of an apologetic grey message.
    """
    parts = [
        '<div class="kn-empty">',
        f'<div class="kn-empty__icon">{_html.escape(icon)}</div>',
        f'<div class="kn-empty__title">{_html.escape(title)}</div>',
    ]
    if body:
        parts.append(
            f'<div class="kn-empty__body">{_html.escape(body)}</div>'
        )
    if hint:
        parts.append(
            f'<div class="kn-empty__hint">{_html.escape(hint)}</div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Divider
# ---------------------------------------------------------------------------


def render_soft_divider() -> None:
    """Render a subtle horizontal separator (lighter than ``st.divider``)."""
    st.markdown('<div class="kn-soft-divider"></div>', unsafe_allow_html=True)


__all__ = [
    "render_page_header",
    "render_section_header",
    "render_chip",
    "render_metric_pill",
    "render_empty_state",
    "render_soft_divider",
    "chip_html",
]
