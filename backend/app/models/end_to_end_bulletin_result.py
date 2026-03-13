from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.article_fetch import FetchedArticle
from app.models.user_personalization import EditorialPreferenceProfile, UserPersonalization
from app.models.audio_generation_package import AudioGenerationPackage
from app.models.final_editorial_briefing import FinalEditorialBriefingPackage


class EndToEndPipelineError(BaseModel):
    stage: Literal[
        "editorial_pipeline_failed",
        "audio_generation_package_failed",
        "tts_generation_failed",
    ]
    code: str
    message: str


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
    personalization_explanation: str = "Pipeline used safe neutral personalization defaults."
    tts_provider: str | None = None
    tts_voice_id: str | None = None
    created_at: datetime
