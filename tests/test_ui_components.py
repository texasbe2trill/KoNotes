"""Tests for the reusable UI design-system helpers."""
from __future__ import annotations

from unittest.mock import patch

from app.components import ui


def _captured_markdown() -> str:
    """Return the concatenated HTML passed to ``st.markdown`` during a test."""
    calls = _mock.call_args_list
    return "\n".join(
        (args[0] if args else kwargs.get("body", ""))
        for args, kwargs in (c for c in calls)
    )


# We patch st.markdown in each test via a context manager — simpler than globals.


def test_render_page_header_minimal():
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_page_header("Library")
    html = mk.call_args[0][0]
    assert "kn-page-header" in html
    assert "<h2" in html and "Library" in html


def test_render_page_header_with_eyebrow_subtitle_and_meta():
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_page_header(
            "Library",
            subtitle="Browse your books",
            eyebrow="Your Books",
            meta=["42 books", "320 highlights"],
        )
    html = mk.call_args[0][0]
    assert "Your Books" in html
    assert "Browse your books" in html
    assert "42 books" in html and "320 highlights" in html
    assert html.count("kn-page-header__chip") == 2


def test_render_page_header_escapes_html():
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_page_header("<script>x</script>")
    html = mk.call_args[0][0]
    assert "<script>" not in html  # must be escaped
    assert "&lt;script&gt;" in html


def test_render_page_header_filters_falsy_meta():
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_page_header("X", meta=["ok", "", None, "also"])
    html = mk.call_args[0][0]
    assert html.count("kn-page-header__chip") == 2


def test_render_section_header():
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_section_header("Top Books", subtitle="Most highlighted")
    html = mk.call_args[0][0]
    assert "kn-section__title" in html and "Top Books" in html
    assert "kn-section__subtitle" in html and "Most highlighted" in html


def test_chip_html_known_tone():
    html = ui.chip_html("Reading", tone="blue")
    assert 'class="kn-chip kn-chip--blue"' in html
    assert "Reading" in html


def test_chip_html_unknown_tone_falls_back_to_neutral():
    html = ui.chip_html("X", tone="neon-pink")
    assert "kn-chip--neutral" in html


def test_render_metric_pill_renders_value_label_and_sub():
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_metric_pill("Highlights", "1,204", tone="amber", sub="+12 this week")
    html = mk.call_args[0][0]
    assert "kn-metric-pill--amber" in html
    assert "1,204" in html and "Highlights" in html
    assert "+12 this week" in html


def test_render_empty_state_minimal():
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_empty_state("No data")
    html = mk.call_args[0][0]
    assert "kn-empty" in html and "No data" in html


def test_render_empty_state_with_body_and_hint():
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_empty_state(
            "Nothing yet",
            body="Upload a file to begin.",
            icon="📚",
            hint="You can use the sample dataset too.",
        )
    html = mk.call_args[0][0]
    assert "Upload a file to begin." in html
    assert "kn-empty__hint" in html
    assert "You can use the sample dataset too." in html


def test_render_soft_divider():
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_soft_divider()
    html = mk.call_args[0][0]
    assert "kn-soft-divider" in html


def test_helpers_do_not_crash_with_empty_strings():
    # Components must gracefully accept empty but valid inputs.
    with patch("app.components.ui.st.markdown") as mk:
        ui.render_page_header("")
        ui.render_section_header("")
        ui.render_empty_state("")
        ui.render_chip("", tone="blue")
        ui.render_metric_pill("", "", tone="green")
    assert mk.call_count == 5
