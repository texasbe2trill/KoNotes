"""Models for reading activity and progress telemetry."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProgressSnapshot(BaseModel):
    """A point-in-time reading progress record for a book."""

    book_id: str
    percent: float
    recorded_at: datetime | None = None


class ReadingSession(BaseModel):
    """An inferred reading session derived from Kobo event timestamps.

    KoNotes infers sessions from timestamp gaps in the Kobo database.
    The ``inferred`` flag marks that this data was computed, not extracted
    directly.
    """

    book_id: str
    book_title: str
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    start_percent: float | None = None
    end_percent: float | None = None
    inferred: bool = True
