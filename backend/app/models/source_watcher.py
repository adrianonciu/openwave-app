from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    source_id: str
    source_name: str
    source_type: Literal["news", "commentary"]
    source_url: str
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
    source_type: Literal["news", "commentary"]


class SourceWatcherState(BaseModel):
    last_seen_url: str | None = None
    last_seen_title: str | None = None
    last_seen_published_at: datetime | None = None
    last_checked_at: datetime | None = None


class SourceCheckResult(BaseModel):
    source_id: str
    source_type: Literal["news", "commentary"]
    status: Literal["no_change", "new_content_detected", "error"]
    item: DetectedContentItem | None = None
    error_message: str | None = None


class SourceCheckSummary(BaseModel):
    checked_at: datetime
    results: list[SourceCheckResult]
