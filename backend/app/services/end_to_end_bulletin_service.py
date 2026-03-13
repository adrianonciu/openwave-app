from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.models.article_fetch import FetchedArticle
from app.models.user_personalization import EditorialPreferenceProfile, UserPersonalization
from app.models.audio_generation_package import AudioGenerationPackage
from app.models.end_to_end_bulletin_result import (
    EndToEndBulletinResult,
    EndToEndExecutionStats,
    EndToEndPipelineError,
)
from app.models.final_editorial_briefing import FinalEditorialBriefingPackage
from app.services.editorial_pipeline_service import EditorialPipelineService
from app.services.editorial_to_audio_service import EditorialToAudioService
from app.services.tts_service import TtsService


class EndToEndBulletinService:
    def __init__(self) -> None:
        self.editorial_pipeline_service = EditorialPipelineService()
        self.editorial_to_audio_service = EditorialToAudioService()
        self.tts_service = TtsService()

    def run_end_to_end_bulletin_generation(
        self,
        articles: list[FetchedArticle],
        bulletin_id: str | None = None,
        presenter_name: str | None = None,
        personalization: UserPersonalization | None = None,
        editorial_preferences: EditorialPreferenceProfile | None = None,
    ) -> EndToEndBulletinResult:
        created_at = datetime.now(UTC)
        resolved_personalization = UserPersonalization.from_input(
            personalization=personalization,
            editorial_preferences=editorial_preferences,
        )

        try:
            final_editorial_briefing = self.editorial_pipeline_service.run_editorial_pipeline(
                articles,
                personalization=resolved_personalization,
            )
        except Exception as exc:
            return self._error_result(
                stage="editorial_pipeline_failed",
                code="editorial_pipeline_exception",
                message=str(exc),
                input_article_count=len(articles),
                created_at=created_at,
                editorial_preferences=resolved_personalization.editorial_preferences,
                personalization=resolved_personalization,
            )

        effective_bulletin_id = (bulletin_id or final_editorial_briefing.briefing_id).strip()
        if effective_bulletin_id != final_editorial_briefing.briefing_id:
            final_editorial_briefing = self._override_editorial_briefing_id(
                final_editorial_briefing,
                effective_bulletin_id,
            )

        audio_package_result = self.editorial_to_audio_service.prepare_audio_generation_package(
            final_editorial_briefing
        )
        if audio_package_result.status == "error" or audio_package_result.package is None:
            error = audio_package_result.error
            return self._error_result(
                stage="audio_generation_package_failed",
                code=error.code if error else "audio_package_unknown_error",
                message=error.message if error else "Audio generation package preparation failed.",
                input_article_count=len(articles),
                final_editorial_briefing=final_editorial_briefing,
                created_at=created_at,
                editorial_preferences=resolved_personalization.editorial_preferences,
                personalization=resolved_personalization,
            )

        audio_package = audio_package_result.package
        if effective_bulletin_id != audio_package.briefing_id:
            audio_package = self._override_audio_package_id(audio_package, effective_bulletin_id)

        segment_blocks = self.editorial_to_audio_service.to_tts_segment_blocks(audio_package)
        try:
            tts_result = self.tts_service.generate_audio_segments(
                segment_blocks=segment_blocks,
                presenter_name=presenter_name,
                file_stem=effective_bulletin_id,
            )
        except Exception as exc:
            return self._error_result(
                stage="tts_generation_failed",
                code="tts_generation_exception",
                message=str(exc),
                input_article_count=len(articles),
                final_editorial_briefing=final_editorial_briefing,
                audio_generation_package=audio_package,
                created_at=created_at,
                editorial_preferences=resolved_personalization.editorial_preferences,
                personalization=resolved_personalization,
            )

        generated_audio_segments = list(tts_result["segments"])
        generated_audio_paths = [
            str(self.tts_service.generated_audio_directory / Path(segment_url).name)
            for segment_url in generated_audio_segments
        ]
        execution_stats = EndToEndExecutionStats(
            input_article_count=len(articles),
            cluster_count=final_editorial_briefing.intermediate_counts.cluster_count,
            selected_story_count=final_editorial_briefing.intermediate_counts.selected_story_count,
            final_story_count=len(final_editorial_briefing.story_items),
            generated_segment_count=len(generated_audio_segments),
        )
        execution_summary = self._build_execution_summary(
            execution_stats=execution_stats,
            effective_bulletin_id=effective_bulletin_id,
            generated_audio_paths=generated_audio_paths,
        )

        return EndToEndBulletinResult(
            bulletin_id=effective_bulletin_id,
            final_editorial_briefing=final_editorial_briefing,
            audio_generation_package=audio_package,
            generated_audio_segments=generated_audio_segments,
            generated_audio_paths=generated_audio_paths,
            estimated_total_duration_seconds=final_editorial_briefing.estimated_total_duration_seconds,
            execution_summary=execution_summary,
            success=True,
            errors=[],
            execution_stats=execution_stats,
            presenter_name=tts_result.get("presenter_name"),
            personalization=final_editorial_briefing.personalization,
            editorial_preferences=final_editorial_briefing.editorial_preferences,
            personalization_used=final_editorial_briefing.personalization_used,
            listener_profile_used=final_editorial_briefing.listener_profile_used,
            editorial_preferences_used=final_editorial_briefing.editorial_preferences_used,
            personalization_defaults_applied=final_editorial_briefing.personalization_defaults_applied,
            local_editorial_anchor=final_editorial_briefing.local_editorial_anchor,
            local_editorial_anchor_scope=final_editorial_briefing.local_editorial_anchor_scope,
            local_source_region_used=final_editorial_briefing.local_source_region_used,
            local_source_count=final_editorial_briefing.local_source_count,
            local_source_registry_used=final_editorial_briefing.local_source_registry_used,
            personalization_explanation=final_editorial_briefing.personalization_explanation,
            tts_provider=tts_result.get("tts_provider"),
            tts_voice_id=tts_result.get("tts_voice_id"),
            created_at=created_at,
        )

    def _override_editorial_briefing_id(
        self,
        briefing: FinalEditorialBriefingPackage,
        briefing_id: str,
    ) -> FinalEditorialBriefingPackage:
        data = self._dump_model(briefing)
        data["briefing_id"] = briefing_id
        return FinalEditorialBriefingPackage(**data)

    def _override_audio_package_id(
        self,
        package: AudioGenerationPackage,
        briefing_id: str,
    ) -> AudioGenerationPackage:
        data = self._dump_model(package)
        data["briefing_id"] = briefing_id
        return AudioGenerationPackage(**data)

    def _error_result(
        self,
        stage: str,
        code: str,
        message: str,
        input_article_count: int,
        created_at: datetime,
        final_editorial_briefing: FinalEditorialBriefingPackage | None = None,
        audio_generation_package: AudioGenerationPackage | None = None,
        personalization: UserPersonalization | None = None,
        editorial_preferences: EditorialPreferenceProfile | None = None,
    ) -> EndToEndBulletinResult:
        execution_stats = EndToEndExecutionStats(
            input_article_count=input_article_count,
            cluster_count=(
                final_editorial_briefing.intermediate_counts.cluster_count
                if final_editorial_briefing is not None
                else 0
            ),
            selected_story_count=(
                final_editorial_briefing.intermediate_counts.selected_story_count
                if final_editorial_briefing is not None
                else 0
            ),
            final_story_count=(
                len(final_editorial_briefing.story_items)
                if final_editorial_briefing is not None
                else 0
            ),
            generated_segment_count=0,
        )
        return EndToEndBulletinResult(
            bulletin_id=(
                final_editorial_briefing.briefing_id
                if final_editorial_briefing is not None
                else None
            ),
            final_editorial_briefing=final_editorial_briefing,
            audio_generation_package=audio_generation_package,
            generated_audio_segments=[],
            generated_audio_paths=[],
            estimated_total_duration_seconds=(
                final_editorial_briefing.estimated_total_duration_seconds
                if final_editorial_briefing is not None
                else 0
            ),
            execution_summary=f"End-to-end bulletin generation failed at stage '{stage}'.",
            success=False,
            errors=[EndToEndPipelineError(stage=stage, code=code, message=message)],
            execution_stats=execution_stats,
            presenter_name=None,
            personalization=personalization or UserPersonalization.from_input(editorial_preferences=editorial_preferences),
            editorial_preferences=(editorial_preferences or UserPersonalization.from_input(personalization=personalization).editorial_preferences),
            personalization_used=(final_editorial_briefing.personalization_used if final_editorial_briefing is not None else (personalization.personalization_used() if personalization else False)),
            listener_profile_used=(final_editorial_briefing.listener_profile_used if final_editorial_briefing is not None else (personalization.listener_profile_used() if personalization else False)),
            editorial_preferences_used=(final_editorial_briefing.editorial_preferences_used if final_editorial_briefing is not None else ((editorial_preferences is not None) or (personalization.editorial_preferences_used() if personalization else False))),
            personalization_defaults_applied=(final_editorial_briefing.personalization_defaults_applied if final_editorial_briefing is not None else (not personalization.personalization_used() if personalization else True)),
            local_editorial_anchor=(final_editorial_briefing.local_editorial_anchor if final_editorial_briefing is not None else (personalization.local_editorial_anchor() if personalization else None)),
            local_editorial_anchor_scope=(final_editorial_briefing.local_editorial_anchor_scope if final_editorial_briefing is not None else (personalization.local_editorial_anchor_scope() if personalization else 'none')),
            local_source_region_used=(final_editorial_briefing.local_source_region_used if final_editorial_briefing is not None else (personalization.local_editorial_anchor() if personalization and personalization.local_editorial_anchor_scope() == 'region' and personalization.editorial_preferences.geography.local > 0 else None)),
            local_source_count=(final_editorial_briefing.local_source_count if final_editorial_briefing is not None else 0),
            local_source_registry_used=(final_editorial_briefing.local_source_registry_used if final_editorial_briefing is not None else False),
            personalization_explanation=(final_editorial_briefing.personalization_explanation if final_editorial_briefing is not None else ((personalization.explainability()[4]) if personalization else "Pipeline used safe neutral personalization defaults because no explicit personalization payload was provided.")),
            tts_provider=None,
            tts_voice_id=None,
            created_at=created_at,
        )

    def _build_execution_summary(
        self,
        execution_stats: EndToEndExecutionStats,
        effective_bulletin_id: str,
        generated_audio_paths: list[str],
    ) -> str:
        return (
            f"Generated bulletin '{effective_bulletin_id}' from {execution_stats.input_article_count} input articles, "
            f"forming {execution_stats.cluster_count} clusters, selecting {execution_stats.selected_story_count} stories, "
            f"and producing {execution_stats.generated_segment_count} audio segments. "
            f"Output files: {', '.join(generated_audio_paths)}."
        )

    def _dump_model(self, model) -> dict:
        if hasattr(model, "model_dump"):
            return model.model_dump()
        return model.dict()
