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
ROMANIA_IMPACT_TERMS = {
    "romania", "romaniei", "roman", "romani", "bucuresti", "guvern", "guvernul", "parlament",
    "presedintie", "pnrr", "fonduri europene", "buget", "deficit", "energie", "carburant",
    "motorina", "bnr", "ccr", "anaf", "mae", "mapn", "psd", "pnl", "usr",
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
        romanian_domestic_balance = self._score_romanian_domestic_balance(cluster)
        editorial_fit = self._score_editorial_fit(cluster)

        total = round(
            recency.contribution
            + source_count.contribution
            + source_quality.contribution
            + entity_importance.contribution
            + topic_weight.contribution
            + title_strength.contribution
            + europe_romania_impact.contribution
            + romanian_domestic_balance.contribution
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
            romanian_domestic_balance=romanian_domestic_balance,
            editorial_fit=editorial_fit,
        )
        explanation = self._build_explanation(cluster, breakdown, total)
        balance_meta = self._romanian_balance_metadata(cluster)
        return ScoredStoryCluster(
            cluster=cluster,
            score_total=total,
            score_breakdown=breakdown,
            scoring_explanation=explanation,
            scored_at=scored_at,
            domestic_purity_score=balance_meta['domestic_purity_score'],
            romania_impact_evidence_hits=balance_meta['romania_impact_evidence_hits'],
            external_penalty_applied=balance_meta['external_penalty_applied'],
            title_only_domestic_boost=balance_meta['title_only_domestic_boost'],
            cluster_event_family_hints=balance_meta['cluster_event_family_hints'],
            domestic_vs_external_rank_reason=balance_meta['domestic_vs_external_rank_reason'],
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


    def _romanian_balance_metadata(self, cluster: StoryCluster) -> dict[str, object]:
        national_members = [
            member for member in cluster.member_articles
            if member.source_scope == "national"
        ]
        if not national_members:
            return {
                "domestic_purity_score": 0.0,
                "romania_impact_evidence_hits": [],
                "external_penalty_applied": 0.0,
                "title_only_domestic_boost": 0.0,
                "cluster_event_family_hints": [],
                "domestic_vs_external_rank_reason": "non-national cluster: Romanian domestic balancing not applied",
            }

        total_members = len(national_members)
        domestic_members = [member for member in national_members if member.national_preference_bucket == "domestic_hard_news"]
        external_members = [member for member in national_members if member.national_preference_bucket == "external_direct_impact"]
        off_target_members = [member for member in national_members if member.national_preference_bucket == "off_target"]
        hints = sorted({hint for member in national_members for hint in (member.romanian_event_family_hints or [])})
        institutions = sorted({hit for member in national_members for hit in (member.institutional_signal_hits or [])})
        impact_hits = sorted({hit for member in national_members for hit in (member.romania_impact_evidence_hits or [])})
        title_only_boost = round(sum(member.title_only_domestic_boost or 0.0 for member in national_members), 2)
        avg_domestic_score = sum((member.domestic_score_total or 0.0) for member in national_members) / max(total_members, 1)
        title_text = self._cluster_text_from_members(cluster.member_articles)
        title_hits = sorted(term for term in ROMANIA_IMPACT_TERMS if term in title_text)
        combined_impact_hits = sorted(set(impact_hits) | set(title_hits))
        strong_impact_hits = [
            hit for hit in combined_impact_hits
            if hit not in {"roman", "romani", "romania", "romaniei", "bucuresti"}
        ]

        domestic_ratio = len(domestic_members) / total_members
        external_ratio = len(external_members) / total_members
        off_target_ratio = len(off_target_members) / total_members
        purity = (
            (domestic_ratio * 0.55)
            + (min(len(hints), 4) * 0.06)
            + (min(len(institutions), 4) * 0.05)
            + (min(len(combined_impact_hits), 5) * 0.04)
            + min(max(avg_domestic_score, 0.0) / 24.0, 0.18)
            + min(title_only_boost / 6.0, 0.12)
            - (external_ratio * 0.24)
            - (off_target_ratio * 0.18)
        )
        domestic_purity_score = round(min(max(purity, 0.0), 1.0), 3)

        external_penalty_applied = 0.0
        reason_parts: list[str] = []
        if external_ratio >= 0.5 and len(strong_impact_hits) < 2:
            external_penalty_applied = round(min(0.38, 0.14 + (external_ratio * 0.24)), 2)
            reason_parts.append("weak Romania-specific impact evidence for external-leaning cluster")
        if domestic_ratio >= 0.34 or domestic_purity_score >= 0.45:
            reason_parts.append("credible Romanian domestic evidence improved national ranking")
        if title_only_boost > 0:
            reason_parts.append("title-only domestic candidate added survivability")
        if not reason_parts:
            reason_parts.append("Romanian balance stayed neutral")

        return {
            "domestic_purity_score": domestic_purity_score,
            "romania_impact_evidence_hits": combined_impact_hits[:8],
            "external_penalty_applied": external_penalty_applied,
            "title_only_domestic_boost": round(min(title_only_boost, 3.0), 2),
            "cluster_event_family_hints": hints[:8],
            "domestic_vs_external_rank_reason": "; ".join(reason_parts),
        }

    def _score_romanian_domestic_balance(self, cluster: StoryCluster) -> ScoreComponent:
        max_points = 8.0
        metadata = self._romanian_balance_metadata(cluster)
        normalized = metadata["domestic_purity_score"]
        penalty = metadata["external_penalty_applied"]
        contribution = round(max((normalized - penalty) * max_points, -2.0), 2)
        explanation = (
            f"Romanian domestic purity={normalized}, impact_hits={', '.join(metadata['romania_impact_evidence_hits']) or 'none'}, "
            f"event_hints={', '.join(metadata['cluster_event_family_hints']) or 'none'}, external_penalty={penalty}, "
            f"title_only_domestic_boost={metadata['title_only_domestic_boost']}. {metadata['domestic_vs_external_rank_reason']}."
        )
        return ScoreComponent(
            name="romanian_domestic_balance",
            value=round(normalized, 3),
            max_points=max_points,
            contribution=contribution,
            explanation=explanation,
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

    def _cluster_text_from_members(self, members: list) -> str:
        titles = " ".join(member.title for member in members)
        return titles.lower()

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
                breakdown.romanian_domestic_balance,
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
