from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SummaryComplianceReport(BaseModel):
    sentence_count_ok: bool
    word_count_ok: bool
    structure_ok: bool
    banned_patterns_found: list[str]
    estimated_duration_seconds: int = Field(ge=0)
    notes: list[str]


class GeneratedStorySummary(BaseModel):
    cluster_id: str
    summary_text: str
    sentence_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    topic_label: str = "general"
    source_labels: list[str] = Field(default_factory=list)
    representative_title: str | None = None
    score_total: float | None = Field(default=None, ge=0.0)
    policy_compliance: SummaryComplianceReport
    generation_explanation: str
    generated_at: datetime
    source_basis: Literal["story_cluster", "scored_story_cluster"]
