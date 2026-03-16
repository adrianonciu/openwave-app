from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceRegistryEntry(BaseModel):
    source_id: str
    source_name: str
    scope: Literal['county', 'regional', 'national', 'international']
    county: str | None = None
    region: str | None = None
    language: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    access_method: Literal['rss', 'atom', 'listing_page', 'unknown'] = 'unknown'
    feed_url: str | None = None
    listing_url: str | None = None
    status: Literal['usable', 'fallback_only', 'unavailable'] = 'unavailable'
    active_in_live_mode: bool = False
    parser_type: str | None = None
    notes: str | None = None


class LiveStoryCandidate(BaseModel):
    source_id: str
    source_name: str
    source_scope: Literal['local', 'national', 'international']
    county: str | None = None
    region: str | None = None
    title: str
    summary: str = ''
    original_url: str
    published_at: datetime
    author: str | None = None
    language: str | None = None
    fetch_timestamp: datetime
    access_method: Literal['rss', 'atom', 'listing_page', 'unknown'] = 'unknown'
    priority: int = Field(default=3, ge=1, le=5)
    status: Literal['usable', 'fallback_only', 'unavailable'] = 'usable'
