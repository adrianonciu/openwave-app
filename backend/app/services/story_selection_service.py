from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path

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

    def select_stories(
        self,
        scored_clusters: list[ScoredStoryCluster],
        max_stories: int | None = None,
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

        for cluster in ordered_clusters:
            topic_label = self._infer_topic(cluster)
            source_labels = self._source_labels(cluster)
            base_rejection = self._base_rejection_reason(cluster, effective_max_stories, selected)
            if base_rejection is not None:
                rejected.append(cluster)
                decisions.append(
                    self._build_decision(
                        cluster=cluster,
                        status="rejected",
                        reason=base_rejection,
                        topic_label=topic_label,
                        source_labels=source_labels,
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
                        source_labels=source_labels,
                    )
                )
                continue

            selected.append(cluster)
            for source_label in source_labels:
                source_counter[source_label] += 1
            topic_counter[topic_label] += 1
            decisions.append(
                self._build_decision(
                    cluster=cluster,
                    status="selected",
                    reason="selected_for_candidate_set",
                    topic_label=topic_label,
                    source_labels=source_labels,
                )
            )

        stats = StorySelectionStats(
            total_input_clusters=len(scored_clusters),
            selected_count=len(selected),
            rejected_count=len(rejected),
            max_stories=effective_max_stories,
            minimum_score_threshold=self.minimum_score_threshold,
        )
        explanation = self._build_selection_explanation(selected, rejected, stats)
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
        max_stories: int,
        selected: list[ScoredStoryCluster],
    ) -> str | None:
        if cluster.score_total < self.minimum_score_threshold:
            return "below_minimum_score_threshold"

        if len(selected) >= max_stories:
            return "selection_limit_reached"

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
        source_labels: list[str],
    ) -> StorySelectionDecision:
        explanation = self._decision_explanation(
            cluster=cluster,
            status=status,
            reason=reason,
            topic_label=topic_label,
            source_labels=source_labels,
        )
        return StorySelectionDecision(
            cluster_id=cluster.cluster.cluster_id,
            status=status,
            reason=reason,
            score_total=cluster.score_total,
            topic_label=topic_label,
            source_labels=source_labels,
            explanation=explanation,
        )

    def _decision_explanation(
        self,
        cluster: ScoredStoryCluster,
        status: str,
        reason: str,
        topic_label: str,
        source_labels: list[str],
    ) -> str:
        title = cluster.cluster.representative_title
        sources = ", ".join(source_labels) or "unknown source"
        if status == "selected":
            return (
                f"Selected '{title}' because it cleared the score threshold with {cluster.score_total} points "
                f"and fit the current mix for topic '{topic_label}' across sources {sources}."
            )

        reason_map = {
            "below_minimum_score_threshold": "its score was below the minimum editorial threshold",
            "selection_limit_reached": "the candidate set had already reached the story limit",
            "rejected_by_topic_diversity_soft_cap": "a similar-topic cluster with a close score had already been kept",
            "rejected_by_source_diversity_soft_cap": "other close-scoring clusters already represented the same source mix",
            "commentary_like_cluster_below_editorial_bar": "its title looked commentary-like and it did not clear the higher bar for inclusion",
        }
        detail = reason_map.get(reason, reason)
        return (
            f"Rejected '{title}' because {detail}. The cluster scored {cluster.score_total} points, "
            f"topic '{topic_label}', sources {sources}."
        )

    def _build_selection_explanation(
        self,
        selected: list[ScoredStoryCluster],
        rejected: list[ScoredStoryCluster],
        stats: StorySelectionStats,
    ) -> str:
        if not selected:
            return (
                f"No clusters were selected. {stats.rejected_count} cluster(s) were rejected under the "
                "current threshold and diversity rules."
            )

        top_titles = ", ".join(
            cluster.cluster.representative_title for cluster in selected[:3]
        )
        return (
            f"Selected {stats.selected_count} of {stats.total_input_clusters} scored clusters using a "
            f"minimum score of {stats.minimum_score_threshold} and a limit of {stats.max_stories}. "
            f"Top selected titles: {top_titles}."
        )
