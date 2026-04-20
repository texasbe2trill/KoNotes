"""Tests for the hero insight Bluesky formatter and component contract."""
from __future__ import annotations

from services.hero_insight_engine import HeroInsight
from services.share_formatter import format_hero_for_bluesky


def _hero(pattern: str, **overrides) -> HeroInsight:
    base = dict(
        pattern=pattern,
        title="Title",
        summary="Generic summary that should only appear when no body template exists.",
        evidence=["a", "b"],
        recommendation="Do the thing.",
        priority=0.8,
        is_fallback=False,
    )
    base.update(overrides)
    return HeroInsight(**base)  # type: ignore[arg-type]


class TestFormatHeroForBluesky:
    def test_deep_reader_uses_introspective_body(self):
        text = format_hero_for_bluesky(_hero("deep_reader"))
        assert "I read to understand" in text
        # Must NOT carry promotional / "Discover..." marketing language.
        assert "Discover" not in text
        assert "discover" not in text
        # Must include the app URL and the booksky tag.
        assert "https://konotes.streamlit.app" in text
        assert "#booksky" in text

    def test_pattern_seeker_uses_thread_language(self):
        text = format_hero_for_bluesky(_hero("pattern_seeker"))
        assert "thread" in text.lower() or "idea" in text.lower()
        assert "#booksky" in text

    def test_focused_deep_dive_post(self):
        text = format_hero_for_bluesky(_hero("focused_deep_dive"))
        assert "one book" in text.lower()
        assert "#booksky" in text

    def test_friction_reader_post(self):
        text = format_hero_for_bluesky(_hero("friction_reader"))
        assert "look" in text.lower() or "vocabulary" in text.lower()
        assert "#booksky" in text

    def test_selective_thinker_post(self):
        text = format_hero_for_bluesky(_hero("selective_thinker"))
        assert "note" in text.lower()
        assert "#booksky" in text

    def test_unknown_pattern_falls_back_to_summary(self):
        text = format_hero_for_bluesky(
            _hero("brand_new_pattern", summary="This is a custom personal summary."),
        )
        assert "This is a custom personal summary." in text
        assert "#booksky" in text

    def test_post_stays_under_bluesky_limit(self):
        for pattern in (
            "deep_reader",
            "pattern_seeker",
            "selective_thinker",
            "friction_reader",
            "focused_deep_dive",
        ):
            text = format_hero_for_bluesky(_hero(pattern))
            assert len(text) <= 300, f"{pattern} post exceeded 300 chars: {len(text)}"

    def test_no_marketing_phrasing(self):
        # Sanity check across all built-in pattern bodies.
        banned = ("Discover", "discover your", "click", "sign up")
        for pattern in (
            "deep_reader",
            "pattern_seeker",
            "selective_thinker",
            "friction_reader",
            "focused_deep_dive",
        ):
            text = format_hero_for_bluesky(_hero(pattern))
            for phrase in banned:
                assert phrase not in text, f"'{phrase}' leaked into {pattern} post"


class TestHeroComponentContract:
    """The component is Streamlit-rendered HTML; we sanity-check key strings."""

    def test_render_does_not_crash_for_real_pattern(self):
        # Render is safe to call with a real Streamlit context absent — guarded
        # by importing only the markup-building helper.
        from app.components.hero_insight import _build_copy_text

        text = _build_copy_text(_hero("deep_reader"))
        assert "Title" in text
        assert "Do the thing." in text

    def test_render_does_not_crash_for_fallback(self):
        from app.components.hero_insight import _build_copy_text

        text = _build_copy_text(_hero("getting_started", is_fallback=True))
        assert "Title" in text
