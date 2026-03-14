from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EditorialContractAutoFix(BaseModel):
    rule: str
    message: str
    story_id: str | None = None
    field_name: str | None = None
    original_value: str | None = None
    updated_value: str | None = None


class EditorialContractViolation(BaseModel):
    rule: str
    severity: Literal["blocking", "auto_fix", "warning"]
    message: str
    story_id: str | None = None
    segment_id: str | None = None
    field_name: str | None = None


class StoryValidationResult(BaseModel):
    story_id: str
    passed: bool
    violations: list[EditorialContractViolation] = Field(default_factory=list)
    auto_fixes: list[EditorialContractAutoFix] = Field(default_factory=list)


class BulletinValidationResult(BaseModel):
    passed: bool
    briefing_id: str
    validated_at: datetime
    blocking_violation_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    auto_fix_count: int = Field(ge=0)
    story_results: list[StoryValidationResult] = Field(default_factory=list)
    violations: list[EditorialContractViolation] = Field(default_factory=list)
    auto_fixes: list[EditorialContractAutoFix] = Field(default_factory=list)
    report_path: str | None = None
    summary: str = ""
