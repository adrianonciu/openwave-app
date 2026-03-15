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
    source_scope: Literal["local", "national", "international"] | None = None
    source_category: str | None = None
    is_local_source: bool = False
    national_preference_bucket: Literal["domestic_hard_news", "external_direct_impact", "off_target"] | None = None
    national_preference_reason: str | None = None
    domestic_score_total: float | None = None
    headline_gate_passed: bool | None = None
    romanian_event_family_hints: list[str] = Field(default_factory=list)
    institutional_signal_hits: list[str] = Field(default_factory=list)
    romania_impact_evidence_hits: list[str] = Field(default_factory=list)
    title_only_domestic_boost: float = 0.0

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
            source_scope=article.source_scope,
            source_category=article.source_category,
            is_local_source=article.is_local_source,
            national_preference_bucket=article.national_preference_bucket,
            national_preference_reason=article.national_preference_reason,
            domestic_score_total=article.domestic_score_total,
            headline_gate_passed=article.headline_gate_passed,
            romanian_event_family_hints=article.romanian_event_family_hints,
            institutional_signal_hits=article.institutional_signal_hits,
            romania_impact_evidence_hits=article.romania_impact_evidence_hits,
            title_only_domestic_boost=article.title_only_domestic_boost,
        )


class ClusterMemberArticle(BaseModel):
    url: str
    title: str
    source: str
    published_at: datetime
    ingestion_kind: Literal["full_fetch", "rss_fallback", "unknown"] = "unknown"
    editorial_priority: int = Field(default=3, ge=1, le=5)
    source_scope: Literal["local", "national", "international"] | None = None
    source_category: str | None = None
    is_local_source: bool = False
    national_preference_bucket: Literal["domestic_hard_news", "external_direct_impact", "off_target"] | None = None
    national_preference_reason: str | None = None
    domestic_score_total: float | None = None
    headline_gate_passed: bool | None = None
    romanian_event_family_hints: list[str] = Field(default_factory=list)
    institutional_signal_hits: list[str] = Field(default_factory=list)
    romania_impact_evidence_hits: list[str] = Field(default_factory=list)
    title_only_domestic_boost: float = 0.0


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
