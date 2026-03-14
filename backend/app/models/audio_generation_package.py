from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AudioStorySegment(BaseModel):
    segment_id: str
    story_text: str = Field(..., min_length=1)
    topic_label: str = "general"
    source_labels: list[str] = Field(default_factory=list)
    presenter_name: str | None = None


class AudioSegmentBlock(BaseModel):
    segment_name: str
    segment_type: Literal["intro", "story", "perspective", "stinger", "outro"]
    text: str | None = None
    audio_file: str | None = None
    topic_label: str | None = None
    source_labels: list[str] = Field(default_factory=list)
    presenter_name: str | None = None


class AudioGenerationPackage(BaseModel):
    briefing_id: str
    intro_text: str = Field(..., min_length=1)
    story_segments: list[AudioStorySegment] = Field(min_length=1)
    ordered_segments: list[AudioSegmentBlock] = Field(min_length=3)
    outro_text: str = Field(..., min_length=1)
    segment_count: int = Field(ge=3)
    estimated_duration_seconds: int = Field(ge=0)
    created_at: datetime


class AudioGenerationPackageError(BaseModel):
    code: Literal[
        "missing_intro_text",
        "missing_story_segments",
        "missing_outro_text",
    ]
    message: str


class AudioGenerationPreparationResult(BaseModel):
    status: Literal["success", "error"]
    package: AudioGenerationPackage | None = None
    error: AudioGenerationPackageError | None = None
