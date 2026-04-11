from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from models.annotation import Annotation


class Book(BaseModel):
    id: str
    title: str
    author: str | None = None
    subtitle: str | None = None
    series: str | None = None
    source: str
    annotations: list[Annotation] = []
    shelves: list[str] = []
    read_status: str | None = None
    read_percent: float | None = None
    date_last_read: datetime | None = None
    publisher: str | None = None
    isbn: str | None = None
    language: str | None = None
    content_type: str | None = None
    is_archived: bool = False
    is_favorited: bool = False
    date_added: datetime | None = None
    time_spent_reading: int | None = None  # seconds
    times_started_reading: int | None = None
    last_time_started: datetime | None = None
    last_time_finished: datetime | None = None
    page_count: int | None = None
    word_count: int | None = None
    rating: int | None = None  # 1-5 star rating
    page_turns: int | None = None  # total page turn events
