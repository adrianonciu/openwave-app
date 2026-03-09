from pydantic import BaseModel, model_validator


class Segment(BaseModel):
    TYPE_SECTION_CUE: str = "section_cue"

    id: int
    type: str
    title: str
    summary: str
    source: str
    estimated_duration_seconds: int
    tags: list[str]
    article_id: int
    narration_text: str = ""
    section: str = "General"
    duration_estimate: int | None = None

    @model_validator(mode="after")
    def apply_compatibility_fallbacks(self) -> "Segment":
        if not self.narration_text:
            self.narration_text = self.summary

        if self.duration_estimate is None:
            self.duration_estimate = self.estimated_duration_seconds
        elif self.estimated_duration_seconds <= 0:
            self.estimated_duration_seconds = self.duration_estimate

        return self
