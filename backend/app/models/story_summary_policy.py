from typing import Literal

from pydantic import BaseModel, Field


class StorySummaryPolicy(BaseModel):
    editorial_principle: str
    preferred_sentence_count: int = Field(ge=1)
    min_sentence_count: int = Field(ge=1)
    max_sentence_count: int = Field(ge=1)
    target_duration_seconds_min: int = Field(ge=1)
    target_duration_seconds_max: int = Field(ge=1)
    target_word_count_min: int = Field(ge=1)
    target_word_count_max: int = Field(ge=1)
    attribution_style: str
    allow_quotes: bool
    summary_structure: list[str]
    priority_information: list[str]
    avoid_rules: list[str]
    conflict_policy: list[str]
    category_variations: dict[str, list[str]]


class StorySummaryPolicyExample(BaseModel):
    category: Literal["politics", "economy", "international_conflict", "sport"]
    raw_story_description: str
    policy_compliant_summary: str
    explanation: str


class StorySummaryPolicyBundle(BaseModel):
    policy: StorySummaryPolicy
    examples: list[StorySummaryPolicyExample]
