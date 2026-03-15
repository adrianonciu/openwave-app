from datetime import datetime

from pydantic import BaseModel, Field

from app.models.news_cluster import StoryCluster


class ScoreComponent(BaseModel):
    name: str
    value: float
    max_points: float
    contribution: float
    explanation: str


class StoryScoreBreakdown(BaseModel):
    recency: ScoreComponent
    source_count: ScoreComponent
    source_quality: ScoreComponent
    entity_importance: ScoreComponent
    topic_weight: ScoreComponent
    title_strength: ScoreComponent
    europe_romania_impact: ScoreComponent
    romanian_domestic_balance: ScoreComponent
    editorial_fit: ScoreComponent
    family_lifecycle_boost: ScoreComponent


class ScoredStoryCluster(BaseModel):
    cluster: StoryCluster
    score_total: float = Field(ge=0.0)
    score_breakdown: StoryScoreBreakdown
    scoring_explanation: str
    scored_at: datetime
    domestic_purity_score: float = 0.0
    romania_impact_evidence_hits: list[str] = Field(default_factory=list)
    external_penalty_applied: float = 0.0
    title_only_domestic_boost: float = 0.0
    cluster_event_family_hints: list[str] = Field(default_factory=list)
    domestic_vs_external_rank_reason: str | None = None
    recovery_score: float = 0.0
    recovered_domestic_candidate: bool = False
    persistence_boost_applied: float = 0.0
    top5_balance_adjustment_reason: str | None = None
    recovery_rejection_reason: str | None = None
    failed_threshold_name: str | None = None
    threshold_required_value: float | str | None = None
    candidate_current_value: float | str | None = None
    story_family_id: str | None = None
    family_attach_reason: str | None = None
    editorial_profile_used: str | None = None
    profile_config_name: str | None = None
    shared_core_path_used: bool = False
    family_lifecycle_boost: float = 0.0
    family_first_seen: str | None = None
    family_last_seen: str | None = None
    family_run_count: int = 0
    family_age_hours: float = 0.0
