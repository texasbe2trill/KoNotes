"""Models for AI/ML insight features: themes, clusters, similarities, summaries."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ThemeCluster(BaseModel):
    """A cluster of semantically related highlights within a book or across the library."""

    label: str
    highlight_ids: list[str] = Field(default_factory=list)
    representative_text: str
    book_titles: list[str] = Field(default_factory=list)
    size: int = 0


class HighlightSimilarity(BaseModel):
    """A pair of highlights with a similarity score."""

    source_text: str
    source_book: str
    match_text: str
    match_book: str
    score: float


class BookSummary(BaseModel):
    """A generated summary of what the reader learned from a book."""

    book_id: str
    book_title: str
    summary: str
    themes: list[str] = Field(default_factory=list)
    highlight_count: int = 0
    method: str = "template"  # "template" or "llm"


# ---------------------------------------------------------------------------
# Insight Feed models
# ---------------------------------------------------------------------------

# Canonical categories -- easy to extend by appending to this list.
INSIGHT_CATEGORIES: list[str] = [
    "Reading Patterns",
    "Highlight Behavior",
    "Vocabulary Activity",
    "Most Engaged Books",
    "Books in Progress",
    "Cross-Book Themes",
    "Forgotten Insights",
    "Reading Momentum",
    "Deep Reading Signals",
    "Book Summary",
    "Library Overview",
]


class EvidenceItem(BaseModel):
    """A single piece of supporting evidence for an insight."""

    label: str
    value: str


class InsightCard(BaseModel):
    """A discrete, renderable insight within the Insight Feed."""

    id: str
    title: str
    category: str
    summary: str
    body: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)
    recommendation: str | None = None
    confidence: float | None = None
    priority_score: float = 0.0
    related_books: list[str] = Field(default_factory=list)
    source: str = "computed"
    created_at: datetime | None = None
