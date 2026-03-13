from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re

from app.models.news_cluster import StoryCluster
from app.models.story_score import ScoredStoryCluster, ScoreComponent, StoryScoreBreakdown

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "story_scoring_config.json"
TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")


class StoryScoringService:
    def __init__(self) -> None:
        raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.weights: dict[str, float] = raw_config["weights"]
        self.recency_hours_full_score: float = raw_config["recency_hours_full_score"]
        self.recency_hours_zero_score: float = raw_config["recency_hours_zero_score"]
        self.source_count_bonus: dict[int, float] = {
            int(key): float(value) for key, value in raw_config["source_count_bonus"].items()
        }
        self.source_quality_weights: dict[str, float] = raw_config["source_quality_weights"]
        self.entity_importance_terms: dict[str, float] = raw_config["entity_importance_terms"]
        self.topic_keywords: dict[str, float] = raw_config["topic_keywords"]
        self.title_strength_keywords: dict[str, float] = raw_config["title_strength_keywords"]

    def score_clusters(
        self,
        clusters: list[StoryCluster],
        reference_time: datetime | None = None,
    ) -> list[ScoredStoryCluster]:
        scored_at = reference_time or datetime.now(UTC)
        scored_clusters = [self.score_cluster(cluster, scored_at) for cluster in clusters]
        return sorted(scored_clusters, key=lambda item: item.score_total, reverse=True)

    def score_cluster(
        self,
        cluster: StoryCluster,
        reference_time: datetime | None = None,
    ) -> ScoredStoryCluster:
        scored_at = reference_time or datetime.now(UTC)
        recency = self._score_recency(cluster, scored_at)
        source_count = self._score_source_count(cluster)
        source_quality = self._score_source_quality(cluster)
        entity_importance = self._score_entity_importance(cluster)
        topic_weight = self._score_topic_weight(cluster)
        title_strength = self._score_title_strength(cluster)

        total = round(
            recency.contribution
            + source_count.contribution
            + source_quality.contribution
            + entity_importance.contribution
            + topic_weight.contribution
            + title_strength.contribution,
            2,
        )
        breakdown = StoryScoreBreakdown(
            recency=recency,
            source_count=source_count,
            source_quality=source_quality,
            entity_importance=entity_importance,
            topic_weight=topic_weight,
            title_strength=title_strength,
        )
        explanation = self._build_explanation(cluster, breakdown, total)
        return ScoredStoryCluster(
            cluster=cluster,
            score_total=total,
            score_breakdown=breakdown,
            scoring_explanation=explanation,
            scored_at=scored_at,
        )

    def _score_recency(self, cluster: StoryCluster, reference_time: datetime) -> ScoreComponent:
        age_hours = max(
            (reference_time - cluster.latest_published_at).total_seconds() / 3600.0,
            0.0,
        )
        if age_hours <= self.recency_hours_full_score:
            normalized = 1.0
        elif age_hours >= self.recency_hours_zero_score:
            normalized = 0.0
        else:
            window = self.recency_hours_zero_score - self.recency_hours_full_score
            normalized = 1.0 - ((age_hours - self.recency_hours_full_score) / window)

        contribution = round(normalized * self.weights["recency"], 2)
        return ScoreComponent(
            name="recency",
            value=round(age_hours, 2),
            max_points=self.weights["recency"],
            contribution=contribution,
            explanation=(
                f"Latest article is {age_hours:.1f} hours old; newer clusters keep more of the "
                f"{self.weights['recency']:.0f}-point recency budget."
            ),
        )

    def _score_source_count(self, cluster: StoryCluster) -> ScoreComponent:
        distinct_sources = len({member.source for member in cluster.member_articles})
        capped_sources = min(distinct_sources, max(self.source_count_bonus))
        contribution = round(self.source_count_bonus.get(capped_sources, 0.0), 2)
        return ScoreComponent(
            name="source_count",
            value=float(distinct_sources),
            max_points=self.weights["source_count"],
            contribution=contribution,
            explanation=(
                f"Cluster has {distinct_sources} distinct source(s); broader confirmation raises "
                "priority modestly."
            ),
        )

    def _score_source_quality(self, cluster: StoryCluster) -> ScoreComponent:
        source_scores = [
            self.source_quality_weights.get(member.source, 0.6)
            for member in cluster.member_articles
        ]
        average_quality = sum(source_scores) / len(source_scores)
        contribution = round(average_quality * self.weights["source_quality"], 2)
        return ScoreComponent(
            name="source_quality",
            value=round(average_quality, 2),
            max_points=self.weights["source_quality"],
            contribution=contribution,
            explanation=(
                "Source-quality bonus uses a modest average trust weight across member sources."
            ),
        )

    def _score_entity_importance(self, cluster: StoryCluster) -> ScoreComponent:
        title_text = self._cluster_text(cluster)
        matched_terms = [
            weight
            for term, weight in self.entity_importance_terms.items()
            if term.lower() in title_text
        ]
        normalized = min(sum(matched_terms), 2.0) / 2.0
        contribution = round(normalized * self.weights["entity_importance"], 2)
        matched_labels = [
            term for term in self.entity_importance_terms if term.lower() in title_text
        ]
        label_text = ", ".join(matched_labels[:4]) if matched_labels else "none"
        return ScoreComponent(
            name="entity_importance",
            value=round(normalized, 2),
            max_points=self.weights["entity_importance"],
            contribution=contribution,
            explanation=(
                f"Important institutions/leaders/countries matched: {label_text}."
            ),
        )

    def _score_topic_weight(self, cluster: StoryCluster) -> ScoreComponent:
        text = self._cluster_text(cluster)
        matched_weights = [
            weight for keyword, weight in self.topic_keywords.items() if keyword.lower() in text
        ]
        normalized = min(sum(matched_weights), 2.0) / 2.0
        contribution = round(normalized * self.weights["topic_weight"], 2)
        matched_labels = [
            keyword for keyword in self.topic_keywords if keyword.lower() in text
        ]
        label_text = ", ".join(matched_labels[:4]) if matched_labels else "none"
        return ScoreComponent(
            name="topic_weight",
            value=round(normalized, 2),
            max_points=self.weights["topic_weight"],
            contribution=contribution,
            explanation=(
                f"Topic terms matched: {label_text}; hard-news topics receive a modest boost."
            ),
        )

    def _score_title_strength(self, cluster: StoryCluster) -> ScoreComponent:
        title = cluster.representative_title.lower()
        matched_weights = [
            weight
            for keyword, weight in self.title_strength_keywords.items()
            if keyword.lower() in title
        ]
        verb_signal = min(max(matched_weights, default=0.25), 1.0)
        token_count = len(TOKEN_PATTERN.findall(cluster.representative_title))
        specificity_bonus = 0.15 if token_count >= 8 else 0.0
        normalized = min(verb_signal + specificity_bonus, 1.0)
        contribution = round(normalized * self.weights["title_strength"], 2)
        matched_labels = [
            keyword for keyword in self.title_strength_keywords if keyword.lower() in title
        ]
        label_text = ", ".join(matched_labels[:3]) if matched_labels else "none"
        return ScoreComponent(
            name="title_strength",
            value=round(normalized, 2),
            max_points=self.weights["title_strength"],
            contribution=contribution,
            explanation=(
                f"Representative title matched event-language cues: {label_text}."
            ),
        )

    def _cluster_text(self, cluster: StoryCluster) -> str:
        titles = " ".join(member.title for member in cluster.member_articles)
        return f"{cluster.representative_title} {titles}".lower()

    def _build_explanation(
        self,
        cluster: StoryCluster,
        breakdown: StoryScoreBreakdown,
        total: float,
    ) -> str:
        top_components = sorted(
            [
                breakdown.recency,
                breakdown.source_count,
                breakdown.source_quality,
                breakdown.entity_importance,
                breakdown.topic_weight,
                breakdown.title_strength,
            ],
            key=lambda component: component.contribution,
            reverse=True,
        )[:3]
        component_summary = ", ".join(
            f"{component.name} (+{component.contribution})" for component in top_components
        )
        return (
            f"Cluster '{cluster.representative_title}' scored {total} points. "
            f"Largest contributors: {component_summary}."
        )
