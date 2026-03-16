from __future__ import annotations

from pydantic import BaseModel, Field


class RadioStoryDraft(BaseModel):
    title: str
    summary_sentences: list[str] = Field(default_factory=list)
    main_actor_name: str | None = None
    main_actor_role: str | None = None
    attributed_quote: str | None = None
    impact_sentence: str | None = None
    source_name: str
    original_url: str
    summarization_method: str = "llm"
    actor_detected: bool = False
    quote_detected: bool = False
    impact_detected: bool = False
    skip_reason: str | None = None
