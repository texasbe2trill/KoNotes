"""Models for AI/ML insight features: themes, clusters, similarities, summaries."""
from __future__ import annotations

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
