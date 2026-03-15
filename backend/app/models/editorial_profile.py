from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EditorialProfile(BaseModel):
    name: str
    scope: Literal["local", "national", "international"]
    display_name: str
    priority_domains: list[str] = Field(default_factory=list)
    impact_keywords: list[str] = Field(default_factory=list)
    source_preferences: list[str] = Field(default_factory=list)
    purity_thresholds: dict[str, float] = Field(default_factory=dict)
    recovery_flags: dict[str, bool] = Field(default_factory=dict)
    diversity_rules: dict[str, float | int | bool] = Field(default_factory=dict)
    geographic_signals: list[str] = Field(default_factory=list)
    debug_sections: list[str] = Field(default_factory=list)

    @property
    def profile_config_name(self) -> str:
        return self.name

    @property
    def output_key(self) -> str:
        if self.scope == "international":
            return "global"
        return self.scope
