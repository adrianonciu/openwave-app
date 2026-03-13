from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path

from app.models.editorial_preferences import EditorialPreferenceProfile
from app.models.story_score import ScoredStoryCluster
from app.models.story_selection import (
    StorySelectionDecision,
    StorySelectionResult,
    StorySelectionStats,
)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "story_selection_config.json"


class StorySelectionService:
    def __init__(self) -> None:
        raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.default_max_stories: int = raw_config["default_max_stories"]
        self.minimum_score_threshold: float = raw_config["minimum_score_threshold"]
        self.max_source_repeat: int = raw_config["max_source_repeat"]
        self.max_topic_repeat: int = raw_config["max_topic_repeat"]
        self.diversity_score_tolerance: float = raw_config["diversity_score_tolerance"]
        self.commentary_like_title_penalty_trigger: float = raw_config[
            "commentary_like_title_penalty_trigger"
        ]
        self.commentary_like_title_terms: list[str] = raw_config[
            "commentary_like_title_terms"
        ]
        self.topic_labels: dict[str, list[str]] = raw_config["topic_labels"]
        self.domain_labels: dict[str, list[str]] = raw_config["domain_labels"]
        self.geography_labels: dict[str, list[str]] = raw_config["geography_labels"]
        self.preference_near_tie_tolerance: float = raw_config.get(
            "preference_near_tie_tolerance",
            self.diversity_score_tolerance,
        )
        self.preference_influence_strength: float = raw_config.get(
            "preference_influence_strength",
            0.35,
        )
        self.max_preference_adjustment_per_story: float = raw_config.get(
            "max_preference_adjustment_per_story",
            2.5,
        )

    def select_stories(
        self,
        scored_clusters: list[ScoredStoryCluster],
        max_stories: int | None = None,
        editorial_preferences: EditorialPreferenceProfile | None = None,
    ) -> StorySelectionResult:
        effective_max_stories = max_stories or self.default_max_stories
        selected_at = datetime.now(UTC)
        ordered_clusters = sorted(
            scored_clusters,
            key=lambda cluster: cluster.score_total,
            reverse=True,
        )

        selected: list[ScoredStoryCluster] = []
        rejected: list[ScoredStoryCluster] = []
        decisions: list[StorySelectionDecision] = []
        source_counter: Counter[str] = Counter()
        topic_counter: Counter[str] = Counter()
        domain_counter: Counter[str] = Counter()
        geography_counter: Counter[str] = Counter()
        top_score = ordered_clusters[0].score_total if ordered_clusters else 0.0

        for cluster in ordered_clusters:
            topic_label = self._infer_topic(cluster)
            domain_label = self._infer_domain(cluster)
            geography_label = self._infer_geography(cluster)
            source_labels = self._source_labels(cluster)
            preference_summary = self._preference_summary(
                cluster=cluster,
                selected=selected,
                domain_counter=domain_counter,
                geography_counter=geography_counter,
                editorial_preferences=editorial_preferences,
                top_score=top_score,
            )

            base_rejection = self._base_rejection_reason(cluster)
            if base_rejection is not None:
                rejected.append(cluster)
                decisions.append(
                    self._build_decision(
                        cluster=cluster,
                        status="rejected",
                        reason=base_rejection,
                        topic_label=topic_label,
                        domain_label=domain_label,
                        geography_label=geography_label,
                        source_labels=source_labels,
                        preference_influence_used=False,
                        preference_influence_summary=preference_summary,
                    )
                )
                continue

            diversity_rejection = self._diversity_rejection_reason(
                cluster=cluster,
                topic_label=topic_label,
                source_labels=source_labels,
                selected=selected,
                source_counter=source_counter,
                topic_counter=topic_counter,
            )
            if diversity_rejection is not None:
                rejected.append(cluster)
                decisions.append(
                    self._build_decision(
                        cluster=cluster,
                        status="rejected",
                        reason=diversity_rejection,
                        topic_label=topic_label,
                        domain_label=domain_label,
                        geography_label=geography_label,
                        source_labels=source_labels,
                        preference_influence_used=False,
                        preference_influence_summary=preference_summary,
                    )
                )
                continue

            preferred, displacement_reason = self._preference_displacement_reason(
                cluster=cluster,
                selected=selected,
                domain_counter=domain_counter,
                geography_counter=geography_counter,
                editorial_preferences=editorial_preferences,
                max_stories=effective_max_stories,
            )
            if preferred and displacement_reason is not None:
                displaced_cluster = selected.pop()
                displaced_topic = self._infer_topic(displaced_cluster)
                displaced_domain = self._infer_domain(displaced_cluster)
                displaced_geography = self._infer_geography(displaced_cluster)
                displaced_sources = self._source_labels(displaced_cluster)
                self._decrement_mix_counters(
                    domain_counter,
                    geography_counter,
                    source_counter,
                    topic_counter,
                    displaced_domain,
                    displaced_geography,
                    displaced_sources,
                    displaced_topic,
                )
                rejected.append(displaced_cluster)
                decisions.append(
                    self._build_decision(
                        cluster=displaced_cluster,
                        status="rejected",
                        reason="rejected_by_editorial_preferences_soft_target",
                        topic_label=displaced_topic,
                        domain_label=displaced_domain,
                        geography_label=displaced_geography,
                        source_labels=displaced_sources,
                        preference_influence_used=True,
                        preference_influence_summary=displacement_reason,
                    )
                )

            if len(selected) >= effective_max_stories:
                rejected.append(cluster)
                decisions.append(
                    self._build_decision(
                        cluster=cluster,
                        status="rejected",
                        reason="selection_limit_reached",
                        topic_label=topic_label,
                        domain_label=domain_label,
                        geography_label=geography_label,
                        source_labels=source_labels,
                        preference_influence_used=False,
                        preference_influence_summary=preference_summary,
                    )
                )
                continue

            selected.append(cluster)
            for source_label in source_labels:
                source_counter[source_label] += 1
            topic_counter[topic_label] += 1
            domain_counter[domain_label] += 1
            geography_counter[geography_label] += 1
            decisions.append(
                self._build_decision(
                    cluster=cluster,
                    status="selected",
                    reason="selected_for_candidate_set",
                    topic_label=topic_label,
                    domain_label=domain_label,
                    geography_label=geography_label,
                    source_labels=source_labels,
                    preference_influence_used=preferred,
                    preference_influence_summary=preference_summary if preferred else None,
                )
            )

        selected = sorted(selected, key=lambda cluster: cluster.score_total, reverse=True)
        stats = StorySelectionStats(
            total_input_clusters=len(scored_clusters),
            selected_count=len(selected),
            rejected_count=len(rejected),
            max_stories=effective_max_stories,
            minimum_score_threshold=self.minimum_score_threshold,
        )
        explanation = self._build_selection_explanation(
            selected,
            rejected,
            stats,
            editorial_preferences,
        )
        return StorySelectionResult(
            selected_clusters=selected,
            rejected_clusters=rejected,
            decisions=decisions,
            selection_explanation=explanation,
            selection_stats=stats,
            selected_at=selected_at,
        )

    def _base_rejection_reason(
        self,
        cluster: ScoredStoryCluster,
    ) -> str | None:
        if cluster.score_total < self.minimum_score_threshold:
            return "below_minimum_score_threshold"

        if self._is_commentary_like(cluster) and cluster.score_total < self.commentary_like_title_penalty_trigger:
            return "commentary_like_cluster_below_editorial_bar"

        return None

    def _diversity_rejection_reason(
        self,
        cluster: ScoredStoryCluster,
        topic_label: str,
        source_labels: list[str],
        selected: list[ScoredStoryCluster],
        source_counter: Counter[str],
        topic_counter: Counter[str],
    ) -> str | None:
        top_selected_score = selected[0].score_total if selected else cluster.score_total
        score_gap = max(top_selected_score - cluster.score_total, 0.0)

        if topic_counter[topic_label] >= self.max_topic_repeat and score_gap <= self.diversity_score_tolerance:
            return "rejected_by_topic_diversity_soft_cap"

        if source_labels and all(source_counter[label] >= self.max_source_repeat for label in source_labels) and score_gap <= self.diversity_score_tolerance:
            return "rejected_by_source_diversity_soft_cap"

        return None

    def _preference_displacement_reason(
        self,
        cluster: ScoredStoryCluster,
        selected: list[ScoredStoryCluster],
        domain_counter: Counter[str],
        geography_counter: Counter[str],
        editorial_preferences: EditorialPreferenceProfile | None,
        max_stories: int,
    ) -> tuple[bool, str | None]:
        if editorial_preferences is None or not selected:
            return False, None
        if len(selected) < max_stories:
            return self._preference_match_score(
                cluster,
                domain_counter,
                geography_counter,
                editorial_preferences,
            ) > 0, self._preference_summary(
                cluster,
                selected,
                domain_counter,
                geography_counter,
                editorial_preferences,
                top_score=selected[0].score_total if selected else cluster.score_total,
            )

        lowest_selected = min(selected, key=lambda item: item.score_total)
        score_gap = lowest_selected.score_total - cluster.score_total
        if score_gap < 0 or score_gap > self.preference_near_tie_tolerance:
            return False, None

        candidate_score = self._preference_match_score(
            cluster,
            domain_counter,
            geography_counter,
            editorial_preferences,
        )
        baseline_domain_counter = Counter(domain_counter)
        baseline_geography_counter = Counter(geography_counter)
        baseline_domain_counter[self._infer_domain(lowest_selected)] -= 1
        baseline_geography_counter[self._infer_geography(lowest_selected)] -= 1
        displaced_score = self._preference_match_score(
            lowest_selected,
            baseline_domain_counter,
            baseline_geography_counter,
            editorial_preferences,
        )
        if candidate_score <= displaced_score:
            return False, None

        summary = (
            f"Editorial preferences favored this near-tie because it improves the requested mix for "
            f"geography '{self._infer_geography(cluster)}' and domain '{self._infer_domain(cluster)}' more than "
            f"the displaced cluster."
        )
        return True, summary

    def _preference_match_score(
        self,
        cluster: ScoredStoryCluster,
        domain_counter: Counter[str],
        geography_counter: Counter[str],
        editorial_preferences: EditorialPreferenceProfile,
    ) -> float:
        domain_label = self._infer_domain(cluster)
        geography_label = self._infer_geography(cluster)
        domain_weight = getattr(editorial_preferences.domains, domain_label, 0.0)
        geography_weight = getattr(editorial_preferences.geography, geography_label, 0.0)
        domain_penalty = domain_counter[domain_label] * self.preference_influence_strength
        geography_penalty = geography_counter[geography_label] * self.preference_influence_strength
        raw_score = (domain_weight + geography_weight) - (domain_penalty + geography_penalty)
        return max(min(raw_score, self.max_preference_adjustment_per_story), 0.0)

    def _preference_summary(
        self,
        cluster: ScoredStoryCluster,
        selected: list[ScoredStoryCluster],
        domain_counter: Counter[str],
        geography_counter: Counter[str],
        editorial_preferences: EditorialPreferenceProfile | None,
        top_score: float,
    ) -> str | None:
        if editorial_preferences is None:
            return None
        score_gap = max(top_score - cluster.score_total, 0.0)
        if score_gap > self.preference_near_tie_tolerance:
            return None
        domain_label = self._infer_domain(cluster)
        geography_label = self._infer_geography(cluster)
        domain_weight = getattr(editorial_preferences.domains, domain_label, 0.0)
        geography_weight = getattr(editorial_preferences.geography, geography_label, 0.0)
        if domain_weight <= 0 and geography_weight <= 0:
            return None
        return (
            f"Near-tie preference signal: domain '{domain_label}' weight={domain_weight}, "
            f"geography '{geography_label}' weight={geography_weight}, current_domain_count={domain_counter[domain_label]}, "
            f"current_geography_count={geography_counter[geography_label]}."
        )

    def _decrement_mix_counters(
        self,
        domain_counter: Counter[str],
        geography_counter: Counter[str],
        source_counter: Counter[str],
        topic_counter: Counter[str],
        domain_label: str,
        geography_label: str,
        source_labels: list[str],
        topic_label: str,
    ) -> None:
        domain_counter[domain_label] -= 1
        geography_counter[geography_label] -= 1
        topic_counter[topic_label] -= 1
        for source_label in source_labels:
            source_counter[source_label] -= 1

    def _infer_topic(self, cluster: ScoredStoryCluster) -> str:
        text = self._cluster_text(cluster)
        best_topic = "general"
        best_matches = 0
        for topic, keywords in self.topic_labels.items():
            if topic == "general":
                continue
            matches = sum(1 for keyword in keywords if keyword.lower() in text)
            if matches > best_matches:
                best_matches = matches
                best_topic = topic
        return best_topic

    def _infer_domain(self, cluster: ScoredStoryCluster) -> str:
        text = self._cluster_text(cluster)
        best_domain = "general"
        best_matches = 0
        for domain, keywords in self.domain_labels.items():
            if domain == "general":
                continue
            matches = sum(1 for keyword in keywords if keyword.lower() in text)
            if matches > best_matches:
                best_matches = matches
                best_domain = domain
        inferred_topic = self._infer_topic(cluster)
        if best_domain == "general" and inferred_topic in {"politics", "economy", "sport"}:
            return inferred_topic
        return best_domain

    def _infer_geography(self, cluster: ScoredStoryCluster) -> str:
        text = self._cluster_text(cluster)
        best_label = "international"
        best_matches = 0
        for geography, keywords in self.geography_labels.items():
            matches = sum(1 for keyword in keywords if keyword.lower() in text)
            if matches > best_matches:
                best_matches = matches
                best_label = geography
        return best_label

    def _source_labels(self, cluster: ScoredStoryCluster) -> list[str]:
        return sorted({member.source for member in cluster.cluster.member_articles})

    def _cluster_text(self, cluster: ScoredStoryCluster) -> str:
        titles = " ".join(member.title for member in cluster.cluster.member_articles)
        return f"{cluster.cluster.representative_title} {titles}".lower()

    def _is_commentary_like(self, cluster: ScoredStoryCluster) -> bool:
        title = cluster.cluster.representative_title.lower()
        return any(term in title for term in self.commentary_like_title_terms)

    def _build_decision(
        self,
        cluster: ScoredStoryCluster,
        status: str,
        reason: str,
        topic_label: str,
        domain_label: str,
        geography_label: str,
        source_labels: list[str],
        preference_influence_used: bool,
        preference_influence_summary: str | None,
    ) -> StorySelectionDecision:
        explanation = self._decision_explanation(
            cluster=cluster,
            status=status,
            reason=reason,
            topic_label=topic_label,
            domain_label=domain_label,
            geography_label=geography_label,
            source_labels=source_labels,
            preference_influence_used=preference_influence_used,
            preference_influence_summary=preference_influence_summary,
        )
        return StorySelectionDecision(
            cluster_id=cluster.cluster.cluster_id,
            status=status,
            reason=reason,
            score_total=cluster.score_total,
            topic_label=topic_label,
            domain_label=domain_label,
            geography_label=geography_label,
            source_labels=source_labels,
            preference_influence_used=preference_influence_used,
            preference_influence_summary=preference_influence_summary,
            explanation=explanation,
        )

    def _decision_explanation(
        self,
        cluster: ScoredStoryCluster,
        status: str,
        reason: str,
        topic_label: str,
        domain_label: str,
        geography_label: str,
        source_labels: list[str],
        preference_influence_used: bool,
        preference_influence_summary: str | None,
    ) -> str:
        title = cluster.cluster.representative_title
        sources = ", ".join(source_labels) or "unknown source"
        preference_clause = ""
        if preference_influence_used and preference_influence_summary:
            preference_clause = f" Preference influence: {preference_influence_summary}"

        if status == "selected":
            return (
                f"Selected '{title}' because it cleared the score threshold with {cluster.score_total} points "
                f"and fit the current mix for topic '{topic_label}', domain '{domain_label}', geography '{geography_label}' across sources {sources}."
                f"{preference_clause}"
            )

        reason_map = {
            "below_minimum_score_threshold": "its score was below the minimum editorial threshold",
            "selection_limit_reached": "the candidate set had already reached the story limit",
            "rejected_by_topic_diversity_soft_cap": "a similar-topic cluster with a close score had already been kept",
            "rejected_by_source_diversity_soft_cap": "other close-scoring clusters already represented the same source mix",
            "commentary_like_cluster_below_editorial_bar": "its title looked commentary-like and it did not clear the higher bar for inclusion",
            "rejected_by_editorial_preferences_soft_target": "a near-tie cluster better matched the requested editorial preferences",
        }
        detail = reason_map.get(reason, reason)
        return (
            f"Rejected '{title}' because {detail}. The cluster scored {cluster.score_total} points, "
            f"topic '{topic_label}', domain '{domain_label}', geography '{geography_label}', sources {sources}."
            f"{preference_clause}"
        )

    def _build_selection_explanation(
        self,
        selected: list[ScoredStoryCluster],
        rejected: list[ScoredStoryCluster],
        stats: StorySelectionStats,
        editorial_preferences: EditorialPreferenceProfile | None,
    ) -> str:
        if not selected:
            return (
                f"No clusters were selected. {stats.rejected_count} cluster(s) were rejected under the "
                "current threshold and diversity rules."
            )

        top_titles = ", ".join(
            cluster.cluster.representative_title for cluster in selected[:3]
        )
        preference_note = "Preferences were not applied."
        if editorial_preferences is not None:
            preference_note = (
                "Preferences were applied conservatively as soft near-tie signals for geography and domain mix, "
                "without overriding clearly stronger stories."
            )
        return (
            f"Selected {stats.selected_count} of {stats.total_input_clusters} scored clusters using a "
            f"minimum score of {stats.minimum_score_threshold} and a limit of {stats.max_stories}. "
            f"Top selected titles: {top_titles}. {preference_note}"
        )
