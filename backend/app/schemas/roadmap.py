"""Roadmap schema。"""

from pydantic import BaseModel


class RoadmapItem(BaseModel):
    id: str
    title: str
    summary: str
    doc_url: str
    category: str


class Roadmap(BaseModel):
    items: list[RoadmapItem]
    total: int
