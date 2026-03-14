from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.article_fetch import FetchedArticle


class NewsClusteringArticle(BaseModel):
    url: str
    title: str
    source: str
    published_at: datetime
    content_text: str
    ingestion_kind: Literal["full_fetch", "rss_fallback", "unknown"] = "unknown"
    editorial_priority: int = 3
    is_local_source: bool = False

    @classmethod
    def from_fetched_article(cls, article: FetchedArticle) -> "NewsClusteringArticle":
        published_at = article.published_at or datetime.now(UTC)
        return cls(
            url=article.url,
            title=article.title,
            source=article.source,
            published_at=published_at,
            content_text=article.content_text,
            ingestion_kind=article.ingestion_kind,
            editorial_priority=article.editorial_priority,
            is_local_source=article.is_local_source,
        )


class ClusterMemberArticle(BaseModel):
    url: str
    title: str
    source: str
    published_at: datetime
    ingestion_kind: Literal["full_fetch", "rss_fallback", "unknown"] = "unknown"
    editorial_priority: int = Field(default=3, ge=1, le=5)
    is_local_source: bool = False


class StoryCluster(BaseModel):
    cluster_id: str
    representative_title: str
    member_articles: list[ClusterMemberArticle]
    created_at: datetime
    latest_published_at: datetime


class ClusterDecision(BaseModel):
    status: Literal["merged", "separate"]
    reason: str
    title_similarity: float = Field(ge=0.0, le=1.0)
    keyword_overlap: float = Field(ge=0.0, le=1.0)
    body_overlap: float = Field(ge=0.0, le=1.0)
    shared_entities: list[str] = Field(default_factory=list)
    hours_apart: float = Field(ge=0.0)
