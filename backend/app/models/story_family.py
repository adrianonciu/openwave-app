from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class StoryFamily(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    topic_hint: str | None = None
    first_seen_timestamp: datetime = Field(
        validation_alias=AliasChoices("first_seen", "first_seen_timestamp"),
        serialization_alias="first_seen",
    )
    last_seen_timestamp: datetime = Field(
        validation_alias=AliasChoices("last_seen", "last_seen_timestamp"),
        serialization_alias="last_seen",
    )
    story_count: int = Field(default=0, ge=0)
    source_count: int = Field(default=0, ge=0)
    run_count: int = Field(default=0, ge=0)
    event_hints: list[str] = Field(default_factory=list)
