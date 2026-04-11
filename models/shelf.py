"""Model representing a Kobo shelf / collection."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Shelf(BaseModel):
    """A Kobo shelf (collection) with its member book IDs."""

    name: str
    internal_name: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    book_count: int = 0
