from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user_personalization import EditorialPreferenceProfile, UserPersonalization
from app.models.generated_briefing_draft import BriefingStoryItem
from app.models.sized_briefing_draft import BulletinSizingAction


class EditorialPipelineIntermediateCounts(BaseModel):
    article_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    scored_cluster_count: int = Field(ge=0)
    selected_story_count: int = Field(ge=0)
    generated_summary_count: int = Field(ge=0)


class FinalEditorialBriefingPackage(BaseModel):
    briefing_id: str
    intro_text: str
    intro_variant: str = "intro_01"
    story_items: list[BriefingStoryItem]
    outro_text: str
    outro_variant: str = "outro_01"
    listener_name_mentions: int = Field(default=0, ge=0, le=2)
    estimated_total_word_count: int = Field(ge=0)
    estimated_total_duration_seconds: int = Field(ge=0)
    target_duration_seconds: int = Field(ge=0)
    tolerance_seconds: int = Field(ge=0)
    original_duration_seconds: int = Field(ge=0)
    intermediate_counts: EditorialPipelineIntermediateCounts
    personalization: UserPersonalization = Field(default_factory=UserPersonalization)
    editorial_preferences: EditorialPreferenceProfile | None = None
    personalization_used: bool = False
    listener_profile_used: bool = False
    editorial_preferences_used: bool = False
    personalization_defaults_applied: bool = True
    local_editorial_anchor: str | None = None
    local_editorial_anchor_scope: str = "none"
    local_source_region_used: str | None = None
    local_source_count: int = Field(default=0, ge=0)
    local_source_registry_used: bool = False
    local_sources_enabled: bool = False
    local_sources_monitored: bool = False
    media_source_credits: list[str] = Field(default_factory=list)
    personalization_explanation: str = "Pipeline used safe neutral personalization defaults."
    selection_explanation: str
    bulletin_shaping_explanation: str = "Bulletin shaping was not applied."
    assembly_explanation: str
    sizing_explanation: str
    sizing_actions: list[BulletinSizingAction]
    trimmed: bool = False
    pipeline_explanation: str
    created_at: datetime
