from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re

from app.models.news_cluster import StoryCluster
from app.models.story_score import ScoredStoryCluster, ScoreComponent, StoryScoreBreakdown

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "story_scoring_config.json"
TOKEN_PATTERN = re.compile(r"[0-9A-Za-z\u00C0-\u024F][0-9A-Za-z\u00C0-\u024F\-']{2,}")
ENGLISH_HEADLINE_MARKERS = {
    "asks", "back", "bounce", "bottom", "bracketology", "charges", "conference", "department",
    "evidence", "federal", "investigation", "judge", "justice", "losers", "record", "rock",
    "selling", "shoots", "sold", "sports", "taliban", "winners", "year",
}
LOW_VALUE_TITLE_MARKERS = {
    "live-text", "live text", "video", "photos", "gallery", "highlights", "odds", "preview",
    "recap", "bracketology", "winners", "losers", "propozitie cu", "cum se scrie", "definitie",
    "ce inseamna", "ghid", "tutorial",
}
EUROPE_ROMANIA_IMPACT_TERMS: dict[str, float] = {
    "black sea": 1.0,
    "marea neagra": 1.0,
    "romania": 1.0,
    "romanian": 0.95,
    "romania's": 0.95,
    "european union": 0.95,
    "eu": 0.9,
    "brussels": 0.9,
    "nato": 0.95,
    "ukraine": 0.95,
    "ucraina": 0.95,
    "moldova": 0.9,
    "balkans": 0.8,
    "balcani": 0.8,
    "middle east": 0.7,
    "orientul mijlociu": 0.7,
    "gulf": 0.8,
    "golf": 0.8,
    "emiratele": 0.75,
    "ports": 0.7,
    "porturi": 0.7,
    "eurozone": 0.9,
    "ecb": 0.9,
    "european central bank": 0.9,
    "european markets": 0.8,
    "european energy": 0.85,
    "energy supply": 0.8,
    "gas supply": 0.8,
    "oil": 0.55,
    "gas": 0.55,
    "shipping": 0.65,
    "shipping routes": 0.8,
    "strait of hormuz": 0.85,
    "ormuz": 0.85,
    "security": 0.7,
    "defence": 0.7,
    "defense": 0.7,
    "migration": 0.7,
}


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
        self.priority_quality_weights: dict[int, float] = {1: 1.0, 2: 0.9, 3: 0.75, 4: 0.55, 5: 0.35}
        self.ingestion_quality_adjustments: dict[str, float] = {
            "full_fetch": 0.0,
            "rss_fallback": -0.2,
            "unknown": -0.05,
        }

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
        europe_romania_impact = self._score_europe_romania_impact(cluster)
        editorial_fit = self._score_editorial_fit(cluster)

        total = round(
            recency.contribution
            + source_count.contribution
            + source_quality.contribution
            + entity_importance.contribution
            + topic_weight.contribution
            + title_strength.contribution
            + europe_romania_impact.contribution
            + editorial_fit.contribution,
            2,
        )
        breakdown = StoryScoreBreakdown(
            recency=recency,
            source_count=source_count,
            source_quality=source_quality,
            entity_importance=entity_importance,
            topic_weight=topic_weight,
            title_strength=title_strength,
            europe_romania_impact=europe_romania_impact,
            editorial_fit=editorial_fit,
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
        source_scores = []
        rss_fallback_count = 0
        for member in cluster.member_articles:
            priority_weight = self.priority_quality_weights.get(member.editorial_priority, 0.6)
            configured_weight = self.source_quality_weights.get(member.source, priority_weight)
            ingestion_adjustment = self.ingestion_quality_adjustments.get(
                member.ingestion_kind,
                self.ingestion_quality_adjustments["unknown"],
            )
            if member.ingestion_kind == "rss_fallback":
                rss_fallback_count += 1
            source_scores.append(min(max(configured_weight + ingestion_adjustment, 0.1), 1.0))
        average_quality = sum(source_scores) / len(source_scores)
        contribution = round(average_quality * self.weights["source_quality"], 2)
        explanation = "Source-quality bonus uses trust weighting, registry priority, and a modest RSS fallback penalty."
        if rss_fallback_count:
            explanation += (
                f" {rss_fallback_count} cluster article(s) came from RSS fallback and were scored more conservatively."
            )
        return ScoreComponent(
            name="source_quality",
            value=round(average_quality, 2),
            max_points=self.weights["source_quality"],
            contribution=contribution,
            explanation=explanation,
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

    def _score_europe_romania_impact(self, cluster: StoryCluster) -> ScoreComponent:
        max_points = 9.0
        scopes = {
            member.source_scope or ("local" if member.is_local_source else "unknown")
            for member in cluster.member_articles
        }
        text = self._cluster_text(cluster)
        matched_terms = [
            (term, weight)
            for term, weight in EUROPE_ROMANIA_IMPACT_TERMS.items()
            if term.lower() in text
        ]

        if "international" not in scopes:
            return ScoreComponent(
                name="europe_romania_impact",
                value=0.0,
                max_points=max_points,
                contribution=0.0,
                explanation="Europe/Romania impact boost applies only to international clusters.",
            )

        normalized = min(sum(weight for _, weight in matched_terms), 2.0) / 2.0

        categories = {member.source_category or "general" for member in cluster.member_articles}
        if any(category in {"entertainment", "lifestyle"} for category in categories):
            normalized = max(normalized - 0.35, 0.0)
        elif "sport" in categories and normalized < 0.75:
            normalized = max(normalized - 0.2, 0.0)

        contribution = round(normalized * max_points, 2)
        label_text = ", ".join(term for term, _ in matched_terms[:5]) if matched_terms else "none"
        return ScoreComponent(
            name="europe_romania_impact",
            value=round(normalized, 2),
            max_points=max_points,
            contribution=contribution,
            explanation=(
                f"International relevance to Europe/Romania matched: {label_text}."
            ),
        )

    def _score_editorial_fit(self, cluster: StoryCluster) -> ScoreComponent:
        max_points = 12.0
        categories = {member.source_category or "general" for member in cluster.member_articles}
        scopes = {
            member.source_scope or ("local" if member.is_local_source else "unknown")
            for member in cluster.member_articles
        }
        priorities = [member.editorial_priority for member in cluster.member_articles]
        title = cluster.representative_title
        lowered_title = title.lower()
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(title)]
        english_hits = [token for token in tokens if token in ENGLISH_HEADLINE_MARKERS]
        low_value_markers = [marker for marker in LOW_VALUE_TITLE_MARKERS if marker in lowered_title]

        category_scores = {
            "general": 1.0,
            "economy": 0.95,
            "analysis": 0.65,
            "sport": 0.26,
            "entertainment": 0.05,
            "lifestyle": 0.05,
        }
        normalized = sum(category_scores.get(category, 0.6) for category in categories) / max(len(categories), 1)
        if "local" in scopes:
            normalized += 0.22
        elif "national" in scopes:
            normalized += 0.08

        if priorities:
            normalized += max(0.0, (6 - min(priorities)) * 0.03)

        national_buckets = [
            member.national_preference_bucket
            for member in cluster.member_articles
            if (member.source_scope == "national" and member.national_preference_bucket)
        ]
        reasons: list[str] = []
        if national_buckets:
            bucket_boosts = {
                "domestic_hard_news": 0.18,
                "external_direct_impact": 0.08,
                "off_target": -0.22,
            }
            average_bucket_boost = sum(bucket_boosts.get(bucket, 0.0) for bucket in national_buckets) / len(national_buckets)
            normalized += average_bucket_boost
            dominant_bucket = max(set(national_buckets), key=national_buckets.count)
            reasons.append(f"national-first preference bucket: {dominant_bucket}")

        if low_value_markers:
            penalty = 0.55 if any(marker in {"propozitie cu", "cum se scrie", "definitie", "ghid", "tutorial"} for marker in low_value_markers) else 0.42
            normalized -= penalty
            reasons.append(f"low-value title markers: {', '.join(low_value_markers[:3])}")
        if len(english_hits) >= 2:
            penalty = 0.52 if "local" not in scopes else 0.18
            normalized -= penalty
            reasons.append(f"English-heavy title tokens: {', '.join(english_hits[:4])}")
        if len(tokens) < 4:
            normalized -= 0.18
            reasons.append("headline too short for strong editorial context")
        if any(category in {"sport", "entertainment", "lifestyle"} for category in categories) and "local" not in scopes:
            normalized -= 0.24
            reasons.append("soft-news category without local relevance")
        if min(priorities or [3]) >= 5 and "local" not in scopes:
            normalized -= 0.16
            reasons.append("low-priority source without local relevance")

        normalized = min(max(normalized, 0.0), 1.0)
        contribution = round(normalized * max_points, 2)
        categories_text = ", ".join(sorted(categories))
        scopes_text = ", ".join(sorted(scopes))
        reason_text = "; ".join(reasons) if reasons else "category/scope fit stayed within conservative hard-news defaults"
        return ScoreComponent(
            name="editorial_fit",
            value=round(normalized, 2),
            max_points=max_points,
            contribution=contribution,
            explanation=(
                f"Editorial fit considered categories [{categories_text}], scopes [{scopes_text}], and headline quality. {reason_text}."
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
                breakdown.europe_romania_impact,
                breakdown.editorial_fit,
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
