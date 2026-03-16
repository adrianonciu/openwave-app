from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.article_fetch import FetchedArticle
from app.models.radio_story_draft import RadioStoryDraft


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
    source_region: str | None = None
    is_local_source: bool = False
    national_preference_bucket: Literal["domestic_hard_news", "external_direct_impact", "off_target"] | None = None
    national_preference_reason: str | None = None
    domestic_score_total: float | None = None
    headline_gate_passed: bool | None = None
    romanian_event_family_hints: list[str] = Field(default_factory=list)
    institutional_signal_hits: list[str] = Field(default_factory=list)
    romania_impact_evidence_hits: list[str] = Field(default_factory=list)
    title_only_domestic_boost: float = 0.0
    geo_scope: Literal["county", "regional", "national", "international"] | None = None
    county_detected: str | None = None
    region_detected: str | None = None
    county_match_confidence: float | None = None
    geo_signals: list[str] = Field(default_factory=list)
    radio_story_draft: RadioStoryDraft | None = None
    summarization_method: str | None = None
    summarization_actor_detected: bool | None = None
    summarization_quote_detected: bool | None = None
    summarization_impact_detected: bool | None = None
    summarization_fallback_used: bool = False
    summarization_skip_reason: str | None = None

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
            source_region=article.source_region,
            is_local_source=article.is_local_source,
            national_preference_bucket=article.national_preference_bucket,
            national_preference_reason=article.national_preference_reason,
            domestic_score_total=article.domestic_score_total,
            headline_gate_passed=article.headline_gate_passed,
            romanian_event_family_hints=article.romanian_event_family_hints,
            institutional_signal_hits=article.institutional_signal_hits,
            romania_impact_evidence_hits=article.romania_impact_evidence_hits,
            title_only_domestic_boost=article.title_only_domestic_boost,
            geo_scope=article.geo_scope,
            county_detected=article.county_detected,
            region_detected=article.region_detected,
            county_match_confidence=article.county_match_confidence,
            geo_signals=article.geo_signals,
            radio_story_draft=article.radio_story_draft,
            summarization_method=article.summarization_method,
            summarization_actor_detected=article.summarization_actor_detected,
            summarization_quote_detected=article.summarization_quote_detected,
            summarization_impact_detected=article.summarization_impact_detected,
            summarization_fallback_used=article.summarization_fallback_used,
            summarization_skip_reason=article.summarization_skip_reason,
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
    source_region: str | None = None
    is_local_source: bool = False
    national_preference_bucket: Literal["domestic_hard_news", "external_direct_impact", "off_target"] | None = None
    national_preference_reason: str | None = None
    domestic_score_total: float | None = None
    headline_gate_passed: bool | None = None
    romanian_event_family_hints: list[str] = Field(default_factory=list)
    institutional_signal_hits: list[str] = Field(default_factory=list)
    romania_impact_evidence_hits: list[str] = Field(default_factory=list)
    title_only_domestic_boost: float = 0.0
    geo_scope: Literal["county", "regional", "national", "international"] | None = None
    county_detected: str | None = None
    region_detected: str | None = None
    county_match_confidence: float | None = None
    geo_signals: list[str] = Field(default_factory=list)


class StoryCluster(BaseModel):
    cluster_id: str
    representative_title: str
    representative_summary: str | None = None
    member_articles: list[ClusterMemberArticle]
    source_names: list[str] = Field(default_factory=list)
    original_urls: list[str] = Field(default_factory=list)
    geo_scope: Literal["county", "regional", "national", "international"] | None = None
    county_detected: str | None = None
    region_detected: str | None = None
    cluster_size: int = Field(default=1, ge=1)
    created_at: datetime
    latest_published_at: datetime
    representative_radio_story_draft: RadioStoryDraft | None = None
    representative_source_name: str | None = None
    representative_original_url: str | None = None


class ClusterDecision(BaseModel):
    status: Literal["merged", "separate"]
    reason: str
    title_similarity: float = Field(ge=0.0, le=1.0)
    keyword_overlap: float = Field(ge=0.0, le=1.0)
    body_overlap: float = Field(ge=0.0, le=1.0)
    shared_entities: list[str] = Field(default_factory=list)
    hours_apart: float = Field(ge=0.0)
