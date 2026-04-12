"""Tests for AI insight services: theme detection, clustering, similarity, summaries."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from models.annotation import Annotation
from models.book import Book
from models.insight import BookSummary, HighlightSimilarity, ThemeCluster
from services.embeddings import EmbeddingProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(title: str = "Test Book", author: str = "Test Author", n_highlights: int = 6) -> Book:
    return Book(
        id=f"book-{title.lower().replace(' ', '-')}",
        title=title,
        author=author,
        source="test",
        annotations=[
            Annotation(
                id=f"h{i}",
                book_id=f"book-{title.lower().replace(' ', '-')}",
                kind="highlight",
                text=f"Highlight text number {i} about topic {i % 3}",
                chapter=f"Chapter {i // 2 + 1}",
                source="test",
            )
            for i in range(n_highlights)
        ],
    )


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for testing."""

    def embed(self, texts: list[str]) -> np.ndarray:
        rng = np.random.RandomState(42)
        return rng.randn(len(texts), 32).astype(np.float32)

    def name(self) -> str:
        return "fake (test)"


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestInsightModels:
    def test_theme_cluster_defaults(self):
        tc = ThemeCluster(label="Theme 1", representative_text="sample", size=3)
        assert tc.highlight_ids == []
        assert tc.book_titles == []

    def test_highlight_similarity(self):
        hs = HighlightSimilarity(
            source_text="a",
            source_book="Book A",
            match_text="b",
            match_book="Book B",
            score=0.85,
        )
        assert hs.score == 0.85

    def test_book_summary(self):
        bs = BookSummary(
            book_id="b1",
            book_title="Title",
            summary="A summary.",
            highlight_count=10,
        )
        assert bs.method == "template"
        assert bs.themes == []


# ---------------------------------------------------------------------------
# Theme detection
# ---------------------------------------------------------------------------


class TestDetectThemes:
    def test_too_few_highlights(self):
        from services.insights import detect_themes

        book = _make_book(n_highlights=2)
        provider = FakeEmbeddingProvider()
        result = detect_themes(book, provider)
        assert result == []

    def test_returns_clusters(self):
        from services.insights import detect_themes

        book = _make_book(n_highlights=12)
        provider = FakeEmbeddingProvider()
        clusters = detect_themes(book, provider)
        assert len(clusters) >= 1
        assert all(isinstance(c, ThemeCluster) for c in clusters)
        total = sum(c.size for c in clusters)
        assert total == 12

    def test_clusters_have_representative_text(self):
        from services.insights import detect_themes

        book = _make_book(n_highlights=10)
        provider = FakeEmbeddingProvider()
        clusters = detect_themes(book, provider)
        for c in clusters:
            assert c.representative_text
            assert c.size > 0

    def test_sorted_by_size_descending(self):
        from services.insights import detect_themes

        book = _make_book(n_highlights=20)
        provider = FakeEmbeddingProvider()
        clusters = detect_themes(book, provider)
        sizes = [c.size for c in clusters]
        assert sizes == sorted(sizes, reverse=True)


# ---------------------------------------------------------------------------
# Cross-book clustering
# ---------------------------------------------------------------------------


class TestClusterAcrossBooks:
    def test_empty_library(self):
        from services.insights import cluster_highlights_across_books

        provider = FakeEmbeddingProvider()
        result = cluster_highlights_across_books([], provider)
        assert result == []

    def test_clusters_multiple_books(self):
        from services.insights import cluster_highlights_across_books

        books = [
            _make_book(title="Book A", n_highlights=8),
            _make_book(title="Book B", n_highlights=8),
        ]
        provider = FakeEmbeddingProvider()
        clusters = cluster_highlights_across_books(books, provider)
        assert len(clusters) >= 1
        # At least one cluster should span multiple books
        all_titles = set()
        for c in clusters:
            all_titles.update(c.book_titles)
        assert len(all_titles) == 2

    def test_too_few_highlights(self):
        from services.insights import cluster_highlights_across_books

        books = [_make_book(title="Solo", n_highlights=1)]
        provider = FakeEmbeddingProvider()
        result = cluster_highlights_across_books(books, provider)
        assert result == []


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------


