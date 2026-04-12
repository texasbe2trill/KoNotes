"""Tests for insight feed, formatter, ranking, deduplication, and export."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from models.annotation import Annotation
from models.book import Book
from models.insight import EvidenceItem, InsightCard, INSIGHT_CATEGORIES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(
    title: str = "Test Book",
    author: str = "Test Author",
    n_highlights: int = 6,
    n_notes: int = 0,
    read_percent: float | None = None,
    time_spent: int | None = None,
    rating: int | None = None,
    date_last_read: datetime | None = None,
    word_count: int | None = None,
) -> Book:
    annotations = []
    for i in range(n_highlights):
        annotations.append(Annotation(
            id=f"h{i}-{title}",
            book_id=f"book-{title.lower().replace(' ', '-')}",
            kind="highlight",
            text=f"Highlight text number {i} about topic {i % 3}",
            chapter=f"Chapter {i // 2 + 1}",
            source="test",
        ))
    for i in range(n_notes):
        annotations.append(Annotation(
            id=f"n{i}-{title}",
            book_id=f"book-{title.lower().replace(' ', '-')}",
            kind="note",
            text=f"Note text number {i}",
            chapter=f"Chapter {i // 2 + 1}",
            source="test",
        ))
    return Book(
        id=f"book-{title.lower().replace(' ', '-')}",
        title=title,
        author=author,
        source="test",
        annotations=annotations,
        read_percent=read_percent,
        time_spent_reading=time_spent,
        rating=rating,
        date_last_read=date_last_read,
        word_count=word_count,
    )


# ---------------------------------------------------------------------------
# InsightCard model tests
# ---------------------------------------------------------------------------


class TestInsightCardModel:
    def test_defaults(self):
        card = InsightCard(
            id="test-1",
            title="Test",
            category="Reading Patterns",
            summary="A summary.",
        )
        assert card.body == ""
        assert card.evidence == []
        assert card.recommendation is None
        assert card.confidence is None
        assert card.priority_score == 0.0
        assert card.related_books == []
        assert card.source == "computed"
        assert card.created_at is None

    def test_full_card(self):
        card = InsightCard(
            id="test-2",
            title="Full Card",
            category="Most Engaged Books",
            summary="Full summary.",
            body="Detailed body text.",
            evidence=[EvidenceItem(label="Books", value="3")],
            recommendation="Do something.",
            confidence=0.85,
            priority_score=0.7,
            related_books=["Book A", "Book B"],
            source="computed",
            created_at=datetime(2026, 4, 12),
        )
        assert card.confidence == 0.85
        assert len(card.evidence) == 1
        assert card.evidence[0].label == "Books"

    def test_categories_list(self):
        assert len(INSIGHT_CATEGORIES) >= 9
        assert "Reading Patterns" in INSIGHT_CATEGORIES
        assert "Deep Reading Signals" in INSIGHT_CATEGORIES


# ---------------------------------------------------------------------------
# Insight Feed -- build_feed
# ---------------------------------------------------------------------------


class TestBuildFeed:
    def test_empty_library(self):
        from services.insight_feed import build_feed
        cards = build_feed([])
        assert cards == []

    def test_single_book(self):
        from services.insight_feed import build_feed
        books = [_make_book(n_highlights=5)]
        cards = build_feed(books)
        assert len(cards) >= 1
        assert all(isinstance(c, InsightCard) for c in cards)

    def test_multiple_books(self):
        from services.insight_feed import build_feed
        books = [
            _make_book(title="Book A", n_highlights=10, n_notes=3),
            _make_book(title="Book B", n_highlights=5, n_notes=1),
            _make_book(title="Book C", n_highlights=8),
        ]
        cards = build_feed(books)
        assert len(cards) >= 3
        categories = {c.category for c in cards}
        assert "Library Overview" in categories
        assert "Most Engaged Books" in categories

    def test_ranked_by_priority(self):
        from services.insight_feed import build_feed
        books = [
            _make_book(title="A", n_highlights=15, n_notes=5),
            _make_book(title="B", n_highlights=3),
        ]
        cards = build_feed(books)
        scores = [c.priority_score for c in cards]
        assert scores == sorted(scores, reverse=True)

    def test_category_filter(self):
        from services.insight_feed import build_feed
        books = [_make_book(n_highlights=10, n_notes=3)]
        cards = build_feed(books, categories=["Library Overview"])
        assert all(c.category == "Library Overview" for c in cards)

    def test_book_filter(self):
        from services.insight_feed import build_feed
        books = [
            _make_book(title="Alpha", n_highlights=10),
            _make_book(title="Beta", n_highlights=10),
        ]
        cards = build_feed(books, book_filter="Alpha")
        assert all("Alpha" in c.related_books for c in cards)

    def test_min_priority_filter(self):
        from services.insight_feed import build_feed
        books = [_make_book(n_highlights=10, n_notes=5)]
        cards = build_feed(books, min_priority=0.9)
        assert all(c.priority_score >= 0.9 for c in cards)

    def test_cards_have_evidence(self):
        from services.insight_feed import build_feed
        books = [_make_book(n_highlights=10, n_notes=3)]
        cards = build_feed(books)
        cards_with_evidence = [c for c in cards if c.evidence]
        assert len(cards_with_evidence) >= 1

    def test_cards_have_related_books(self):
        from services.insight_feed import build_feed
        books = [_make_book(title="MyBook", n_highlights=10)]
        cards = build_feed(books)
        cards_with_books = [c for c in cards if c.related_books]
        assert len(cards_with_books) >= 1


# ---------------------------------------------------------------------------
# Specific generator tests
# ---------------------------------------------------------------------------


class TestMostEngaged:
    def test_top_book_identified(self):
        from services.insight_feed import _most_engaged_books
        books = [
            _make_book(title="Big Book", n_highlights=20, n_notes=5, time_spent=7200),
            _make_book(title="Small Book", n_highlights=2),
        ]
        cards = _most_engaged_books(books)
        assert len(cards) >= 1
        assert "Big Book" in cards[0].title

    def test_empty_library(self):
        from services.insight_feed import _most_engaged_books
        assert _most_engaged_books([]) == []


class TestReadingPatterns:
    def test_completion_rate(self):
        from services.insight_feed import _reading_patterns
        books = [
            _make_book(title="Done", read_percent=100),
            _make_book(title="Half", read_percent=50),
            _make_book(title="New", read_percent=5),
        ]
        cards = _reading_patterns(books)
        assert any("Completion" in c.title for c in cards)

    def test_reading_time(self):
        from services.insight_feed import _reading_patterns
        books = [
            _make_book(title="Long", time_spent=7200, n_highlights=5),
            _make_book(title="Short", time_spent=1800, n_highlights=3),
        ]
        cards = _reading_patterns(books)
        assert any("Time" in c.title for c in cards)


class TestBooksInProgress:
    def test_detects_in_progress(self):
        from services.insight_feed import _books_in_progress
        books = [
            _make_book(title="WIP", read_percent=60),
            _make_book(title="Done", read_percent=100),
        ]
        cards = _books_in_progress(books)
        assert len(cards) == 1
        assert "1 Book" in cards[0].title

    def test_no_in_progress(self):
        from services.insight_feed import _books_in_progress
        books = [_make_book(title="Done", read_percent=100)]
        assert _books_in_progress(books) == []

    def test_almost_done_recommendation(self):
        from services.insight_feed import _books_in_progress
        books = [_make_book(title="Almost", read_percent=85)]
        cards = _books_in_progress(books)
        assert cards[0].recommendation is not None
        assert "Almost" in cards[0].recommendation


class TestHighlightBehavior:
    def test_distribution(self):
        from services.insight_feed import _highlight_behavior
        books = [
            _make_book(title="Heavy", n_highlights=20),
            _make_book(title="Light", n_highlights=3),
        ]
        cards = _highlight_behavior(books)
        assert any("Distribution" in c.title for c in cards)

    def test_too_few(self):
        from services.insight_feed import _highlight_behavior
        books = [_make_book(title="Tiny", n_highlights=1)]
        assert _highlight_behavior(books) == []


class TestReadingMomentum:
    def test_recent_books(self):
        from services.insight_feed import _reading_momentum
        books = [_make_book(title="Recent", date_last_read=datetime.now() - timedelta(days=5), n_highlights=5)]
        cards = _reading_momentum(books)
        assert any("Active" in c.title for c in cards)

    def test_stale_books(self):
        from services.insight_feed import _reading_momentum
        books = [_make_book(title="Old", date_last_read=datetime.now() - timedelta(days=120), n_highlights=10)]
        cards = _reading_momentum(books)
        assert any("Forgotten" in c.title for c in cards)


class TestDeepReadingSignals:
    def test_deep_read_detected(self):
        from services.insight_feed import _deep_reading_signals
        books = [_make_book(title="Deep", n_highlights=10, n_notes=8)]
        cards = _deep_reading_signals(books)
        assert len(cards) == 1
        assert "Deep" in cards[0].title

    def test_not_enough_highlights(self):
        from services.insight_feed import _deep_reading_signals
        books = [_make_book(title="Shallow", n_highlights=2)]
        assert _deep_reading_signals(books) == []


class TestAuthorInsights:
    def test_multi_book_author(self):
        from services.insight_feed import _author_insights
        books = [
            _make_book(title="Book1", author="Alice", n_highlights=10),
            _make_book(title="Book2", author="Alice", n_highlights=5),
            _make_book(title="Book3", author="Bob", n_highlights=3),
        ]
        cards = _author_insights(books)
        assert len(cards) == 1
        assert "Alice" in cards[0].title

    def test_no_multi_book_author(self):
        from services.insight_feed import _author_insights
        books = [_make_book(title="Solo", author="Unique", n_highlights=5)]
        assert _author_insights(books) == []


class TestRatingInsights:
    def test_rated_books(self):
        from services.insight_feed import _rating_insights
        books = [
            _make_book(title="Good", rating=4, n_highlights=5),
            _make_book(title="Great", rating=5, n_highlights=5),
        ]
        cards = _rating_insights(books)
        assert len(cards) == 1
        assert "4.5" in cards[0].summary

    def test_too_few_ratings(self):
        from services.insight_feed import _rating_insights
        books = [_make_book(title="Lone", rating=3, n_highlights=5)]
        assert _rating_insights(books) == []


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def test_removes_id_duplicates(self):
        from services.insight_feed import deduplicate
        cards = [
            InsightCard(id="x", title="A", category="C", summary="First"),
            InsightCard(id="x", title="B", category="C", summary="Second"),
        ]
        result = deduplicate(cards)
        assert len(result) == 1
        assert result[0].title == "A"

    def test_removes_summary_duplicates(self):
        from services.insight_feed import deduplicate
        cards = [
            InsightCard(id="a", title="A", category="C", summary="Your library contains 5 books with 20 highlights"),
            InsightCard(id="b", title="B", category="C", summary="Your library contains 5 books with 20 highlights and notes"),
        ]
        result = deduplicate(cards)
        assert len(result) == 1

    def test_keeps_distinct(self):
        from services.insight_feed import deduplicate
        cards = [
            InsightCard(id="a", title="A", category="C", summary="Completely different topic one"),
            InsightCard(id="b", title="B", category="C", summary="Another unrelated insight here"),
        ]
        result = deduplicate(cards)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestRanking:
    def test_sort_by_priority(self):
        from services.insight_feed import rank_cards
        cards = [
            InsightCard(id="low", title="Low", category="C", summary="s", priority_score=0.1),
            InsightCard(id="high", title="High", category="C", summary="s", priority_score=0.9),
            InsightCard(id="mid", title="Mid", category="C", summary="s", priority_score=0.5),
        ]
        ranked = rank_cards(cards)
        assert ranked[0].id == "high"
        assert ranked[-1].id == "low"

    def test_recommendation_boost(self):
        from services.insight_feed import rank_cards
        card_a = InsightCard(id="a", title="A", category="C", summary="s", priority_score=0.5)
        card_b = InsightCard(id="b", title="B", category="C", summary="s", priority_score=0.5, recommendation="Do this")
        ranked = rank_cards([card_a, card_b])
        assert ranked[0].id == "b"  # recommendation gets boost


# ---------------------------------------------------------------------------
# Takeaways
# ---------------------------------------------------------------------------


class TestTakeaways:
    def test_extracts_takeaways(self):
        from services.insight_feed import extract_takeaways
        cards = [
            InsightCard(id="1", title="A", category="Cat1", summary="First takeaway"),
            InsightCard(id="2", title="B", category="Cat2", summary="Second takeaway"),
            InsightCard(id="3", title="C", category="Cat1", summary="Third takeaway (dup cat)"),
        ]
        takeaways = extract_takeaways(cards, n=5)
        assert len(takeaways) == 2  # one per category
        assert "First takeaway" in takeaways

    def test_empty_cards(self):
        from services.insight_feed import extract_takeaways
        assert extract_takeaways([], n=5) == []


# ---------------------------------------------------------------------------
# Insight Formatter
# ---------------------------------------------------------------------------


class TestInsightFormatter:
    def test_split_llm_paragraphs(self):
        from services.insight_formatter import split_llm_output
        text = "First paragraph about themes.\n\nSecond paragraph about patterns."
        cards = split_llm_output(text, book_title="Test Book")
        assert len(cards) >= 1
        assert all(isinstance(c, InsightCard) for c in cards)

    def test_split_llm_headings(self):
        from services.insight_formatter import split_llm_output
        text = "## Theme One\nDetail about theme one.\n\n## Theme Two\nDetail about theme two."
        cards = split_llm_output(text)
        assert len(cards) == 2
        assert cards[0].title == "Theme One"

    def test_split_llm_numbered(self):
        from services.insight_formatter import split_llm_output
        text = "1. First insight about power.\n2. Second insight about freedom.\n3. Third insight."
        cards = split_llm_output(text)
        assert len(cards) == 3

    def test_empty_input(self):
        from services.insight_formatter import split_llm_output
        assert split_llm_output("") == []
        assert split_llm_output("   ") == []

    def test_format_long_text(self):
        from services.insight_formatter import format_long_text
        short = "Short text."
        preview, full = format_long_text(short)
        assert preview == full == short

    def test_format_long_text_truncation(self):
        from services.insight_formatter import format_long_text
        long_text = "This is the first sentence. " * 20
        preview, full = format_long_text(long_text, max_preview=100)
        assert len(preview) <= 110  # some flexibility for sentence boundary
        assert len(full) > len(preview)

    def test_normalize_ai_insights(self):
        from services.insight_formatter import normalize_ai_insights
        text = "## Key Theme\nYou focused on ideas of power and control."
        cards = normalize_ai_insights(text, book_title="1984")
        assert len(cards) >= 1
        assert cards[0].related_books == ["1984"]

    def test_extract_title_markdown(self):
        from services.insight_formatter import _extract_title
        assert _extract_title("## My Title\nBody text.") == "My Title"

    def test_extract_title_numbered(self):
        from services.insight_formatter import _extract_title
        assert _extract_title("1. First item\nDetail.") == "First item"

    def test_extract_title_bold(self):
        from services.insight_formatter import _extract_title
        assert _extract_title("**Bold Title** and more text") == "Bold Title"

    def test_extract_summary(self):
        from services.insight_formatter import _extract_summary
        text = "First sentence here. Second sentence here. Third sentence."
        summary = _extract_summary(text)
        assert "First sentence" in summary
        assert len(summary.split('. ')) <= 3


# ---------------------------------------------------------------------------
# Insight Export
# ---------------------------------------------------------------------------


class TestInsightExport:
    def _sample_cards(self) -> list[InsightCard]:
        return [
            InsightCard(
                id="e1",
                title="Top Insight",
                category="Reading Patterns",
                summary="You read a lot.",
                body="Detailed body here.",
                evidence=[
                    EvidenceItem(label="Books", value="5"),
                    EvidenceItem(label="Highlights", value="42"),
                ],
                recommendation="Keep reading.",
                related_books=["Book A", "Book B"],
            ),
            InsightCard(
                id="e2",
                title="Vocabulary Growth",
                category="Vocabulary Activity",
                summary="You looked up 30 words.",
                body="Your vocabulary is expanding.",
            ),
        ]

    def test_export_markdown(self):
        from services.insight_export import export_insights_markdown
        md = export_insights_markdown(self._sample_cards())
        assert "# KoNotes Reading Intelligence" in md
        assert "## Reading Patterns" in md
        assert "### Top Insight" in md
        assert "**Summary:** You read a lot." in md
        assert "- Books: 5" in md
        assert "**Recommendation:** Keep reading." in md
        assert "Book A, Book B" in md
        assert "Made with love for the Kobo community." in md
        assert "## Vocabulary Activity" in md

    def test_export_text(self):
        from services.insight_export import export_insights_text
        txt = export_insights_text(self._sample_cards())
        assert "KONOTES READING INTELLIGENCE" in txt
        assert "[1] Top Insight" in txt
        assert "Category: Reading Patterns" in txt
        assert "Evidence:" in txt
        assert "- Books: 5" in txt
        assert "Action: Keep reading." in txt
        assert "Made with love for the Kobo community." in txt

    def test_export_single_card(self):
        from services.insight_export import export_single_card_markdown
        card = self._sample_cards()[0]
        md = export_single_card_markdown(card)
        assert "## Top Insight" in md
        assert "Reading Patterns" in md
        assert "**Evidence:**" in md
        assert "**Next step:** Keep reading." in md

    def test_export_empty(self):
        from services.insight_export import export_insights_markdown
        md = export_insights_markdown([])
        assert "KoNotes Reading Intelligence" in md
        assert "Made with love" in md

    def test_export_markdown_has_github_link(self):
        from services.insight_export import export_insights_markdown
        md = export_insights_markdown(self._sample_cards())
        assert "https://github.com/texasbe2trill/KoNotes" in md

    def test_export_text_has_github_link(self):
        from services.insight_export import export_insights_text
        txt = export_insights_text(self._sample_cards())
        assert "https://github.com/texasbe2trill/KoNotes" in txt
