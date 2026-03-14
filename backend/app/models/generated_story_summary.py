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
    story_id: str
    story_type: Literal["short", "major"] = "short"
    headline: str
    lead: str
    body: str
    source_attribution: str
    quotes: list[str] = Field(default_factory=list)
    editorial_notes: list[str] = Field(default_factory=list)
    short_headline: str
    lead_type: Literal["impact", "decision", "warning", "conflict", "change", "event"]
    story_continuity_type: Literal["new_story", "update", "major_update"] = "new_story"
    continuity_detected: bool = False
    continuity_explanation: str = "Cluster did not appear in the previous bulletin."
    summary_text: str
    sentence_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    topic_label: str = "general"
    source_labels: list[str] = Field(default_factory=list)
    attribution_type: Literal["direct_quote", "official_statement", "source_attribution"]
    attribution_variant: str = "potrivit"
    summary_variation_used: bool = False
    quote_line: str | None = None
    memorable_quote_used: bool = False
    essential_numbers_kept: bool = False
    nonessential_numbers_removed: bool = False
    expanded_summary_used: bool = False
    casualty_line_included: bool = False
    context_line_included: bool = False
    representative_title: str | None = None
    score_total: float | None = Field(default=None, ge=0.0)
    policy_compliance: SummaryComplianceReport
    generation_explanation: str
    generated_at: datetime
    source_basis: Literal["story_cluster", "scored_story_cluster"]
