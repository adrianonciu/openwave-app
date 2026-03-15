from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path

from app.models.editorial_preferences import EditorialPreferenceProfile
from app.models.editorial_profile import EditorialProfile
from app.models.story_score import ScoredStoryCluster
from app.models.story_selection import StorySelectionResult
from app.models.user_personalization import UserPersonalization
from app.services.story_scoring_service import StoryScoringService
from app.services.story_selection_service import StorySelectionService

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "editorial_profiles.json"


@dataclass
class EditorialSelectionCoreResult:
    profile: EditorialProfile
    candidate_clusters: list[ScoredStoryCluster]
    selection_result: StorySelectionResult
    debug_metadata: dict[str, object]


class EditorialSelectionCoreService:
    """
    Shared Editorial Core - used by all profiles (national, international, future local).
    Differences must come from EditorialProfile injection.
    Do not add Romania-specific or international-specific logic directly here unless unavoidable.
    """

    def __init__(
        self,
        selection_service: StorySelectionService | None = None,
        scoring_service: StoryScoringService | None = None,
    ) -> None:
        self.selection_service = selection_service or StorySelectionService()
        self.scoring_service = scoring_service or StoryScoringService()
        raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self._profiles = {name: EditorialProfile.model_validate(payload) for name, payload in raw_config.items()}

    def get_profile(self, profile_name: str) -> EditorialProfile:
        if profile_name not in self._profiles:
            available = ", ".join(sorted(self._profiles))
            raise ValueError(f"Unknown editorial profile '{profile_name}'. Available profiles: {available}")
        return self._profiles[profile_name]

    def available_profiles(self) -> list[str]:
        return sorted(self._profiles)

    def dominant_scope(self, scored_cluster: ScoredStoryCluster) -> str:
        scopes = [member.source_scope or ("local" if member.is_local_source else "unknown") for member in scored_cluster.cluster.member_articles]
        return Counter(scopes).most_common(1)[0][0] if scopes else "unknown"

    def run_profile(
        self,
        scored_clusters: list[ScoredStoryCluster],
        profile: str | EditorialProfile,
        max_stories: int | None = None,
        editorial_preferences: EditorialPreferenceProfile | None = None,
        personalization: UserPersonalization | None = None,
    ) -> EditorialSelectionCoreResult:
        resolved_profile = profile if isinstance(profile, EditorialProfile) else self.get_profile(profile)
        candidate_clusters = [
            cluster.model_copy(deep=True)
            for cluster in scored_clusters
            if self._cluster_matches_profile(cluster, resolved_profile)
        ]
        self._annotate_clusters(candidate_clusters, resolved_profile)
        self.scoring_service.apply_editorial_profile_adjustments(candidate_clusters, resolved_profile)
        if resolved_profile.scope == "local":
            candidate_clusters = [
                cluster for cluster in candidate_clusters
                if cluster.local_relevance_boost > 0
            ]
        effective_max_stories = max_stories or int(resolved_profile.diversity_rules.get("max_stories", 5))
        selection_result = self.selection_service.select_stories(
            candidate_clusters,
            max_stories=effective_max_stories,
            editorial_preferences=editorial_preferences,
            personalization=personalization,
        )
        debug_metadata = {
            "editorial_profile_used": resolved_profile.name,
            "profile_config_name": resolved_profile.profile_config_name,
            "shared_core_path_used": True,
            "candidate_count": len(candidate_clusters),
            "selected_count": len(selection_result.selected_clusters),
            "priority_domains": resolved_profile.priority_domains,
            "debug_sections": resolved_profile.debug_sections,
            "candidate_scopes": resolved_profile.effective_candidate_scopes,
        }
        return EditorialSelectionCoreResult(
            profile=resolved_profile,
            candidate_clusters=candidate_clusters,
            selection_result=selection_result,
            debug_metadata=debug_metadata,
        )

    def _cluster_matches_profile(self, cluster: ScoredStoryCluster, profile: EditorialProfile) -> bool:
        dominant_scope = self.dominant_scope(cluster)
        return dominant_scope in profile.effective_candidate_scopes

    def _annotate_clusters(self, candidate_clusters: list[ScoredStoryCluster], profile: EditorialProfile) -> None:
        for cluster in candidate_clusters:
            cluster.editorial_profile_used = profile.name
            cluster.profile_config_name = profile.profile_config_name
            cluster.shared_core_path_used = True
