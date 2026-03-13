from __future__ import annotations

from datetime import UTC, datetime

from app.models.audio_generation_package import (
    AudioGenerationPackage,
    AudioGenerationPackageError,
    AudioGenerationPreparationResult,
    AudioStorySegment,
)
from app.models.final_editorial_briefing import FinalEditorialBriefingPackage


class EditorialToAudioService:
    def prepare_audio_generation_package(
        self,
        briefing: FinalEditorialBriefingPackage,
    ) -> AudioGenerationPreparationResult:
        intro_text = briefing.intro_text.strip()
        if not intro_text:
            return self._error(
                code="missing_intro_text",
                message="Final editorial briefing package is missing intro_text.",
            )

        story_segments = [
            AudioStorySegment(
                segment_id=f"story_{index:02d}",
                story_text=item.story.summary_text.strip(),
                topic_label=item.story.topic_label,
                source_labels=item.story.source_labels,
            )
            for index, item in enumerate(briefing.story_items, start=1)
            if item.story.summary_text.strip()
        ]
        if not story_segments:
            return self._error(
                code="missing_story_segments",
                message="Final editorial briefing package does not contain at least one usable story segment.",
            )

        outro_text = briefing.outro_text.strip()
        if not outro_text:
            return self._error(
                code="missing_outro_text",
                message="Final editorial briefing package is missing outro_text.",
            )

        package = AudioGenerationPackage(
            briefing_id=briefing.briefing_id,
            intro_text=intro_text,
            story_segments=story_segments,
            outro_text=outro_text,
            segment_count=len(story_segments) + 2,
            estimated_duration_seconds=briefing.estimated_total_duration_seconds,
            created_at=datetime.now(UTC),
        )
        return AudioGenerationPreparationResult(
            status="success",
            package=package,
        )

    def to_tts_segment_blocks(
        self,
        package: AudioGenerationPackage,
    ) -> list[dict[str, str]]:
        segment_blocks = [{"segment_name": "intro", "text": package.intro_text}]
        segment_blocks.extend(
            {
                "segment_name": story.segment_id,
                "text": story.story_text,
            }
            for story in package.story_segments
        )
        segment_blocks.append({"segment_name": "outro", "text": package.outro_text})
        return segment_blocks

    def _error(self, code: str, message: str) -> AudioGenerationPreparationResult:
        return AudioGenerationPreparationResult(
            status="error",
            error=AudioGenerationPackageError(code=code, message=message),
        )
