from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.story_score import ScoredStoryCluster


class StorySelectionDecision(BaseModel):
    cluster_id: str
    status: Literal["selected", "rejected"]
    reason: str
    score_total: float = Field(ge=0.0)
    topic_label: str
    domain_label: str = "general"
    geography_label: str = "international"
    regional_relevance: Literal["region_match", "national", "international", "unknown"] = "unknown"
    source_labels: list[str]
    preference_influence_used: bool = False
    preference_influence_summary: str | None = None
    regional_preference_used: bool = False
    regional_preference_summary: str | None = None
    explanation: str


class StorySelectionStats(BaseModel):
    total_input_clusters: int
    selected_count: int
    rejected_count: int
    max_stories: int
    minimum_score_threshold: float


class StorySelectionResult(BaseModel):
    selected_clusters: list[ScoredStoryCluster]
    rejected_clusters: list[ScoredStoryCluster]
    decisions: list[StorySelectionDecision]
    selection_explanation: str
    selection_stats: StorySelectionStats
    selected_at: datetime
