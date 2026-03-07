from pydantic import BaseModel


class Segment(BaseModel):
    id: int
    type: str
    title: str
    summary: str
    source: str
    estimated_duration_seconds: int
    tags: list[str]
    article_id: int
