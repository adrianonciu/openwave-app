from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from app.models.article_fetch import FetchedArticle
from app.models.user_personalization import UserPersonalization
from app.models.final_editorial_briefing import (
    EditorialPipelineIntermediateCounts,
    FinalEditorialBriefingPackage,
)
from app.services.briefing_assembly_service import BriefingAssemblyService
from app.services.bulletin_sizing_service import BulletinSizingService
from app.services.news_clustering_service import NewsClusteringService
from app.services.story_scoring_service import StoryScoringService
from app.services.story_selection_service import StorySelectionService
from app.services.story_summary_generator_service import StorySummaryGeneratorService
from app.services.source_watcher_service import SourceWatcherService

CONTINUITY_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "bulletin_continuity_state.json"


class EditorialPipelineService:
    def __init__(self) -> None:
        self.clustering_service = NewsClusteringService()
        self.scoring_service = StoryScoringService()
        self.selection_service = StorySelectionService()
        self.summary_generator_service = StorySummaryGeneratorService()
        self.briefing_assembly_service = BriefingAssemblyService()
        self.bulletin_sizing_service = BulletinSizingService()
        self.source_watcher_service = SourceWatcherService()

    def run_editorial_pipeline(
        self,
        articles: list[FetchedArticle],
        max_stories: int | None = None,
        target_duration_seconds: int | None = None,
        tolerance_seconds: int | None = None,
        personalization: UserPersonalization | None = None,
        previous_bulletin_clusters: list[str | dict[str, object]] | None = None,
    ) -> FinalEditorialBriefingPackage:
        created_at = datetime.now(UTC)
        resolved_personalization = UserPersonalization.from_input(personalization=personalization)
        (
            personalization_used,
            listener_profile_used,
            editorial_preferences_used,
            defaults_applied,
            personalization_explanation,
        ) = resolved_personalization.explainability()
        local_editorial_anchor = resolved_personalization.local_editorial_anchor()
        local_editorial_anchor_scope = resolved_personalization.local_editorial_anchor_scope()
        local_source_resolution = self.source_watcher_service.resolve_local_sources_for_personalization(
            resolved_personalization
        )
        continuity_records = self._load_previous_bulletin_clusters(previous_bulletin_clusters)
        story_clusters = self.clustering_service.cluster_articles(articles)
        scored_clusters = self.scoring_service.score_clusters(story_clusters)
        selection_result = self.selection_service.select_stories(
            scored_clusters,
            max_stories=max_stories,
            editorial_preferences=resolved_personalization.editorial_preferences,
            personalization=resolved_personalization,
        )
        self.summary_generator_service.reset_variation_state()
        generated_summaries = [
            self.summary_generator_service.generate_story_summary(
                cluster,
                previous_bulletin_clusters=continuity_records,
            )
            for cluster in selection_result.selected_clusters
        ]
        briefing_draft = self.briefing_assembly_service.assemble_briefing(
            generated_summaries,
            personalization=resolved_personalization,
        )
        sized_briefing = self.bulletin_sizing_service.size_briefing(
            briefing_draft,
            target_duration_seconds=target_duration_seconds,
            tolerance_seconds=tolerance_seconds,
        )
        self._persist_current_bulletin_clusters(sized_briefing.story_items)

        intermediate_counts = EditorialPipelineIntermediateCounts(
            article_count=len(articles),
            cluster_count=len(story_clusters),
            scored_cluster_count=len(scored_clusters),
            selected_story_count=len(selection_result.selected_clusters),
            generated_summary_count=len(generated_summaries),
        )
        pipeline_explanation = self._build_pipeline_explanation(
            intermediate_counts=intermediate_counts,
            trimmed=bool(sized_briefing.stories_removed),
            sized_duration=sized_briefing.estimated_total_duration_seconds,
            target_duration=sized_briefing.target_duration_seconds,
            tolerance=sized_briefing.tolerance_seconds,
            continuity_record_count=len(continuity_records),
            local_source_region_used=local_source_resolution.region_used,
            local_source_count=local_source_resolution.source_count,
            local_source_registry_used=local_source_resolution.local_source_registry_used,
            local_sources_enabled=local_source_resolution.local_sources_enabled,
            local_source_explanation=local_source_resolution.explanation,
        )

        return FinalEditorialBriefingPackage(
            briefing_id=sized_briefing.briefing_id,
            intro_text=sized_briefing.intro_text,
            intro_variant=sized_briefing.intro_variant,
            story_items=sized_briefing.story_items,
            outro_text=sized_briefing.outro_text,
            outro_variant=sized_briefing.outro_variant,
            listener_name_mentions=sized_briefing.listener_name_mentions,
            estimated_total_word_count=sized_briefing.estimated_total_word_count,
            estimated_total_duration_seconds=sized_briefing.estimated_total_duration_seconds,
            target_duration_seconds=sized_briefing.target_duration_seconds,
            tolerance_seconds=sized_briefing.tolerance_seconds,
            original_duration_seconds=sized_briefing.original_duration_seconds,
            intermediate_counts=intermediate_counts,
            personalization=resolved_personalization,
            editorial_preferences=resolved_personalization.editorial_preferences,
            personalization_used=personalization_used,
            listener_profile_used=listener_profile_used,
            editorial_preferences_used=editorial_preferences_used,
            personalization_defaults_applied=defaults_applied,
            local_editorial_anchor=local_editorial_anchor,
            local_editorial_anchor_scope=local_editorial_anchor_scope,
            local_source_region_used=local_source_resolution.region_used,
            local_source_count=local_source_resolution.source_count,
            local_source_registry_used=local_source_resolution.local_source_registry_used,
            local_sources_enabled=local_source_resolution.local_sources_enabled,
            personalization_explanation=personalization_explanation,
            selection_explanation=selection_result.selection_explanation,
            assembly_explanation=briefing_draft.assembly_explanation,
            sizing_explanation=sized_briefing.sizing_explanation,
            sizing_actions=sized_briefing.sizing_actions,
            trimmed=bool(sized_briefing.stories_removed),
            pipeline_explanation=pipeline_explanation,
            created_at=created_at,
        )

    def _load_previous_bulletin_clusters(
        self,
        previous_bulletin_clusters: list[str | dict[str, object]] | None,
    ) -> list[dict[str, object]]:
        if previous_bulletin_clusters is not None:
            return self._normalize_previous_bulletin_clusters(previous_bulletin_clusters)
        if not CONTINUITY_STATE_PATH.exists():
            return []
        try:
            payload = json.loads(CONTINUITY_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return self._normalize_previous_bulletin_clusters(
            payload.get("latest_bulletin_clusters", [])
        )

    def _normalize_previous_bulletin_clusters(
        self,
        previous_bulletin_clusters: list[str | dict[str, object]],
    ) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        seen_cluster_ids: set[str] = set()
        for item in previous_bulletin_clusters:
            if isinstance(item, str):
                cluster_id = item.strip()
                if cluster_id and cluster_id not in seen_cluster_ids:
                    normalized.append({"cluster_id": cluster_id})
                    seen_cluster_ids.add(cluster_id)
                continue
            if not isinstance(item, dict):
                continue
            cluster_id = str(item.get("cluster_id") or "").strip()
            if not cluster_id or cluster_id in seen_cluster_ids:
                continue
            normalized.append(
                {
                    "cluster_id": cluster_id,
                    "score_total": item.get("score_total"),
                    "source_count": item.get("source_count"),
                }
            )
            seen_cluster_ids.add(cluster_id)
        return normalized

    def _persist_current_bulletin_clusters(self, story_items: list) -> None:
        CONTINUITY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(UTC).isoformat(),
            "latest_bulletin_clusters": [
                {
                    "cluster_id": item.story.cluster_id,
                    "score_total": item.story.score_total,
                    "source_count": len(item.story.source_labels),
                }
                for item in story_items
            ],
        }
        CONTINUITY_STATE_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _build_pipeline_explanation(
        self,
        intermediate_counts: EditorialPipelineIntermediateCounts,
        trimmed: bool,
        sized_duration: int,
        target_duration: int,
        tolerance: int,
        continuity_record_count: int,
        local_source_region_used: str | None,
        local_source_count: int,
        local_source_registry_used: bool,
        local_sources_enabled: bool,
        local_source_explanation: str,
    ) -> str:
        lower_bound = max(target_duration - tolerance, 0)
        upper_bound = target_duration + tolerance
        trim_note = "The sized bulletin kept all assembled stories."
        if trimmed:
            trim_note = "The sized bulletin trimmed trailing lower-priority stories to fit the target window."
        continuity_note = (
            f"Loaded {continuity_record_count} cluster record(s) from the previous bulletin to detect story updates."
            if continuity_record_count
            else "No previous bulletin continuity records were available, so all stories were treated as new."
        )
        local_source_note = (
            f"Loaded {local_source_count} county-based local source(s) for region '{local_source_region_used}'. {local_source_explanation}"
            if local_source_registry_used and local_source_region_used and local_sources_enabled
            else local_source_explanation
        )

        return (
            f"Editorial pipeline processed {intermediate_counts.article_count} fetched articles into "
            f"{intermediate_counts.cluster_count} clusters, scored {intermediate_counts.scored_cluster_count} clusters, "
            f"selected {intermediate_counts.selected_story_count} stories, and generated {intermediate_counts.generated_summary_count} summaries. "
            f"Final draft duration is {sized_duration} seconds against a target window of {lower_bound}-{upper_bound} seconds. "
            f"{trim_note} {continuity_note} {local_source_note} Personalization is now a first-class pipeline contract; listener profile and editorial preferences are always resolved explicitly, with safe defaults visible in output explainability."
        )
