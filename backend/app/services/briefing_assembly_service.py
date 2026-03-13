from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from app.models.generated_briefing_draft import BriefingStoryItem, GeneratedBriefingDraft
from app.models.generated_story_summary import GeneratedStorySummary

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "briefing_assembly_config.json"


class BriefingAssemblyService:
    def __init__(self) -> None:
        raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.spoken_words_per_minute: int = raw_config["spoken_words_per_minute"]
        self.intro_text: str = raw_config["intro_text"]
        self.outro_text: str = raw_config["outro_text"]
        self.lighter_topics: list[str] = raw_config["lighter_topics"]
        self.heavier_topics: list[str] = raw_config["heavier_topics"]
        self.medium_topics: list[str] = raw_config.get("medium_topics", [])
        self.similarity_soft_groups: dict[str, list[str]] = raw_config["similarity_soft_groups"]
        self.max_consecutive_heavy: int = raw_config.get("max_consecutive_heavy", 2)
        self.too_short_seconds: int = raw_config["too_short_seconds"]
        self.too_long_seconds: int = raw_config["too_long_seconds"]

    def assemble_briefing(
        self,
        stories: list[GeneratedStorySummary],
    ) -> GeneratedBriefingDraft:
        assembled_at = datetime.now(UTC)
        ordered_stories = self._order_stories(stories)
        ordered_items = [
            BriefingStoryItem(
                position=index,
                story=story,
                pacing_label=self._pacing_label(story),
                ordering_reason=reason,
            )
            for index, (story, reason) in enumerate(ordered_stories, start=1)
        ]
        estimated_total_word_count = self._estimate_total_word_count(ordered_items)
        estimated_total_duration_seconds = round(
            (estimated_total_word_count / self.spoken_words_per_minute) * 60
        )
        briefing_id = self._build_briefing_id(ordered_items, assembled_at)
        assembly_explanation = self._build_assembly_explanation(
            ordered_items,
            estimated_total_duration_seconds,
        )

        return GeneratedBriefingDraft(
            briefing_id=briefing_id,
            intro_text=self.intro_text,
            ordered_story_items=ordered_items,
            outro_text=self.outro_text,
            estimated_total_word_count=estimated_total_word_count,
            estimated_total_duration_seconds=estimated_total_duration_seconds,
            assembly_explanation=assembly_explanation,
            assembled_at=assembled_at,
        )

    def _order_stories(
        self,
        stories: list[GeneratedStorySummary],
    ) -> list[tuple[GeneratedStorySummary, str]]:
        remaining = sorted(stories, key=self._story_rank_key)
        ordered: list[tuple[GeneratedStorySummary, str]] = []

        if not remaining:
            return ordered

        opener = remaining.pop(0)
        ordered.append((opener, "opened_bulletin_as_strongest_available_story"))

        while remaining:
            next_story = self._pick_next_story(ordered, remaining)
            remaining.remove(next_story)
            ordered.append((next_story, self._ordering_reason(ordered, next_story, len(ordered) + 1)))

        if len(ordered) >= 2 and self._pacing_label(ordered[-1][0]) == "heavy":
            lighter_candidate = self._last_lighter_story_index(ordered)
            if lighter_candidate is not None and lighter_candidate != len(ordered) - 1:
                ordered[lighter_candidate], ordered[-1] = ordered[-1], ordered[lighter_candidate]
                final_story = ordered[-1][0]
                ordered[-1] = (final_story, "moved_to_close_bulletin_with_more_breathable_finish")

        return ordered

    def _pick_next_story(
        self,
        ordered: list[tuple[GeneratedStorySummary, str]],
        remaining: list[GeneratedStorySummary],
    ) -> GeneratedStorySummary:
        previous_story = ordered[-1][0]

        def candidate_key(story: GeneratedStorySummary) -> tuple[float, float, float, str]:
            similarity_penalty = 1.0 if self._same_soft_group(previous_story, story) else 0.0
            same_topic_penalty = 1.0 if previous_story.topic_label == story.topic_label else 0.0
            pacing_penalty = self._pacing_penalty(ordered, story)
            score_value = -(story.score_total or 0.0)
            return (pacing_penalty, similarity_penalty, same_topic_penalty, score_value)

        return min(remaining, key=candidate_key)

    def _pacing_penalty(
        self,
        ordered: list[tuple[GeneratedStorySummary, str]],
        story: GeneratedStorySummary,
    ) -> float:
        label = self._pacing_label(story)
        if label != "heavy":
            return 0.0
        recent_labels = [self._pacing_label(item[0]) for item in ordered[-self.max_consecutive_heavy :]]
        if recent_labels and all(recent == "heavy" for recent in recent_labels):
            return 2.0
        if recent_labels and recent_labels[-1] == "heavy":
            return 0.75
        return 0.0

    def _ordering_reason(
        self,
        ordered: list[tuple[GeneratedStorySummary, str]],
        current_story: GeneratedStorySummary,
        position: int,
    ) -> str:
        if position == 1:
            return "opened_bulletin_as_strongest_available_story"
        previous_story = ordered[-1][0]
        if self._pacing_penalty(ordered, current_story) == 0 and self._pacing_label(previous_story) == "heavy":
            return "placed_here_to_relieve_bulletin_pacing_after_a_heavier_story"
        if not self._same_soft_group(previous_story, current_story):
            return "placed_here_to_improve_topic_flow_and_reduce_back_to_back_similarity"
        if previous_story.topic_label != current_story.topic_label:
            return "placed_here_as_next_best_story_with_related_but_not_identical_weight"
        return "placed_here_by_remaining_priority_after_flow_checks"

    def _pacing_label(self, story: GeneratedStorySummary) -> str:
        if story.casualty_line_included or story.lead_type == "impact" or story.topic_label in self.heavier_topics:
            return "heavy"
        if story.topic_label in self.lighter_topics:
            return "light"
        if story.topic_label in self.medium_topics:
            return "medium"
        if (story.score_total or 0.0) >= 70:
            return "heavy"
        if (story.score_total or 0.0) <= 35:
            return "light"
        return "medium"

    def _same_soft_group(
        self,
        left: GeneratedStorySummary,
        right: GeneratedStorySummary,
    ) -> bool:
        for topics in self.similarity_soft_groups.values():
            if left.topic_label in topics and right.topic_label in topics:
                return True
        return False

    def _last_lighter_story_index(
        self,
        ordered: list[tuple[GeneratedStorySummary, str]],
    ) -> int | None:
        for index in range(len(ordered) - 1, -1, -1):
            if self._pacing_label(ordered[index][0]) == "light":
                return index
        return None

    def _story_rank_key(self, story: GeneratedStorySummary) -> tuple[float, int, str]:
        return (
            -(story.score_total or 0.0),
            0 if self._pacing_label(story) == "heavy" else 1,
            story.cluster_id,
        )

    def _estimate_total_word_count(self, ordered_items: list[BriefingStoryItem]) -> int:
        story_words = sum(item.story.word_count for item in ordered_items)
        intro_words = len(self.intro_text.split())
        outro_words = len(self.outro_text.split())
        return story_words + intro_words + outro_words

    def _build_briefing_id(
        self,
        ordered_items: list[BriefingStoryItem],
        assembled_at: datetime,
    ) -> str:
        seed = "|".join(item.story.cluster_id for item in ordered_items) + assembled_at.isoformat()
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
        return f"briefing-{digest}"

    def _build_assembly_explanation(
        self,
        ordered_items: list[BriefingStoryItem],
        estimated_total_duration_seconds: int,
    ) -> str:
        if not ordered_items:
            return "Briefing draft is empty because no story summaries were provided."

        opener = ordered_items[0].story.representative_title or ordered_items[0].story.cluster_id
        duration_note = "within a usable draft range"
        if estimated_total_duration_seconds < self.too_short_seconds:
            duration_note = "shorter than a typical briefing candidate"
        elif estimated_total_duration_seconds > self.too_long_seconds:
            duration_note = "longer than a typical briefing candidate"

        pacing_trace = ", ".join(item.pacing_label for item in ordered_items)
        return (
            f"Bulletin opens with '{opener}' as the strongest available item, then keeps score as the primary ordering rule while trying to avoid long heavy-heavy-heavy runs when lighter alternatives exist. "
            f"Pacing labels across the bulletin are: {pacing_trace}. Estimated total duration is {estimated_total_duration_seconds} seconds, which is {duration_note}."
        )
