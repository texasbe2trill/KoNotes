from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Annotation(BaseModel):
    id: str
    book_id: str
    kind: Literal["highlight", "note", "unknown"] = "unknown"
    text: str
    created_at: datetime | None = None
    chapter: str | None = None
    location: str | None = None
    source: str
