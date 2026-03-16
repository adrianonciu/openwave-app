from __future__ import annotations

from pydantic import BaseModel, Field


class RadioSentenceDecision(BaseModel):
    text: str
    score: float
    role: str
    reasons: list[str] = Field(default_factory=list)


class CompressedStoryCore(BaseModel):
    story_id: str
    headline_original: str
    source_text_word_count: int = Field(ge=0)
    compressed_text: str
    compressed_word_count: int = Field(ge=0)
    estimated_duration_seconds: int = Field(ge=0)
    compressed_facts: dict[str, str] = Field(default_factory=dict)
    kept_sentences: list[RadioSentenceDecision] = Field(default_factory=list)
    dropped_sentences: list[RadioSentenceDecision] = Field(default_factory=list)
    kept_entities: list[str] = Field(default_factory=list)
    dropped_entities: list[str] = Field(default_factory=list)
    debug_notes: list[str] = Field(default_factory=list)


class RadioEditedStory(BaseModel):
    story_id: str
    headline_original: str
    compressed_facts: dict[str, str] = Field(default_factory=dict)
    radio_sentences: list[str] = Field(default_factory=list)
    radio_text: str
    estimated_word_count: int = Field(ge=0)
    estimated_duration_seconds: int = Field(ge=0)
    kept_entities: list[str] = Field(default_factory=list)
    dropped_entities: list[str] = Field(default_factory=list)
    editing_debug_notes: list[str] = Field(default_factory=list)
    compression_debug: CompressedStoryCore

