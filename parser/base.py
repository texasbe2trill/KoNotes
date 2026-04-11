"""Abstract base for all KoNotes parsers.

Each parser receives raw file content (str or bytes) and returns a list of
raw annotation dicts that the normalizer converts into typed models.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseParser(ABC):
    """Common interface every export parser must implement."""

    source_name: str = "unknown"

    @abstractmethod
    def parse(self, content: str) -> list[dict[str, Any]]:
        """Parse raw file content into a list of raw annotation dicts.

        Each dict should contain at minimum:
            - ``book_title`` (str)
            - ``text`` (str)
            - ``kind`` (str): "highlight" | "note" | "unknown"
        Optional fields: ``author``, ``chapter``, ``location``, ``created_at``.
        """
