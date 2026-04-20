"""Hero insight component — the headline section at the top of the Overview."""
from __future__ import annotations

from html import escape

import streamlit as st

from services.hero_insight_engine import HeroInsight
from services import share_formatter
from services.share_links import build_bluesky_share_url


def render_hero_insight(insight: HeroInsight) -> None:
    """Render the hero insight as a visually distinct callout."""
    bullets_html = "".join(
        f"<li>{escape(item)}</li>" for item in insight.evidence
    )
    bullets_block = f"<ul class='kn-hero-evidence'>{bullets_html}</ul>" if bullets_html else ""

    rec_block = (
        f"<div class='kn-hero-rec'>{escape(insight.recommendation)}</div>"
        if insight.recommendation
        else ""
    )

    fallback_class = " kn-hero--fallback" if insight.is_fallback else ""

    # Identity reinforcement line — subtle, sits between title and summary.
    identity_block = (
        "<div class='kn-hero-identity'>This is your dominant reading pattern.</div>"
        if not insight.is_fallback
        else ""
    )

    st.markdown(
        f"""
        <div class="kn-hero{fallback_class}">
            <div class="kn-hero-eyebrow">Reading pattern detected</div>
            <div class="kn-hero-title">{escape(insight.title)}</div>
            {identity_block}
            <div class="kn-hero-summary">{escape(insight.summary)}</div>
            {bullets_block}
            {rec_block}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if insight.is_fallback:
        return

    copy_text = _build_copy_text(insight)
    formatter = getattr(share_formatter, "format_hero_for_bluesky", None)
    if callable(formatter):
        share_text = formatter(insight)
    else:
        # Fallback keeps sharing functional if an older module version is loaded.
        share_text = f"{insight.summary}\n\nhttps://konotes.streamlit.app/\n\n#booksky"

    bluesky_url = build_bluesky_share_url(share_text) # pyright: ignore[reportArgumentType]

    _, col_copy, col_share, _ = st.columns([1.4, 1.8, 1.8, 1.4])
    with col_copy:
        with st.popover("Copy insight", use_container_width=True):
            st.caption("Select and copy:")
            st.code(copy_text, language=None)
    with col_share:
        st.link_button("Share on Bluesky", bluesky_url, use_container_width=True)

    st.markdown(
        "<div class='kn-hero-footnote'>If this feels accurate, it's probably worth keeping.</div>",
        unsafe_allow_html=True,
    )

    # Curiosity hook — directional, not clickable.
    st.markdown(
        "<div class='kn-hero-hook'>Want to see what else stands out in your reading?</div>",
        unsafe_allow_html=True,
    )


def _build_copy_text(insight: HeroInsight) -> str:
    """Plain-text version for the Copy popover (richer than the share post)."""
    lines = [insight.title, "", insight.summary]
    if insight.evidence:
        lines.append("")
        lines.extend(f"- {item}" for item in insight.evidence)
    if insight.recommendation:
        lines.append("")
        lines.append(insight.recommendation)
    lines.append("")
    lines.append("(via KoNotes — https://konotes.streamlit.app)")
    return "\n".join(lines)
