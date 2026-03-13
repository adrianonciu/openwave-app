from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable
import json
from pathlib import Path

from app.models.generated_briefing_draft import BriefingStoryItem, GeneratedBriefingDraft
from app.models.sized_briefing_draft import BulletinSizingAction, SizedBriefingDraft

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "bulletin_sizing_config.json"


class BulletinSizingService:
    def __init__(self) -> None:
        raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.default_target_duration_seconds: int = raw_config["target_duration_seconds"]
        self.default_tolerance_seconds: int = raw_config["tolerance_seconds"]
        self.max_story_count: int = raw_config["max_story_count"]
        self.min_story_count: int = raw_config["min_story_count"]
        self.speaking_rate_wpm: int = raw_config["speaking_rate_wpm"]

    def size_briefing(
        self,
        draft: GeneratedBriefingDraft,
        target_duration_seconds: int | None = None,
        tolerance_seconds: int | None = None,
    ) -> SizedBriefingDraft:
        target_duration = target_duration_seconds or self.default_target_duration_seconds
        tolerance = tolerance_seconds or self.default_tolerance_seconds
        original_duration = draft.estimated_total_duration_seconds
        lower_bound = max(target_duration - tolerance, 0)
        upper_bound = target_duration + tolerance
        sized_at = datetime.now(UTC)

        story_items = list(draft.ordered_story_items)
        actions: list[BulletinSizingAction] = []
        removed_story_ids: list[str] = []

        if lower_bound <= original_duration <= upper_bound:
            actions.append(
                BulletinSizingAction(
                    action="kept_unchanged",
                    explanation="Briefing draft was already within the acceptable duration window.",
                )
            )
        elif original_duration < lower_bound:
            actions.append(
                BulletinSizingAction(
                    action="below_target_duration",
                    explanation=(
                        "Briefing draft is shorter than the target window. In v1, the system does not expand or regenerate text automatically."
                    ),
                )
            )
        else:
            story_items, removed_story_ids, trim_actions = self._trim_to_fit(
                story_items=story_items,
                intro_text=draft.intro_text,
                outro_text=draft.outro_text,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
            )
            actions.extend(trim_actions)
            if not trim_actions:
                actions.append(
                    BulletinSizingAction(
                        action="unable_to_reach_target_without_breaking_min_story_count",
                        explanation=(
                            "Briefing remained above the preferred window because removing more stories would have dropped below the minimum story count."
                        ),
                    )
                )

        normalized_story_items = self._renumber_story_items(story_items)
        final_word_count = self._estimate_total_word_count(
            intro_text=draft.intro_text,
            outro_text=draft.outro_text,
            story_items=normalized_story_items,
        )
        final_duration = self._estimate_duration_seconds(final_word_count)
        kept_story_ids = [item.story.cluster_id for item in normalized_story_items]
        explanation = self._build_sizing_explanation(
            original_duration=original_duration,
            final_duration=final_duration,
            target_duration=target_duration,
            tolerance=tolerance,
            removed_story_ids=removed_story_ids,
            kept_story_ids=kept_story_ids,
        )

        return SizedBriefingDraft(
            briefing_id=draft.briefing_id,
            intro_text=draft.intro_text,
            intro_variant=draft.intro_variant,
            story_items=normalized_story_items,
            outro_text=draft.outro_text,
            outro_variant=draft.outro_variant,
            listener_name_mentions=draft.listener_name_mentions,
            estimated_total_word_count=final_word_count,
            estimated_total_duration_seconds=final_duration,
            target_duration_seconds=target_duration,
            tolerance_seconds=tolerance,
            original_duration_seconds=original_duration,
            sizing_actions=actions,
            stories_removed=removed_story_ids,
            stories_kept=kept_story_ids,
            sizing_explanation=explanation,
            sized_at=sized_at,
        )

    def _trim_to_fit(
        self,
        story_items: list[BriefingStoryItem],
        intro_text: str,
        outro_text: str,
        lower_bound: int,
        upper_bound: int,
    ) -> tuple[list[BriefingStoryItem], list[str], list[BulletinSizingAction]]:
        working_items = list(story_items)
        removed_story_ids: list[str] = []
        actions: list[BulletinSizingAction] = []

        while len(working_items) > self.min_story_count:
            current_duration = self._estimate_duration_seconds(
                self._estimate_total_word_count(
                    intro_text=intro_text,
                    outro_text=outro_text,
                    story_items=working_items,
                )
            )
            if current_duration <= upper_bound:
                break

            removed_item = working_items.pop()
            removed_story_ids.append(removed_item.story.cluster_id)
            actions.append(
                BulletinSizingAction(
                    action="removed_lowest_priority_tail_story",
                    story_cluster_ids=[removed_item.story.cluster_id],
                    explanation=(
                        f"Removed trailing story '{removed_item.story.cluster_id}' to reduce bulletin duration while preserving earlier, stronger stories."
                    ),
                )
            )

        final_duration = self._estimate_duration_seconds(
            self._estimate_total_word_count(
                intro_text=intro_text,
                outro_text=outro_text,
                story_items=working_items,
            )
        )
        if lower_bound <= final_duration <= upper_bound:
            actions.append(
                BulletinSizingAction(
                    action="within_target_after_trimming",
                    explanation="Bulletin duration moved into the acceptable target window after trimming low-priority tail stories.",
                )
            )

        return working_items, removed_story_ids, actions

    def _renumber_story_items(self, story_items: list[BriefingStoryItem]) -> list[BriefingStoryItem]:
        return [
            BriefingStoryItem(
                position=index,
                story=item.story,
                perspective_segments=item.perspective_segments,
                presenter_voice=item.presenter_voice,
                pass_phrase_used=item.pass_phrase_used,
                pacing_label=item.pacing_label,
                ordering_reason=item.ordering_reason,
            )
            for index, item in enumerate(story_items, start=1)
        ]

    def _estimate_total_word_count(
        self,
        intro_text: str,
        outro_text: str,
        story_items: Iterable[BriefingStoryItem],
    ) -> int:
        story_items = list(story_items)
        story_words = sum(item.story.word_count for item in story_items)
        pass_words = sum(len((item.pass_phrase_used or "").split()) for item in story_items)
        perspective_words = sum(
            len(segment.narration_text.split())
            for item in story_items
            for segment in item.perspective_segments
        )
        return story_words + pass_words + perspective_words + len(intro_text.split()) + len(outro_text.split())

    def _estimate_duration_seconds(self, total_word_count: int) -> int:
        return round((total_word_count / self.speaking_rate_wpm) * 60)

    def _build_sizing_explanation(
        self,
        original_duration: int,
        final_duration: int,
        target_duration: int,
        tolerance: int,
        removed_story_ids: list[str],
        kept_story_ids: list[str],
    ) -> str:
        lower_bound = max(target_duration - tolerance, 0)
        upper_bound = target_duration + tolerance
        if lower_bound <= final_duration <= upper_bound and not removed_story_ids:
            return (
                f"Briefing was already within the target window of {lower_bound}-{upper_bound} seconds and was kept unchanged."
            )
        if lower_bound <= final_duration <= upper_bound and removed_story_ids:
            return (
                f"Bulletin exceeded the target duration. Removed {len(removed_story_ids)} trailing lower-priority stories to reach the acceptable range."
            )
        if final_duration < lower_bound:
            return (
                f"Briefing remains below the target window at {final_duration} seconds. In v1, the system reports the shortfall without expanding story text."
            )
        return (
            f"Briefing still sits outside the target window after sizing. Kept stories: {len(kept_story_ids)}, removed stories: {len(removed_story_ids)}."
        )
