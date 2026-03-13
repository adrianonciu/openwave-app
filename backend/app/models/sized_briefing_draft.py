from datetime import datetime

from pydantic import BaseModel, Field

from app.models.generated_briefing_draft import BriefingStoryItem


class BulletinSizingAction(BaseModel):
    action: str
    story_cluster_ids: list[str] = Field(default_factory=list)
    explanation: str


class SizedBriefingDraft(BaseModel):
    briefing_id: str
    intro_text: str
    story_items: list[BriefingStoryItem]
    outro_text: str
    estimated_total_word_count: int = Field(ge=0)
    estimated_total_duration_seconds: int = Field(ge=0)
    target_duration_seconds: int = Field(ge=0)
    tolerance_seconds: int = Field(ge=0)
    original_duration_seconds: int = Field(ge=0)
    sizing_actions: list[BulletinSizingAction]
    stories_removed: list[str] = Field(default_factory=list)
    stories_kept: list[str] = Field(default_factory=list)
    sizing_explanation: str
    sized_at: datetime
