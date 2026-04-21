"""Tests for the storyboard/dashboard composition helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.components import insights_dashboard as dash
from models.insight import EvidenceItem, InsightCard


def _card(**kw) -> InsightCard:
    defaults = dict(
        id="t",
        category="Reading Patterns",
        title="You read in deep bursts",
        summary="Most of your highlights cluster in 2-3 evening sessions per week.",
        body="",
        evidence=[],
        recommendation="",
        related_books=[],
        priority_score=1.0,
    )
    defaults.update(kw)
    return InsightCard(**defaults)


# ---------------------------------------------------------------------------
# Storyboard card
# ---------------------------------------------------------------------------


def test_render_storyboard_card_minimal() -> None:
    card = _card()
    with patch("app.components.insights_dashboard.st.markdown") as md:
        dash.render_storyboard_card(card, color="#6366f1")
    html = "".join(c.args[0] for c in md.call_args_list)
    assert "kn-story-card" in html
    assert "Reading Patterns" in html
    assert "You read in deep bursts" in html


def test_render_storyboard_card_with_evidence_chips() -> None:
    card = _card(
        evidence=[
            EvidenceItem(label="Sessions", value="12"),
            EvidenceItem(label="Avg highlights", value="6"),
        ]
    )
    with patch("app.components.insights_dashboard.st.markdown") as md:
        dash.render_storyboard_card(card, color="#10b981")
    html = "".join(c.args[0] for c in md.call_args_list)
    assert "kn-story-chip" in html
    assert "Sessions" in html and "12" in html
    assert "Avg highlights" in html and "6" in html


def test_render_storyboard_card_uses_category_label_override() -> None:
    card = _card(category="Reading Patterns")
    with patch("app.components.insights_dashboard.st.markdown") as md:
        dash.render_storyboard_card(card, color="#6366f1", category_label="Habits")
    html = "".join(c.args[0] for c in md.call_args_list)
    assert "Habits" in html
    assert "Reading Patterns" not in html


def test_render_storyboard_card_open_button_only_when_detail_present() -> None:
    plain = _card()
    with_detail = _card(body="A longer body")
    with patch("app.components.insights_dashboard.st.markdown"), \
         patch("app.components.insights_dashboard.st.button") as button:
        dash.render_storyboard_card(plain, color="#6366f1", on_open=lambda c: None)
        dash.render_storyboard_card(with_detail, color="#6366f1", on_open=lambda c: None)
    # Only the card with detail should trigger the button
    assert button.call_count == 1


# ---------------------------------------------------------------------------
# Insight grid
# ---------------------------------------------------------------------------


def test_render_insight_grid_skips_empty() -> None:
    with patch("app.components.insights_dashboard.st.columns") as cols:
        dash.render_insight_grid([], color_for=lambda c: "#6366f1")
    cols.assert_not_called()


def test_render_insight_grid_pads_odd_rows_with_ghost() -> None:
    cards = [_card(id="a", title="A"), _card(id="b", title="B"), _card(id="c", title="C")]
    fake_col = MagicMock()
    fake_col.__enter__ = MagicMock(return_value=None)
    fake_col.__exit__ = MagicMock(return_value=None)
    with patch("app.components.insights_dashboard.st.columns", return_value=[fake_col, fake_col]) as cols, \
         patch("app.components.insights_dashboard.st.markdown") as md:
        dash.render_insight_grid(cards, columns=2, color_for=lambda c: "#6366f1")
    # Two rows: 1st has 2 cards, 2nd has 1 + 1 ghost
    assert cols.call_count == 2
    html = "".join(c.args[0] for c in md.call_args_list)
    assert "kn-story-card--ghost" in html


# ---------------------------------------------------------------------------
# Hero row
# ---------------------------------------------------------------------------


def test_render_hero_row_invokes_featured_renderer() -> None:
    called = []
    fake_col = MagicMock()
    fake_col.__enter__ = MagicMock(return_value=None)
    fake_col.__exit__ = MagicMock(return_value=None)
    with patch("app.components.insights_dashboard.st.columns", return_value=[fake_col, fake_col]), \
         patch("app.components.insights_dashboard.st.markdown"):
        dash.render_hero_row(featured_renderer=lambda: called.append("yes"))
    assert called == ["yes"]


# ---------------------------------------------------------------------------
# Quick stats panel
# ---------------------------------------------------------------------------


def test_render_quick_stats_panel_renders_tiles_and_identity() -> None:
    archetype = {
        "emoji": "🧠",
        "name": "Deep Thinker",
        "color": "#a855f7",
        "description": "You think on the page.",
    }
    with patch("app.components.insights_dashboard.st.markdown") as md:
        dash.render_quick_stats_panel(
            stats=[("Books", "12", "#3b82f6"), ("Highlights", "240", "#f59e0b")],
            archetype=archetype,
        )
    html = md.call_args.args[0]
    assert "kn-dash-stats" in html
    assert "Deep Thinker" in html and "🧠" in html
    assert "Books" in html and "12" in html
    assert "Highlights" in html and "240" in html


# ---------------------------------------------------------------------------
# Next action panel
# ---------------------------------------------------------------------------


def test_render_next_action_panel_invokes_callback_when_clicked() -> None:
    called = []
    with patch("app.components.insights_dashboard.st.markdown"), \
         patch("app.components.insights_dashboard.st.button", return_value=True):
        dash.render_next_action_panel(
            title="Rediscover this passage",
            body="A forgotten highlight from months ago.",
            cta_label="Show another",
            cta_callback=lambda: called.append("clicked"),
        )
    assert called == ["clicked"]


def test_render_next_action_panel_does_not_call_when_not_clicked() -> None:
    called = []
    with patch("app.components.insights_dashboard.st.markdown"), \
         patch("app.components.insights_dashboard.st.button", return_value=False):
        dash.render_next_action_panel(
            title="X",
            body="Y",
            cta_label="Go",
            cta_callback=lambda: called.append("clicked"),
        )
    assert called == []


# ---------------------------------------------------------------------------
# Analysis workspace
# ---------------------------------------------------------------------------


def test_render_analysis_workspace_invokes_each_tab_renderer() -> None:
    invoked: list[str] = []
    fake_tab = MagicMock()
    fake_tab.__enter__ = MagicMock(return_value=None)
    fake_tab.__exit__ = MagicMock(return_value=None)
    with patch("app.components.insights_dashboard.st.markdown"), \
         patch("app.components.insights_dashboard.st.tabs", return_value=[fake_tab, fake_tab]) as tabs:
        dash.render_analysis_workspace(
            intro="On-device AI.",
            tabs=[
                ("Themes", lambda: invoked.append("themes")),
                ("Search", lambda: invoked.append("search")),
            ],
        )
    tabs.assert_called_once_with(["Themes", "Search"])
    assert invoked == ["themes", "search"]


def test_render_analysis_workspace_runs_actions_renderer_first() -> None:
    order: list[str] = []
    fake_tab = MagicMock()
    fake_tab.__enter__ = MagicMock(return_value=None)
    fake_tab.__exit__ = MagicMock(return_value=None)
    with patch("app.components.insights_dashboard.st.markdown"), \
         patch("app.components.insights_dashboard.st.tabs", return_value=[fake_tab]):
        dash.render_analysis_workspace(
            intro="x",
            tabs=[("T", lambda: order.append("tab"))],
            actions_renderer=lambda: order.append("actions"),
        )
    assert order == ["actions", "tab"]


# ---------------------------------------------------------------------------
# Tools footer
# ---------------------------------------------------------------------------


def test_render_tools_footer_skips_when_no_panels() -> None:
    with patch("app.components.insights_dashboard.st.markdown") as md, \
         patch("app.components.insights_dashboard.st.columns") as cols:
        dash.render_tools_footer()
    md.assert_not_called()
    cols.assert_not_called()


def test_render_tools_footer_renders_export_and_extras() -> None:
    invoked: list[str] = []
    fake_col = MagicMock()
    fake_col.__enter__ = MagicMock(return_value=None)
    fake_col.__exit__ = MagicMock(return_value=None)
    with patch("app.components.insights_dashboard.st.markdown"), \
         patch("app.components.insights_dashboard.st.columns", return_value=[fake_col, fake_col]) as cols:
        dash.render_tools_footer(
            export_renderer=lambda: invoked.append("export"),
            extra_renderers=[("Community", lambda: invoked.append("community"))],
        )
    cols.assert_called_once()
    assert invoked == ["export", "community"]
