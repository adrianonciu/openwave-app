from datetime import datetime

from pydantic import BaseModel, Field


class StoryFamily(BaseModel):
    id: str
    topic_hint: str | None = None
    first_seen_timestamp: datetime
    last_seen_timestamp: datetime
    story_count: int = Field(default=0, ge=0)
    source_count: int = Field(default=0, ge=0)
    event_hints: list[str] = Field(default_factory=list)
