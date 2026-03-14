from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.source_watcher import DetectedContentItem, LatestContentItem


class FetchedArticle(BaseModel):
    url: str
    title: str
    author: str | None = None
    published_at: datetime | None = None
    source: str
    content_text: str
    ingestion_kind: Literal["full_fetch", "rss_fallback", "unknown"] = "unknown"
    editorial_priority: int = 3
    is_local_source: bool = False


class ArticleFetchResult(BaseModel):
    status: Literal[
        "success",
        "network_error",
        "timeout",
        "invalid_html",
        "content_extraction_failed",
        "error",
    ]
    article: FetchedArticle | None = None
    error_message: str | None = None
    extraction_method: Literal["json_ld", "article_tag", "heuristic", "paragraph_fallback"] | None = None
    cached: bool = False


FetchArticleInput = str | LatestContentItem | DetectedContentItem
