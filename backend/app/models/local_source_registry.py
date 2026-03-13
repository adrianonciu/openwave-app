from pydantic import BaseModel, Field


class LocalSourceEntry(BaseModel):
    source_name: str
    source_url: str
    priority_rank: int = Field(ge=1)
    notes: str | None = None


class LocalCountySourceGroup(BaseModel):
    county_name: str
    source_entries: list[LocalSourceEntry] = Field(default_factory=list)
