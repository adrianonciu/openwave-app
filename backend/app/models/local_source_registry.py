from pydantic import BaseModel, Field


class LocalSourceEntry(BaseModel):
    source_name: str
    source_url: str
    category: str = "general"
    scope: str = "local"
    country: str = "Romania"
    language: str = "ro"
    enabled: bool = True
    editorial_priority: int = Field(default=3, ge=1, le=5)
    priority_rank: int = Field(ge=1)
    notes: str | None = None


class LocalCountySourceGroup(BaseModel):
    county_name: str
    source_entries: list[LocalSourceEntry] = Field(default_factory=list)
