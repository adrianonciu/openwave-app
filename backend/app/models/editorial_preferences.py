from pydantic import BaseModel, Field


class GeographyPreferenceMix(BaseModel):
    local: float = Field(default=0.0, ge=0.0, le=100.0)
    national: float = Field(default=0.0, ge=0.0, le=100.0)
    international: float = Field(default=0.0, ge=0.0, le=100.0)


class DomainPreferenceMix(BaseModel):
    politics: float = Field(default=0.0, ge=0.0, le=100.0)
    economy: float = Field(default=0.0, ge=0.0, le=100.0)
    sport: float = Field(default=0.0, ge=0.0, le=100.0)
    entertainment: float = Field(default=0.0, ge=0.0, le=100.0)
    education: float = Field(default=0.0, ge=0.0, le=100.0)
    health: float = Field(default=0.0, ge=0.0, le=100.0)
    tech: float = Field(default=0.0, ge=0.0, le=100.0)


class EditorialPreferenceProfile(BaseModel):
    geography: GeographyPreferenceMix = Field(default_factory=GeographyPreferenceMix)
    domains: DomainPreferenceMix = Field(default_factory=DomainPreferenceMix)
