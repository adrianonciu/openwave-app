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
    source_scope: Literal["local", "national", "international"] | None = None
    source_category: str | None = None
    is_local_source: bool = False
    national_preference_bucket: Literal["domestic_hard_news", "external_direct_impact", "off_target"] | None = None
    national_preference_reason: str | None = None
    domestic_hard_news_positive_signals: list[str] = []
    domestic_hard_news_negative_signals: list[str] = []
    classifier_decision_reason: str | None = None


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
