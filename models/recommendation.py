"""Recommendation model — a single actionable suggestion grounded in the user's own library."""
from __future__ import annotations

from dataclasses import dataclass, field

# Stable kind identifiers (used in CSS, tests, and formatters).
KIND_REVISIT = "revisit"
KIND_FINISH = "finish"
KIND_EXPORT = "export"
KIND_FORGOTTEN_GEM = "forgotten_gem"
KIND_DEEPEST_THINKING = "deepest_thinking"
KIND_COMPARE = "compare"


@dataclass
class Recommendation:
    """A single actionable recommendation grounded in the user's own library data.

    Each recommendation must be fully explainable from first principles:
    *reason* is the one-sentence justification, *evidence* is the supporting data,
    *recommended_action* is the concrete next step.
    """

    id: str
    kind: str  # one of KIND_* constants above
    title: str
    summary: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    priority_score: float = 0.0  # 0.0–1.0; higher = surfaces first
    related_books: list[str] = field(default_factory=list)
    recommended_action: str = ""
    source: str = "rule"  # "rule" | "engagement" | "similarity"
