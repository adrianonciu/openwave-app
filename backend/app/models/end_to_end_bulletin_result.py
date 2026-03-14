from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.article_fetch import FetchedArticle
from app.models.user_personalization import EditorialPreferenceProfile, UserPersonalization
from app.models.audio_generation_package import AudioGenerationPackage
from app.models.final_editorial_briefing import FinalEditorialBriefingPackage


class TtsBudgetEstimate(BaseModel):
    provider: str
    presenter_name: str
    segment_count: int = Field(ge=0)
    estimated_total_characters: int = Field(ge=0)
    estimated_required_credits: int = Field(ge=0)
    remaining_credits: int | None = Field(default=None, ge=0)
    budget_check_performed: bool = False
    within_budget: bool | None = None


class EndToEndPipelineError(BaseModel):
    stage: Literal[
        "editorial_pipeline_failed",
        "editorial_contract_validation_failed",
        "audio_generation_package_failed",
        "tts_budget_preflight_failed",
        "tts_generation_failed",
    ]
    code: str
    message: str
    estimated_required_credits: int | None = Field(default=None, ge=0)
    remaining_credits: int | None = Field(default=None, ge=0)
    estimated_total_characters: int | None = Field(default=None, ge=0)
    segment_count: int | None = Field(default=None, ge=0)


class EndToEndExecutionStats(BaseModel):
    input_article_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    selected_story_count: int = Field(ge=0)
    final_story_count: int = Field(ge=0)
    generated_segment_count: int = Field(ge=0)


class EndToEndBulletinGenerationRequest(BaseModel):
    articles: list[FetchedArticle] = Field(min_length=1)
    bulletin_id: str | None = None
    presenter_name: str | None = None
    personalization: UserPersonalization | None = None
    editorial_preferences: EditorialPreferenceProfile | None = None


class EndToEndBulletinResult(BaseModel):
    bulletin_id: str | None = None
    final_editorial_briefing: FinalEditorialBriefingPackage | None = None
    audio_generation_package: AudioGenerationPackage | None = None
    generated_audio_segments: list[str] = Field(default_factory=list)
    generated_audio_paths: list[str] = Field(default_factory=list)
    estimated_total_duration_seconds: int = Field(ge=0)
    execution_summary: str
    success: bool
    errors: list[EndToEndPipelineError] = Field(default_factory=list)
    execution_stats: EndToEndExecutionStats | None = None
    presenter_name: str | None = None
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
    personalization_explanation: str = "Pipeline used safe neutral personalization defaults."
    tts_provider: str | None = None
    tts_voice_id: str | None = None
    tts_budget_estimate: TtsBudgetEstimate | None = None
    editorial_validation_passed: bool | None = None
    editorial_validation_report_path: str | None = None
    created_at: datetime
