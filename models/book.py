from __future__ import annotations

from pydantic import BaseModel

from models.annotation import Annotation


class Book(BaseModel):
    id: str
    title: str
    author: str | None = None
    source: str
    annotations: list[Annotation] = []