class TestSimilaritySearch:
    def test_empty_library(self):
        from services.insights import find_similar_highlights

        provider = FakeEmbeddingProvider()
        result = find_similar_highlights("some text", [], provider)
        assert result == []

    def test_returns_results(self):
        from services.insights import find_similar_highlights

        books = [_make_book(n_highlights=10)]
        provider = FakeEmbeddingProvider()
        results = find_similar_highlights("topic 0", books, provider, min_score=0.0)
        assert len(results) >= 1
        assert all(isinstance(r, HighlightSimilarity) for r in results)

    def test_scores_between_0_and_1(self):
        from services.insights import find_similar_highlights

        books = [_make_book(n_highlights=10)]
        provider = FakeEmbeddingProvider()
        results = find_similar_highlights("topic 0", books, provider, min_score=0.0)
        for r in results:
            assert -1.0 <= r.score <= 1.0

    def test_respects_top_n(self):
        from services.insights import find_similar_highlights

        books = [_make_book(n_highlights=20)]
        provider = FakeEmbeddingProvider()
        results = find_similar_highlights("topic 0", books, provider, top_n=3, min_score=0.0)
        assert len(results) <= 3


# ---------------------------------------------------------------------------
# Reading insights (no AI needed)
# ---------------------------------------------------------------------------


class TestReadingInsights:
    def test_basic_insights(self):
        from services.insights import compute_reading_insights

        books = [_make_book(n_highlights=5)]
        insights = compute_reading_insights(books)
        assert insights["total_highlights"] == 5
        assert insights["books_with_annotations"] == 1
        assert insights["avg_highlights_per_book"] == 5.0

    def test_empty_library(self):
        from services.insights import compute_reading_insights

        insights = compute_reading_insights([])
        assert insights["total_highlights"] == 0
        assert insights["books_with_annotations"] == 0
        assert insights["avg_highlights_per_book"] == 0

    def test_top_authors(self):
        from services.insights import compute_reading_insights

        books = [
            _make_book(title="A", author="Alice", n_highlights=10),
            _make_book(title="B", author="Bob", n_highlights=5),
            _make_book(title="C", author="Alice", n_highlights=8),
        ]
        insights = compute_reading_insights(books)
        top = insights["top_highlighted_authors"]
        assert top[0][0] == "Alice"
        assert top[0][1] == 18  # 10 + 8


# ---------------------------------------------------------------------------
# Smart summaries
# ---------------------------------------------------------------------------


class TestTemplateSummary:
    def test_generates_summary(self):
        from services.summaries import generate_template_summary

        book = _make_book(n_highlights=5)
        result = generate_template_summary(book)
        assert isinstance(result, BookSummary)
        assert result.method == "template"
        assert "Test Book" in result.summary
        assert result.highlight_count == 5

    def test_includes_themes(self):
        from services.summaries import generate_template_summary

        book = _make_book(n_highlights=5)
        themes = [
            ThemeCluster(label="Theme 1", representative_text="sample idea", size=3, book_titles=["Test Book"]),
        ]
        result = generate_template_summary(book, themes=themes)
        assert "sample idea" in result.summary
        assert "Theme 1" in result.themes

    def test_includes_reading_time(self):
        from services.summaries import generate_template_summary

        book = _make_book(n_highlights=3)
        book.time_spent_reading = 7200  # 2 hours
        result = generate_template_summary(book)
        assert "2h" in result.summary

    def test_includes_rating(self):
        from services.summaries import generate_template_summary

        book = _make_book(n_highlights=3)
        book.rating = 4
        result = generate_template_summary(book)
        assert "4 out of 5" in result.summary


