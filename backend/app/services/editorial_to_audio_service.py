from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from app.models.audio_generation_package import (
    AudioGenerationPackage,
    AudioGenerationPackageError,
    AudioGenerationPreparationResult,
    AudioSegmentBlock,
    AudioStorySegment,
)
from app.models.final_editorial_briefing import FinalEditorialBriefingPackage

STINGER_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "audio_stingers_config.json"


class EditorialToAudioService:
    def __init__(self) -> None:
        raw_config = json.loads(STINGER_CONFIG_PATH.read_text(encoding="utf-8"))
        self.stingers_enabled: bool = raw_config.get("enabled", False)
        self.stinger_files: list[str] = raw_config.get("stinger_files", [])
        self.max_stingers_per_bulletin: int = raw_config.get("max_stingers_per_bulletin", 8)

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

        ordered_segments = self._build_ordered_segments(
            briefing_id=briefing.briefing_id,
            intro_text=intro_text,
            story_segments=story_segments,
            outro_text=outro_text,
        )

        package = AudioGenerationPackage(
            briefing_id=briefing.briefing_id,
            intro_text=intro_text,
            story_segments=story_segments,
            ordered_segments=ordered_segments,
            outro_text=outro_text,
            segment_count=len(ordered_segments),
            estimated_duration_seconds=briefing.estimated_total_duration_seconds,
            created_at=datetime.now(UTC),
        )
        return AudioGenerationPreparationResult(
            status="success",
            package=package,
        )

    def _build_ordered_segments(
        self,
        briefing_id: str,
        intro_text: str,
        story_segments: list[AudioStorySegment],
        outro_text: str,
    ) -> list[AudioSegmentBlock]:
        ordered_segments: list[AudioSegmentBlock] = [
            AudioSegmentBlock(
                segment_name="intro",
                segment_type="intro",
                text=intro_text,
            )
        ]

        stinger_count = 0
        previous_stinger_file: str | None = None
        for index, story in enumerate(story_segments, start=1):
            ordered_segments.append(
                AudioSegmentBlock(
                    segment_name=story.segment_id,
                    segment_type="story",
                    text=story.story_text,
                    topic_label=story.topic_label,
                    source_labels=story.source_labels,
                )
            )
            is_last_story = index == len(story_segments)
            if is_last_story:
                continue
            if not self._should_insert_stinger(story_segments, stinger_count):
                continue
            stinger_file = self._select_stinger_file(
                briefing_id=briefing_id,
                stinger_index=stinger_count,
                previous_stinger_file=previous_stinger_file,
            )
            if not stinger_file:
                continue
            stinger_count += 1
            previous_stinger_file = stinger_file
            ordered_segments.append(
                AudioSegmentBlock(
                    segment_name=f"stinger_{stinger_count:02d}",
                    segment_type="stinger",
                    audio_file=stinger_file,
                )
            )

        ordered_segments.append(
            AudioSegmentBlock(
                segment_name="outro",
                segment_type="outro",
                text=outro_text,
            )
        )
        return ordered_segments

    def _should_insert_stinger(
        self,
        story_segments: list[AudioStorySegment],
        stinger_count: int,
    ) -> bool:
        if not self.stingers_enabled:
            return False
        if len(story_segments) < 2:
            return False
        if not self.stinger_files:
            return False
        return stinger_count < self.max_stingers_per_bulletin

    def _select_stinger_file(
        self,
        briefing_id: str,
        stinger_index: int,
        previous_stinger_file: str | None,
    ) -> str | None:
        if not self.stinger_files:
            return None
        start_index = (sum(ord(char) for char in briefing_id) + stinger_index) % len(self.stinger_files)
        rotated = self.stinger_files[start_index:] + self.stinger_files[:start_index]
        for candidate in rotated:
            if candidate != previous_stinger_file:
                return candidate
        return rotated[0]

    def to_tts_segment_blocks(
        self,
        package: AudioGenerationPackage,
    ) -> list[dict[str, str]]:
        return [
            {
                "segment_name": segment.segment_name,
                "text": segment.text or "",
            }
            for segment in package.ordered_segments
            if segment.segment_type != "stinger" and segment.text
        ]

    def to_audio_segment_sequence(
        self,
        package: AudioGenerationPackage,
    ) -> list[dict[str, str]]:
        sequence: list[dict[str, str]] = []
        for segment in package.ordered_segments:
            entry = {
                "segment_name": segment.segment_name,
                "segment_type": segment.segment_type,
            }
            if segment.text:
                entry["text"] = segment.text
            if segment.audio_file:
                entry["audio_file"] = segment.audio_file
            sequence.append(entry)
        return sequence

    def _error(self, code: str, message: str) -> AudioGenerationPreparationResult:
        return AudioGenerationPreparationResult(
            status="error",
            error=AudioGenerationPackageError(code=code, message=message),
        )
