"""AI insight services: theme detection, highlight clustering, similarity search."""
from __future__ import annotations

import logging
import re
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity

from models.book import Book
from models.insight import HighlightSimilarity, ThemeCluster
from services.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

# Minimal stopword set for keyword extraction -- avoids adding dependencies.
_STOPWORDS = frozenset(
    "a an the and or but is was were are been be being to of in for on with at by "
    "from as into about that this it its not no nor so if then than too very can "
    "will just more most also which who whom what when where why how all each every "
    "any both few many some such there their they them these those he she her his "
    "him me my we us our you your do does did doing done has have had having get "
    "got make made over own same would could should may might shall must need "
    "want like going one even still back way much thing things well come came "
    "see seen know knew take took tell told said say says think thought find found "
    "give gave look looked seem seemed really only because through before after "
    "people something other another new between first last long great little right "
    "big high old different next important enough never always often sometimes "
    "what where when while who whom whose why until upon yet already "
    "out up down off away here now then there".split()
)


def _generate_label(
    cluster_texts: list[str],
    corpus_texts: list[str] | None = None,
) -> str:
    """Generate a short descriptive label from highlight texts via keyword extraction."""
    cluster_words: Counter[str] = Counter()
    for text in cluster_texts:
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        cluster_words.update(w for w in words if w not in _STOPWORDS)

    if not cluster_words:
        return "General"

    if corpus_texts:
        corpus_words: Counter[str] = Counter()
        for text in corpus_texts:
            words = re.findall(r"[a-zA-Z]{3,}", text.lower())
            corpus_words.update(w for w in words if w not in _STOPWORDS)

        # TF-IDF-like score: cluster frequency / sqrt(corpus frequency)
        scored: dict[str, float] = {}
        for word, count in cluster_words.items():
            corpus_freq = corpus_words.get(word, 1)
            scored[word] = count / (corpus_freq ** 0.5)

        top_words = sorted(scored, key=lambda w: scored[w], reverse=True)[:3]
    else:
        top_words = [w for w, _ in cluster_words.most_common(3)]

    formatted = [w.capitalize() for w in top_words]
    if len(formatted) >= 2:
        return f"{formatted[0]} & {formatted[1]}"
    return formatted[0] if formatted else "General"


def _optimal_k(embeddings: np.ndarray, k_min: int = 2, k_max: int = 10) -> int:
    """Choose the best number of clusters via silhouette score."""
    n = embeddings.shape[0]
    k_max = min(k_max, n - 1)
    if k_max < k_min:
        return k_min

    best_k, best_score = k_min, -1.0
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(embeddings)
        score = float(silhouette_score(embeddings, labels))
        if score > best_score:
            best_k, best_score = k, score
    return best_k


