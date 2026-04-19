"""Insight share actions — lightweight UI components for sharing insights.

Renders subtle "Copy" and "Share on Bluesky" actions beneath insight cards
that meet the share-worthiness threshold.
"""
from __future__ import annotations

import streamlit as st

from models.insight import InsightCard
from services.share_formatter import (
    format_insight_for_bluesky,
    format_insight_for_copy,
    is_shareworthy,
)
from services.share_links import build_bluesky_share_url


def render_share_actions(card: InsightCard) -> None:
    """Render share actions for a single insight card.

    Only renders if the card passes the share-worthiness check.
    Actions: Copy insight text, Share on Bluesky.
    """
    if not is_shareworthy(card):
        return

    copy_key = f"share_copy_{card.id}"
    bsky_text = format_insight_for_bluesky(card)
    bsky_url = build_bluesky_share_url(bsky_text)

    col_copy, col_bsky, col_spacer = st.columns([1, 1, 3])

    with col_copy:
        if st.button("📋 Copy", key=copy_key, help="Copy this insight"):
            copy_text = format_insight_for_copy(card)
            st.session_state[f"_copied_{card.id}"] = copy_text

    with col_bsky:
        st.link_button(
            "🦋 Share on Bluesky",
            url=bsky_url,
            help="Open Bluesky with this insight pre-filled",
        )

    # Show copy result if the user just clicked Copy
    copied = st.session_state.get(f"_copied_{card.id}")
    if copied:
        st.text_area(
            "Copied — select all and copy:",
            value=copied,
            height=120,
            key=f"_copied_area_{card.id}",
        )
        if st.button("Dismiss", key=f"_dismiss_{card.id}"):
            del st.session_state[f"_copied_{card.id}"]
            st.rerun()
