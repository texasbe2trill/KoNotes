from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from models.annotation import Annotation


class Book(BaseModel):
    id: str
    title: str
    author: str | None = None
    subtitle: str | None = None
    source: str
    annotations: list[Annotation] = []
    shelves: list[str] = []
    read_status: str | None = None
    read_percent: float | None = None
    date_last_read: datetime | None = None
    publisher: str | None = None
    isbn: str | None = None
    language: str | None = None
