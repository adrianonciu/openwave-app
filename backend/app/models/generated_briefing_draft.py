from datetime import datetime

from pydantic import BaseModel, Field

from app.models.generated_story_summary import GeneratedStorySummary


class BriefingStoryItem(BaseModel):
    position: int = Field(ge=1)
    story: GeneratedStorySummary
    ordering_reason: str


class GeneratedBriefingDraft(BaseModel):
    briefing_id: str
    intro_text: str
    ordered_story_items: list[BriefingStoryItem]
    outro_text: str
    estimated_total_word_count: int = Field(ge=0)
    estimated_total_duration_seconds: int = Field(ge=0)
    assembly_explanation: str
    assembled_at: datetime
