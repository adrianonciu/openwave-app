from pydantic import BaseModel, Field

from app.models.story_score import ScoredStoryCluster


class BulletinShapingDecision(BaseModel):
    position: int = Field(ge=1)
    cluster_id: str
    headline: str
    topic_bucket: str
    story_family_id: str | None = None
    decision_reason: str
    radio_priority_score: float | None = None
    ordering_signals: dict[str, float] = Field(default_factory=dict)


class BulletinShapingResult(BaseModel):
    profile_name: str
    ordered_clusters: list[ScoredStoryCluster]
    lead_cluster_id: str | None = None
    shaping_explanation: str
    decisions: list[BulletinShapingDecision] = Field(default_factory=list)
