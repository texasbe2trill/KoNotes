"""Recommendation card component — renders Recommendation objects in the Streamlit UI."""
from __future__ import annotations

from html import escape

import streamlit as st

from models.recommendation import (
    KIND_COMPARE,
    KIND_DEEPEST_THINKING,
    KIND_EXPORT,
    KIND_FINISH,
    KIND_FORGOTTEN_GEM,
    KIND_REVISIT,
    Recommendation,
)

# Human-readable labels for each recommendation kind
_KIND_LABELS: dict[str, str] = {
    KIND_REVISIT: "Revisit",
    KIND_FINISH: "Finish next",
    KIND_EXPORT: "Export next",
    KIND_FORGOTTEN_GEM: "Forgotten gem",
    KIND_DEEPEST_THINKING: "Deepest thinking",
    KIND_COMPARE: "Compare",
}

# Accent colours — use primary-color for revisit, distinct hues for the rest
_KIND_COLORS: dict[str, str] = {
    KIND_REVISIT: "var(--primary-color)",
    KIND_FINISH: "#22c55e",
    KIND_EXPORT: "#f59e0b",
    KIND_FORGOTTEN_GEM: "#a78bfa",
    KIND_DEEPEST_THINKING: "#06b6d4",
    KIND_COMPARE: "#f472b6",
}


def render_recommendation_card(
    rec: Recommendation,
    *,
    show_share: bool = False,
) -> None:
    """Render a single recommendation card.

    Parameters
    ----------
    rec:
        The recommendation to render.
    show_share:
        When True, show Copy and Bluesky share buttons below the card.
    """
    kind_label = _KIND_LABELS.get(rec.kind, rec.kind.replace("_", " ").title())
    kind_color = _KIND_COLORS.get(rec.kind, "var(--primary-color)")

    evidence_html = "".join(f"<li>{escape(item)}</li>" for item in rec.evidence)
    evidence_block = (
        f"<ul class='kn-rec-evidence'>{evidence_html}</ul>" if evidence_html else ""
    )

    st.markdown(
        f"""
        <div class="kn-rec-card">
            <div class="kn-rec-badge" style="color:{kind_color};">{escape(kind_label)}</div>
            <div class="kn-rec-title">{escape(rec.title)}</div>
            <div class="kn-rec-summary">{escape(rec.summary)}</div>
            <div class="kn-rec-reason">{escape(rec.reason)}</div>
            {evidence_block}
            <div class="kn-rec-action">{escape(rec.recommended_action)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if show_share:
        _render_share_row(rec)


def render_recommendation_section(
    recs: list[Recommendation],
    *,
    show_share: bool = False,
    heading: str = "Recommended next steps",
) -> None:
    """Render a section of up to three recommendation cards in a column layout.

    Parameters
    ----------
    recs:
        Ranked list of recommendations to display (only the first three are shown).
    show_share:
        Passed through to each card — enables copy/share buttons.
    heading:
        Section heading text.
    """
    if not recs:
        return

    st.markdown(
        f"<div class='kn-rec-section-title'>{escape(heading)}</div>",
        unsafe_allow_html=True,
    )

    visible = recs[:3]
    cols = st.columns(len(visible))
    for col, rec in zip(cols, visible):
        with col:
            render_recommendation_card(rec, show_share=show_share)


# ---------------------------------------------------------------------------
# Share helpers (used when show_share=True)
# ---------------------------------------------------------------------------


def _build_copy_text(rec: Recommendation) -> str:
    """Plain-text representation for the copy popover."""
    lines = [rec.title, "", rec.summary, "", f"Why: {rec.reason}"]
    if rec.evidence:
        lines.append("")
        lines.extend(f"- {item}" for item in rec.evidence)
    if rec.recommended_action:
        lines.append("")
        lines.append(f"Next step: {rec.recommended_action}")
    lines.append("")
    lines.append("(via KoNotes \u2014 https://konotes.streamlit.app)")
    return "\n".join(lines)


def _render_share_row(rec: Recommendation) -> None:
    """Render Copy and optional Bluesky share buttons for a recommendation card."""
    # Import here to avoid a hard circular dependency at module load time
    from services import share_formatter  # noqa: PLC0415
    from services.share_links import build_bluesky_share_url  # noqa: PLC0415

    copy_text = _build_copy_text(rec)
    formatter = getattr(share_formatter, "format_recommendation_for_bluesky", None)

    _, col_copy, col_share, _ = st.columns([1.4, 1.8, 1.8, 1.4])
    with col_copy:
        with st.popover("Copy", use_container_width=True):
            st.caption("Select and copy:")
            st.code(copy_text, language=None)

    if callable(formatter):
        share_text = formatter(rec)
        bluesky_url = build_bluesky_share_url(share_text) # pyright: ignore[reportArgumentType]
        with col_share:
            st.link_button("Share on Bluesky", bluesky_url, use_container_width=True)
