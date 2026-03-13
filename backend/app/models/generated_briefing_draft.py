from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.generated_story_summary import GeneratedStorySummary


class BriefingStoryItem(BaseModel):
    position: int = Field(ge=1)
    story: GeneratedStorySummary
    presenter_voice: Literal["female", "male"] = "female"
    pass_phrase_used: str | None = None
    pacing_label: Literal["heavy", "medium", "light"] = "medium"
    ordering_reason: str


class GeneratedBriefingDraft(BaseModel):
    briefing_id: str
    intro_text: str
    intro_variant: str = "intro_01"
    ordered_story_items: list[BriefingStoryItem]
    outro_text: str
    outro_variant: str = "outro_01"
    estimated_total_word_count: int = Field(ge=0)
    estimated_total_duration_seconds: int = Field(ge=0)
    assembly_explanation: str
    assembled_at: datetime
