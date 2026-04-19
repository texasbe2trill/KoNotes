"""Tests for insight sharing: formatting, URL building, and share-worthiness."""
from __future__ import annotations

from urllib.parse import unquote

import pytest

from models.insight import EvidenceItem, InsightCard
from services.share_formatter import (
    APP_PUBLIC_URL,
    format_insight_for_bluesky,
    format_insight_for_copy,
    format_insight_for_markdown,
    is_shareworthy,
)
from services.share_links import build_bluesky_share_url


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _card(
    *,
    priority: float = 0.7,
    recommendation: str | None = "Keep reading deeply.",
    body: str = "You consistently engage with books about systems and structure, building a pattern of deep intellectual curiosity across multiple titles.",
    related_books: list[str] | None = None,
    summary: str = "Your annotations reveal a focus on systems thinking.",
    title: str = "Deep Engagement",
) -> InsightCard:
    return InsightCard(
        id="test123",
        title=title,
        category="Deep Reading Signals",
        summary=summary,
        body=body,
        recommendation=recommendation,
        priority_score=priority,
        related_books=related_books if related_books is not None else ["Thinking in Systems", "The Design of Everyday Things"],
        evidence=[EvidenceItem(label="Highlights", value="42")],
    )


# ---------------------------------------------------------------------------
# is_shareworthy
# ---------------------------------------------------------------------------


class TestIsShareworthy:
    def test_high_priority_with_all_criteria(self):
        card = _card(priority=0.8)
        assert is_shareworthy(card) is True

    def test_low_priority_no_details(self):
        card = _card(priority=0.1, recommendation=None, body="", related_books=[])
        assert is_shareworthy(card) is False

    def test_missing_recommendation_not_shareworthy(self):
        card = _card(priority=0.8, recommendation=None)
        assert is_shareworthy(card) is False

    def test_short_body_not_shareworthy(self):
        card = _card(priority=0.8, body="Too short.")
        assert is_shareworthy(card) is False

    def test_no_related_books_not_shareworthy(self):
        card = _card(priority=0.8, related_books=[])
        assert is_shareworthy(card) is False

    def test_minimal_card_not_shareworthy(self):
        card = InsightCard(
            id="bare",
            title="Tiny",
            category="Library Overview",
            summary="One stat.",
            priority_score=0.1,
        )
        assert is_shareworthy(card) is False


# ---------------------------------------------------------------------------
# Bluesky formatter
# ---------------------------------------------------------------------------


class TestBlueskyFormat:
    def test_contains_book_reference(self):
        text = format_insight_for_bluesky(_card())
        assert "Thinking in Systems" in text

    def test_contains_hashtag(self):
        text = format_insight_for_bluesky(_card())
        assert "#booksky" in text

    def test_contains_app_url(self):
        text = format_insight_for_bluesky(_card())
        assert APP_PUBLIC_URL in text

    def test_within_length_limit(self):
        text = format_insight_for_bluesky(_card())
        assert len(text) <= 300

    def test_no_recommendation_in_post(self):
        text = format_insight_for_bluesky(_card(recommendation="Read more Meadows."))
        # Bluesky posts are summary-only, no recommendation
        assert "Read more Meadows" not in text

    def test_no_related_books_in_post(self):
        text = format_insight_for_bluesky(_card(related_books=[]))
        # Bluesky posts don't include book list
        assert "#booksky" in text

    def test_custom_url(self):
        text = format_insight_for_bluesky(_card(), app_url="https://example.com/")
        assert "https://example.com/" in text
        assert APP_PUBLIC_URL not in text


# ---------------------------------------------------------------------------
# Copy/share formatter
# ---------------------------------------------------------------------------


class TestCopyFormat:
    def test_contains_title_and_summary(self):
        text = format_insight_for_copy(_card())
        assert "Deep Engagement" in text
        assert "systems thinking" in text

    def test_contains_attribution(self):
        text = format_insight_for_copy(_card())
        assert "Shared via KoNotes" in text

    def test_contains_app_url(self):
        text = format_insight_for_copy(_card())
        assert APP_PUBLIC_URL in text

    def test_contains_recommendation(self):
        text = format_insight_for_copy(_card(recommendation="Try Senge next."))
        assert "Try Senge next" in text

    def test_no_hashtag(self):
        text = format_insight_for_copy(_card())
        assert "#booksky" not in text


# ---------------------------------------------------------------------------
# Markdown formatter
# ---------------------------------------------------------------------------


class TestMarkdownFormat:
    def test_has_heading(self):
        text = format_insight_for_markdown(_card())
        assert "### Deep Engagement" in text

    def test_has_blockquote(self):
        text = format_insight_for_markdown(_card())
        assert "> " in text

    def test_has_attribution_link(self):
        text = format_insight_for_markdown(_card())
        assert "[KoNotes]" in text
        assert APP_PUBLIC_URL in text

    def test_books_italicized(self):
        text = format_insight_for_markdown(_card())
        assert "*Thinking in Systems*" in text


# ---------------------------------------------------------------------------
# Bluesky share URL
# ---------------------------------------------------------------------------


class TestBlueskyShareUrl:
    def test_url_prefix(self):
        url = build_bluesky_share_url("hello world")
        assert url.startswith("https://bsky.app/intent/compose?text=")

    def test_text_is_encoded(self):
        url = build_bluesky_share_url("hello world #test")
        assert "hello%20world" in url
        assert "%23test" in url

    def test_roundtrip_decode(self):
        original = "Some insight\n\nhttps://example.com\n\n#booksky"
        url = build_bluesky_share_url(original)
        decoded = unquote(url.split("text=", 1)[1])
        assert decoded == original

    def test_special_characters(self):
        url = build_bluesky_share_url("quotes: \u201chello\u201d & ampersand")
        assert "bsky.app" in url


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_no_recommendation(self):
        text = format_insight_for_bluesky(_card(recommendation=None))
        assert "#booksky" in text

    def test_no_related_books(self):
        text = format_insight_for_bluesky(_card(related_books=[]))
        assert "#booksky" in text
        assert "#booksky" in text

    def test_empty_body(self):
        text = format_insight_for_copy(_card(body=""))
        assert "Deep Engagement" in text

    def test_long_summary_truncated_for_bluesky(self):
        long_summary = "A" * 300
        text = format_insight_for_bluesky(_card(summary=long_summary))
        assert len(text) <= 300