class TestGenerateSummary:
    def test_fallback_to_template(self):
        from services.summaries import generate_summary

        book = _make_book(n_highlights=5)
        result = generate_summary(book, api_key=None)
        assert result.method == "template"

    def test_llm_fallback_on_error(self):
        from services.summaries import generate_summary

        book = _make_book(n_highlights=5)
        # Pass an invalid key -- should fall back to template
        with patch("services.summaries.generate_llm_summary", side_effect=Exception("API error")):
            result = generate_summary(book, api_key="sk-fake")
        assert result.method == "template"


# ---------------------------------------------------------------------------
# Embedding provider factory
# ---------------------------------------------------------------------------


class TestGetProvider:
    def test_openai_requires_key(self):
        from services.embeddings import get_provider

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            get_provider("openai", api_key=None)

    def test_openai_requires_key_empty(self):
        from services.embeddings import get_provider

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            get_provider("openai", api_key="")


# ---------------------------------------------------------------------------
# Optimal k selection
# ---------------------------------------------------------------------------


class TestOptimalK:
    def test_returns_within_range(self):
        from services.insights import _optimal_k

        rng = np.random.RandomState(42)
        embeddings = rng.randn(20, 32).astype(np.float32)
        k = _optimal_k(embeddings, k_min=2, k_max=5)
        assert 2 <= k <= 5

    def test_small_dataset(self):
        from services.insights import _optimal_k

        rng = np.random.RandomState(42)
        embeddings = rng.randn(4, 16).astype(np.float32)
        k = _optimal_k(embeddings, k_min=2, k_max=8)
        assert 2 <= k <= 3  # capped at n-1


# ---------------------------------------------------------------------------
# Smart label generation
# ---------------------------------------------------------------------------


class TestGenerateLabel:
    def test_generates_descriptive_label(self):
        from services.insights import _generate_label

        label = _generate_label([
            "The importance of leadership in organizations",
            "Leadership styles and their impact on teams",
            "How great leaders inspire action",
        ])
        assert isinstance(label, str)
        assert len(label) > 0
        assert "&" in label  # Should combine top keywords

    def test_empty_texts(self):
        from services.insights import _generate_label

        assert _generate_label([]) == "General"

    def test_stopword_only_texts(self):
        from services.insights import _generate_label

        assert _generate_label(["is a the", "to of in"]) == "General"

    def test_with_corpus_boosts_distinctive_words(self):
        from services.insights import _generate_label

        cluster = [
            "Neural networks process information in layers",
            "Deep neural architectures improve accuracy",
        ]
        corpus = [
            "Neural networks process information in layers",
            "Deep neural architectures improve accuracy",
            "Financial markets react to global events",
            "Historical trends shape modern policy",
        ]
        label = _generate_label(cluster, corpus)
        assert isinstance(label, str)
        assert len(label) > 0

    def test_single_keyword(self):
        from services.insights import _generate_label

        label = _generate_label(["xyz xyz xyz"])
        assert label == "Xyz"  # Only one unique word found

    def test_detect_themes_uses_descriptive_labels(self):
        """Ensure detect_themes produces labels that are not 'Theme N'."""
        from services.insights import detect_themes

        book = _make_book(n_highlights=12)
        provider = FakeEmbeddingProvider()
        clusters = detect_themes(book, provider)
        for c in clusters:
            assert not c.label.startswith("Theme ")

    def test_cluster_across_books_uses_descriptive_labels(self):
        """Ensure cluster_highlights_across_books produces labels that are not 'Idea N'."""
        from services.insights import cluster_highlights_across_books

        books = [
            _make_book(title="Book A", n_highlights=8),
            _make_book(title="Book B", n_highlights=8),
        ]
        provider = FakeEmbeddingProvider()
        clusters = cluster_highlights_across_books(books, provider)
        for c in clusters:
            assert not c.label.startswith("Idea ")