def detect_themes(
    book: Book,
    provider: EmbeddingProvider,
    *,
    max_clusters: int = 8,
) -> list[ThemeCluster]:
    """Cluster a single book's highlights into semantic themes."""
    highlights = [a for a in book.annotations if a.kind == "highlight" and a.text.strip()]
    if len(highlights) < 3:
        return []

    texts = [h.text for h in highlights]
    embeddings = provider.embed(texts)

    k = _optimal_k(embeddings, k_max=min(max_clusters, len(highlights) // 2 or 2))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(embeddings)

    clusters: list[ThemeCluster] = []
    for cluster_id in range(k):
        indices = [i for i, lbl in enumerate(labels) if lbl == cluster_id]
        if not indices:
            continue

        # Find the highlight closest to the centroid as representative
        centroid = km.cluster_centers_[cluster_id]
        cluster_embeds = embeddings[indices]
        sims = cosine_similarity(cluster_embeds, centroid.reshape(1, -1)).flatten()
        rep_idx = indices[int(np.argmax(sims))]

        cluster_texts = [highlights[i].text for i in indices]
        label = _generate_label(cluster_texts, texts)

        cluster = ThemeCluster(
            label=label,
            highlight_ids=[highlights[i].id for i in indices],
            representative_text=highlights[rep_idx].text,
            book_titles=[book.title],
            size=len(indices),
        )
        clusters.append(cluster)

    clusters.sort(key=lambda c: c.size, reverse=True)
    return clusters


def cluster_highlights_across_books(
    books: list[Book],
    provider: EmbeddingProvider,
    *,
    max_clusters: int = 12,
) -> list[ThemeCluster]:
    """Cluster highlights across all books to surface recurring ideas."""
    all_highlights = []
    all_book_titles = []
    for book in books:
        for a in book.annotations:
            if a.kind == "highlight" and a.text.strip():
                all_highlights.append(a)
                all_book_titles.append(book.title)

    if len(all_highlights) < 3:
        return []

    texts = [h.text for h in all_highlights]
    embeddings = provider.embed(texts)

    k = _optimal_k(embeddings, k_max=min(max_clusters, len(all_highlights) // 3 or 2))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(embeddings)

    clusters: list[ThemeCluster] = []
    for cluster_id in range(k):
        indices = [i for i, lbl in enumerate(labels) if lbl == cluster_id]
        if not indices:
            continue

        centroid = km.cluster_centers_[cluster_id]
        cluster_embeds = embeddings[indices]
        sims = cosine_similarity(cluster_embeds, centroid.reshape(1, -1)).flatten()
        rep_idx = indices[int(np.argmax(sims))]

        book_titles = sorted(set(all_book_titles[i] for i in indices))

        cluster_texts = [all_highlights[i].text for i in indices]
        label = _generate_label(cluster_texts, texts)

        cluster = ThemeCluster(
            label=label,
            highlight_ids=[all_highlights[i].id for i in indices],
            representative_text=all_highlights[rep_idx].text,
            book_titles=book_titles,
            size=len(indices),
        )
        clusters.append(cluster)

    clusters.sort(key=lambda c: c.size, reverse=True)
    return clusters


def find_similar_highlights(
    query_text: str,
    books: list[Book],
    provider: EmbeddingProvider,
    *,
    top_n: int = 10,
    min_score: float = 0.4,
) -> list[HighlightSimilarity]:
    """Find highlights across the library that are most similar to a query."""
    all_highlights = []
    all_book_titles = []
    for book in books:
        for a in book.annotations:
            if a.kind == "highlight" and a.text.strip():
                all_highlights.append(a)
                all_book_titles.append(book.title)

    if not all_highlights:
        return []

    texts = [h.text for h in all_highlights]
    embeddings = provider.embed(texts)
    query_embedding = provider.embed([query_text])

    sims = cosine_similarity(query_embedding, embeddings).flatten()

    # Rank by similarity, filter by threshold
    ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)

    results: list[HighlightSimilarity] = []
    for idx, score in ranked[:top_n]:
        if score < min_score:
            break
        # Skip exact matches
        if all_highlights[idx].text.strip() == query_text.strip():
            continue
        results.append(
            HighlightSimilarity(
                source_text=query_text,
                source_book="(query)",
                match_text=all_highlights[idx].text,
                match_book=all_book_titles[idx],
                score=round(float(score), 4),
            )
        )

    return results


def compute_reading_insights(books: list[Book]) -> dict:
    """Compute reading insights from annotation metadata (no embeddings needed)."""
    author_highlights: Counter[str] = Counter()
    total_highlights = 0
    total_notes = 0
    books_with_annotations = 0

    for book in books:
        h_count = sum(1 for a in book.annotations if a.kind == "highlight")
        n_count = sum(1 for a in book.annotations if a.kind == "note")
        total_highlights += h_count
        total_notes += n_count
        if h_count + n_count > 0:
            books_with_annotations += 1
        if book.author and h_count > 0:
            author_highlights[book.author] += h_count

    return {
        "total_highlights": total_highlights,
        "total_notes": total_notes,
        "books_with_annotations": books_with_annotations,
        "top_highlighted_authors": author_highlights.most_common(10),
        "avg_highlights_per_book": (
            round(total_highlights / books_with_annotations, 1)
            if books_with_annotations
            else 0
        ),
    }
