from datetime import datetime
from typing import Literal

from app.models.local_source_registry import LocalSourceEntry

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    source_id: str
    source_name: str
    source_type: Literal["news", "commentary", "local_county"]
    source_url: str
    region: str | None = None
    priority_rank: int | None = Field(default=None, ge=1)
    rss_url: str | None = None
    parser_type: Literal["auto", "rss", "html_listing", "meta_page"] = "auto"
    check_interval_minutes: int = Field(default=30, ge=1)
    last_seen_url: str | None = None
    last_seen_title: str | None = None
    last_seen_published_at: datetime | None = None


class DetectedContentItem(BaseModel):
    url: str
    title: str
    published_at: datetime
    source_name: str


class LatestContentItem(DetectedContentItem):
    source_type: Literal["news", "commentary", "local_county"]


class SourceWatcherState(BaseModel):
    last_seen_url: str | None = None
    last_seen_title: str | None = None
    last_seen_published_at: datetime | None = None
    last_checked_at: datetime | None = None


class SourceCheckResult(BaseModel):
    source_id: str
    source_type: Literal["news", "commentary", "local_county"]
    status: Literal["no_change", "new_content_detected", "error"]
    item: DetectedContentItem | None = None
    error_message: str | None = None


class SourceCheckSummary(BaseModel):
    checked_at: datetime
    results: list[SourceCheckResult]


class LocalSourceResolutionResult(BaseModel):
    region_used: str | None = None
    resolved_sources: list[SourceConfig] = Field(default_factory=list)
    source_count: int = Field(default=0, ge=0)
    local_source_registry_used: bool = False
    local_sources_enabled: bool = False
    explanation: str
