"""Model for vocabulary / dictionary lookups tracked by Kobo."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WordLookup(BaseModel):
    """A word looked up in the dictionary while reading."""

    word: str
    book_id: str
    book_title: str | None = None
    language: str | None = None
    looked_up_at: datetime | None = None
