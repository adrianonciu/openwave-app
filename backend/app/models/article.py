from datetime import datetime

from pydantic import BaseModel, Field


class Article(BaseModel):
    id: int
    title: str
    source: str
    summary: str
    url: str
    published_at: datetime = Field(description="UTC publication timestamp")