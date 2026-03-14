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
    editorial_fit: ScoreComponent


class ScoredStoryCluster(BaseModel):
    cluster: StoryCluster
    score_total: float = Field(ge=0.0)
    score_breakdown: StoryScoreBreakdown
    scoring_explanation: str
    scored_at: datetime
