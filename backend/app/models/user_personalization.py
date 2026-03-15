from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


_GEOGRAPHY_KEYS = ["local", "national", "international"]
_DOMAIN_KEYS = [
    "politics",
    "economy",
    "justice",
    "sport",
    "entertainment",
    "education",
    "health",
    "tech",
]


def _normalize_mix(values: dict[str, float], keys: list[str]) -> dict[str, float]:
    filtered = {key: max(float(values.get(key, 0.0)), 0.0) for key in keys}
    total = sum(filtered.values())

    if total <= 0:
        equal = round(100.0 / len(keys), 4)
        normalized = {key: equal for key in keys}
        normalized[keys[-1]] = round(100.0 - sum(normalized[key] for key in keys[:-1]), 4)
        return normalized

    if 0.99 <= total <= 1.01:
        scale = 100.0
    elif 99.0 <= total <= 101.0:
        scale = 1.0
    else:
        scale = 100.0 / total

    normalized = {key: round(value * scale, 4) for key, value in filtered.items()}
    normalized[keys[-1]] = round(100.0 - sum(normalized[key] for key in keys[:-1]), 4)
    return normalized


class ListenerProfile(BaseModel):
    first_name: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None

    def is_neutral(self) -> bool:
        return not any(
            value and str(value).strip()
            for value in [self.first_name, self.country, self.region, self.city]
        )

    def primary_local_anchor(self) -> str | None:
        region = (self.region or '').strip()
        if region:
            return region
        city = (self.city or '').strip()
        if city:
            return city
        return None

    def primary_local_anchor_scope(self) -> str:
        if (self.region or '').strip():
            return 'region'
        if (self.city or '').strip():
            return 'city_fallback'
        return 'none'

    def primary_local_anchor_explanation(self) -> str:
        scope = self.primary_local_anchor_scope()
        anchor = self.primary_local_anchor()
        if scope == 'region' and anchor:
            return f"Local editorial anchor uses listener region or county '{anchor}' as the primary local reference."
        if scope == 'city_fallback' and anchor:
            return f"Listener city '{anchor}' is stored and used only as a fallback because no region or county was provided."
        return 'No local editorial anchor was provided in the listener profile.'


class GeographyPreferenceMix(BaseModel):
    local: float = Field(default=0.0, ge=0.0, le=100.0)
    national: float = Field(default=0.0, ge=0.0, le=100.0)
    international: float = Field(default=0.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def normalize(self) -> "GeographyPreferenceMix":
        normalized = _normalize_mix(self.model_dump(), _GEOGRAPHY_KEYS)
        for key, value in normalized.items():
            object.__setattr__(self, key, value)
        return self


class DomainPreferenceMix(BaseModel):
    politics: float = Field(default=0.0, ge=0.0, le=100.0)
    economy: float = Field(default=0.0, ge=0.0, le=100.0)
    justice: float = Field(default=0.0, ge=0.0, le=100.0)
    sport: float = Field(default=0.0, ge=0.0, le=100.0)
    entertainment: float = Field(default=0.0, ge=0.0, le=100.0)
    education: float = Field(default=0.0, ge=0.0, le=100.0)
    health: float = Field(default=0.0, ge=0.0, le=100.0)
    tech: float = Field(default=0.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def normalize(self) -> "DomainPreferenceMix":
        normalized = _normalize_mix(self.model_dump(), _DOMAIN_KEYS)
        for key, value in normalized.items():
            object.__setattr__(self, key, value)
        return self


class EditorialPreferenceProfile(BaseModel):
    geography: GeographyPreferenceMix = Field(default_factory=GeographyPreferenceMix)
    domains: DomainPreferenceMix = Field(default_factory=DomainPreferenceMix)

    def is_neutral(self) -> bool:
        default_profile = EditorialPreferenceProfile()
        return self.model_dump() == default_profile.model_dump()


class UserPersonalization(BaseModel):
    listener_profile: ListenerProfile = Field(default_factory=ListenerProfile)
    editorial_preferences: EditorialPreferenceProfile = Field(default_factory=EditorialPreferenceProfile)

    def personalization_used(self) -> bool:
        return self.listener_profile_used() or self.editorial_preferences_used()

    def listener_profile_used(self) -> bool:
        return not self.listener_profile.is_neutral()

    def editorial_preferences_used(self) -> bool:
        return not self.editorial_preferences.is_neutral()

    def defaults_applied(self) -> bool:
        return not self.personalization_used()

    def local_editorial_anchor(self) -> str | None:
        return self.listener_profile.primary_local_anchor()

    def local_editorial_anchor_scope(self) -> str:
        return self.listener_profile.primary_local_anchor_scope()

    def local_editorial_anchor_explanation(self) -> str:
        return self.listener_profile.primary_local_anchor_explanation()

    def explainability(self) -> tuple[bool, bool, bool, bool, str]:
        personalization_used = self.personalization_used()
        listener_profile_used = self.listener_profile_used()
        editorial_preferences_used = self.editorial_preferences_used()
        defaults_applied = self.defaults_applied()
        local_anchor_note = self.local_editorial_anchor_explanation()
        explanation = (
            f"User personalization was provided and carried through the pipeline. {local_anchor_note}"
            if personalization_used
            else "Pipeline used safe neutral personalization defaults because no explicit personalization payload was provided."
        )
        return (
            personalization_used,
            listener_profile_used,
            editorial_preferences_used,
            defaults_applied,
            explanation,
        )

    @classmethod
    def from_input(
        cls,
        personalization: UserPersonalization | None = None,
        editorial_preferences: EditorialPreferenceProfile | None = None,
        listener_profile: ListenerProfile | None = None,
    ) -> "UserPersonalization":
        if personalization is not None:
            return personalization
        if editorial_preferences is not None or listener_profile is not None:
            return cls(
                listener_profile=listener_profile or ListenerProfile(),
                editorial_preferences=editorial_preferences or EditorialPreferenceProfile(),
            )
        return cls()
