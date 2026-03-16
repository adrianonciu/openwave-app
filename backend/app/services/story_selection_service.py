from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import re

ROMANIAN_EVENT_PERSISTENCE_PATH = Path(__file__).resolve().parents[2] / "data" / "romanian_event_persistence_state.json"
ROMANIAN_PERSISTENCE_HINTS = {
    "romanian_fiscal_policy_2026",
    "romanian_domestic_politics",
    "romanian_pnrr_funds",
    "romanian_energy_security",
    "romanian_justice",
    "romanian_justice_case",
    "romanian_prosecutor_decision",
    "romanian_high_court_decision",
    "romanian_anti_corruption_case",
    "romanian_major_policy_decision",
}
ROMANIAN_RECOVERY_HINTS = {
    "romanian_domestic_politics",
    "romanian_fiscal_policy_2026",
    "romanian_pnrr_funds",
    "romanian_energy_security",
    "romanian_justice",
    "romanian_justice_case",
    "romanian_prosecutor_decision",
    "romanian_high_court_decision",
    "romanian_anti_corruption_case",
    "romanian_major_policy_decision",
    "romanian_budget_fiscal",
}
ROMANIAN_PRIORITY_RECOVERY_HINTS = {
    "romanian_domestic_politics",
    "romanian_fiscal_policy_2026",
    "romanian_justice",
    "romanian_justice_case",
    "romanian_prosecutor_decision",
    "romanian_high_court_decision",
    "romanian_anti_corruption_case",
    "romanian_major_policy_decision",
    "romanian_budget_fiscal",
}
JUSTICE_PERSISTENCE_HINTS = {
    "romanian_justice",
    "romanian_justice_case",
    "romanian_prosecutor_decision",
    "romanian_high_court_decision",
    "romanian_anti_corruption_case",
}
ROMANIAN_RECOVERY_POLICY_TERMS = {
    "buget", "deficit", "deficit bugetar", "taxe", "salariu minim", "energie", "pnrr", "reforme", "carburant", "motorina", "amendamente buget"
}
ROMANIAN_RECOVERY_INSTITUTIONS = {
    "guvern", "guvernul", "parlament", "ccr", "bnr", "anaf", "mae", "mapn", "psd", "pnl", "usr", "csm", "dna", "diicot", "procuror sef", "procuror-sef", "procuror", "procurorilor", "audieri"
}
ROMANIAN_RECOVERY_MIN_PURITY = 0.35
ROMANIAN_RECOVERY_REQUIRED_IMPACT_HITS = 1
ROMANIAN_RECOVERY_SCORE_RATIO = 0.52
ROMANIAN_JUSTICE_RECOVERY_MIN_PURITY = 0.2

from app.models.editorial_preferences import EditorialPreferenceProfile
from app.models.story_score import ScoredStoryCluster
from app.models.story_selection import (
    StorySelectionDecision,
    StorySelectionResult,
    StorySelectionStats,
)
from app.models.user_personalization import UserPersonalization

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
        self.regional_preference_influence_strength: float = raw_config.get(
            "regional_preference_influence_strength",
            1.0,
        )
        self.minimum_editorial_fit: float = raw_config.get("minimum_editorial_fit", 0.24)
        self.soft_news_editorial_fit_bar: float = raw_config.get("soft_news_editorial_fit_bar", 0.42)
        self.minimum_unique_sources: int = raw_config.get("minimum_unique_sources", 2)
        self.anchor_min_unique_sources: int = raw_config.get("anchor_min_unique_sources", 3)
        self.placeholder_headline_pattern = re.compile(
            r"^(?:actualitate|stiri|stiri|live|breaking|updates?|context)$",
            re.IGNORECASE,
        )
        self.national_hard_news_excluded_categories = {
            "sport",
            "entertainment",
            "lifestyle",
            "culture",
            "tv",
        }
        self._romanian_event_persistence_state = self._load_romanian_event_persistence_state()

    def select_stories(
        self,
        scored_clusters: list[ScoredStoryCluster],
        max_stories: int | None = None,
        editorial_preferences: EditorialPreferenceProfile | None = None,
        personalization: UserPersonalization | None = None,
    ) -> StorySelectionResult:
        effective_max_stories = max_stories or self.default_max_stories
        selected_at = datetime.now(UTC)
        self._romanian_event_persistence_state = self._load_romanian_event_persistence_state()
        ordered_clusters = sorted(
            scored_clusters,
            key=self._selection_sort_key,
            reverse=True,
        )
        resolved_preferences = (
            editorial_preferences
            or (personalization.editorial_preferences if personalization is not None else None)
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
            regional_relevance = self._infer_regional_relevance(cluster, personalization)
            source_labels = self._source_labels(cluster)
            preference_summary = self._preference_summary(
                cluster=cluster,
                selected=selected,
                domain_counter=domain_counter,
                geography_counter=geography_counter,
                editorial_preferences=resolved_preferences,
                personalization=personalization,
                top_score=top_score,
            )
            regional_preference_summary = self._regional_preference_summary(
                cluster=cluster,
                editorial_preferences=resolved_preferences,
                personalization=personalization,
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
                        regional_relevance=regional_relevance,
                        source_labels=source_labels,
                        preference_influence_used=False,
                        preference_influence_summary=preference_summary,
                        regional_preference_used=False,
                        regional_preference_summary=None,
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
                        regional_relevance=regional_relevance,
                        source_labels=source_labels,
                        preference_influence_used=False,
                        preference_influence_summary=preference_summary,
                        regional_preference_used=False,
                        regional_preference_summary=None,
                    )
                )
                continue

            (
                preferred,
                displacement_reason,
                displacement_regional_used,
                displacement_regional_summary,
            ) = self._preference_displacement_reason(
                cluster=cluster,
                selected=selected,
                domain_counter=domain_counter,
                geography_counter=geography_counter,
                editorial_preferences=resolved_preferences,
                personalization=personalization,
                max_stories=effective_max_stories,
            )
            if preferred and displacement_reason is not None:
                displaced_cluster = selected.pop()
                displaced_topic = self._infer_topic(displaced_cluster)
                displaced_domain = self._infer_domain(displaced_cluster)
                displaced_geography = self._infer_geography(displaced_cluster)
                displaced_regional_relevance = self._infer_regional_relevance(
                    displaced_cluster,
                    personalization,
                )
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
                        regional_relevance=displaced_regional_relevance,
                        source_labels=displaced_sources,
                        preference_influence_used=True,
                        preference_influence_summary=displacement_reason,
                        regional_preference_used=displacement_regional_used,
                        regional_preference_summary=displacement_regional_summary,
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
                        regional_relevance=regional_relevance,
                        source_labels=source_labels,
                        preference_influence_used=False,
                        preference_influence_summary=preference_summary,
                        regional_preference_used=False,
                        regional_preference_summary=None,
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
                    regional_relevance=regional_relevance,
                    source_labels=source_labels,
                    preference_influence_used=preferred,
                    preference_influence_summary=preference_summary if preferred else None,
                    regional_preference_used=bool(preferred and regional_preference_summary),
                    regional_preference_summary=regional_preference_summary if preferred else None,
                )
            )

        selected = sorted(selected, key=self._selection_sort_key, reverse=True)
        selected = self._rebalance_national_domestic_selection(selected, ordered_clusters, effective_max_stories)
        selected = self._recover_near_miss_domestic_candidates(selected, rejected, ordered_clusters, effective_max_stories)
        selected = self._apply_soft_external_cap(selected, ordered_clusters, effective_max_stories)
        selected = self._enforce_story_family_diversity_cap(selected, ordered_clusters, effective_max_stories)
        selected = self._enforce_local_geography_diversity_cap(selected, ordered_clusters, effective_max_stories)
        selected = sorted(selected, key=self._selection_sort_key, reverse=True)
        self._persist_romanian_event_persistence_state(selected, selected_at)
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
            resolved_preferences,
            personalization,
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

        editorial_fit = cluster.score_breakdown.editorial_fit.value
        editorial_fit_explanation = cluster.score_breakdown.editorial_fit.explanation.lower()
        scopes = self._cluster_scopes(cluster)
        categories = self._cluster_categories(cluster)
        is_local = self._has_local_relevance(cluster)
        if self._is_placeholder_headline(cluster.cluster.representative_title):
            return "placeholder_headline_cluster"
        if cluster.editorial_profile_used == "local" and not is_local:
            return "missing_local_geographic_signal"
        if "national" in scopes and categories & self.national_hard_news_excluded_categories:
            return "non_hard_news_national_cluster"
        unique_source_count = self._unique_source_count(cluster)
        if unique_source_count < self.minimum_unique_sources and not is_local:
            if not self._single_source_national_exception(cluster):
                return "single_source_cluster_without_local_relevance"
        if "low-value title markers" in editorial_fit_explanation and not is_local:
            return "low_value_headline_cluster"
        if "english-heavy title tokens" in editorial_fit_explanation and not is_local:
            return "english_heavy_headline_cluster"
        if "low-priority source without local relevance" in editorial_fit_explanation and editorial_fit < 0.7:
            return "low_priority_source_cluster"
        if "low-value title markers" in editorial_fit_explanation and editorial_fit < 0.6:
            return "low_value_headline_cluster"
        if editorial_fit < self.minimum_editorial_fit:
            return "low_editorial_fit_cluster"

        if self._is_soft_news_cluster(cluster) and editorial_fit < self.soft_news_editorial_fit_bar:
            return "soft_news_cluster_below_editorial_bar"

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
        personalization: UserPersonalization | None,
        max_stories: int,
    ) -> tuple[bool, str | None, bool, str | None]:
        if editorial_preferences is None or editorial_preferences.is_neutral() or not selected:
            return False, None, False, None
        if len(selected) < max_stories:
            candidate_summary = self._preference_summary(
                cluster,
                selected,
                domain_counter,
                geography_counter,
                editorial_preferences,
                personalization,
                top_score=selected[0].score_total if selected else cluster.score_total,
            )
            regional_summary = self._regional_preference_summary(
                cluster,
                editorial_preferences,
                personalization,
                top_score=selected[0].score_total if selected else cluster.score_total,
            )
            return (
                self._preference_match_score(
                    cluster,
                    domain_counter,
                    geography_counter,
                    editorial_preferences,
                    personalization,
                ) > 0,
                candidate_summary,
                regional_summary is not None,
                regional_summary,
            )

        lowest_selected = min(selected, key=lambda item: item.score_total)
        score_gap = lowest_selected.score_total - cluster.score_total
        if score_gap < 0 or score_gap > self.preference_near_tie_tolerance:
            return False, None, False, None

        candidate_score = self._preference_match_score(
            cluster,
            domain_counter,
            geography_counter,
            editorial_preferences,
            personalization,
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
            personalization,
        )
        if candidate_score <= displaced_score:
            return False, None, False, None

        regional_summary = self._regional_preference_summary(
            cluster,
            editorial_preferences,
            personalization,
            top_score=lowest_selected.score_total,
        )
        summary = (
            f"Editorial preferences favored this near-tie because it improves the requested mix for "
            f"geography '{self._infer_geography(cluster)}' and domain '{self._infer_domain(cluster)}' more than "
            f"the displaced cluster."
        )
        if regional_summary:
            summary = f"{summary} {regional_summary}"
        return True, summary, regional_summary is not None, regional_summary

    def _preference_match_score(
        self,
        cluster: ScoredStoryCluster,
        domain_counter: Counter[str],
        geography_counter: Counter[str],
        editorial_preferences: EditorialPreferenceProfile,
        personalization: UserPersonalization | None,
    ) -> float:
        domain_label = self._infer_domain(cluster)
        geography_label = self._infer_geography(cluster)
        domain_weight = getattr(editorial_preferences.domains, domain_label, 0.0)
        geography_weight = getattr(editorial_preferences.geography, geography_label, 0.0)
        regional_bonus = self._regional_preference_bonus(
            cluster,
            editorial_preferences,
            personalization,
        )
        domain_penalty = domain_counter[domain_label] * self.preference_influence_strength
        geography_penalty = geography_counter[geography_label] * self.preference_influence_strength
        raw_score = (domain_weight + geography_weight + regional_bonus) - (domain_penalty + geography_penalty)
        return max(min(raw_score, self.max_preference_adjustment_per_story), 0.0)

    def _preference_summary(
        self,
        cluster: ScoredStoryCluster,
        selected: list[ScoredStoryCluster],
        domain_counter: Counter[str],
        geography_counter: Counter[str],
        editorial_preferences: EditorialPreferenceProfile | None,
        personalization: UserPersonalization | None,
        top_score: float,
    ) -> str | None:
        if editorial_preferences is None or editorial_preferences.is_neutral():
            return None
        score_gap = max(top_score - cluster.score_total, 0.0)
        if score_gap > self.preference_near_tie_tolerance:
            return None
        domain_label = self._infer_domain(cluster)
        geography_label = self._infer_geography(cluster)
        domain_weight = getattr(editorial_preferences.domains, domain_label, 0.0)
        geography_weight = getattr(editorial_preferences.geography, geography_label, 0.0)
        regional_bonus = self._regional_preference_bonus(
            cluster,
            editorial_preferences,
            personalization,
        )
        if domain_weight <= 0 and geography_weight <= 0 and regional_bonus <= 0:
            return None
        summary = (
            f"Near-tie preference signal: domain '{domain_label}' weight={domain_weight}, "
            f"geography '{geography_label}' weight={geography_weight}, current_domain_count={domain_counter[domain_label]}, "
            f"current_geography_count={geography_counter[geography_label]}."
        )
        regional_summary = self._regional_preference_summary(
            cluster,
            editorial_preferences,
            personalization,
            top_score,
        )
        if regional_summary:
            summary = f"{summary} {regional_summary}"
        return summary

    def _regional_preference_bonus(
        self,
        cluster: ScoredStoryCluster,
        editorial_preferences: EditorialPreferenceProfile | None,
        personalization: UserPersonalization | None,
    ) -> float:
        if not self._regional_preference_applies(editorial_preferences, personalization):
            return 0.0
        if self._infer_regional_relevance(cluster, personalization) != "region_match":
            return 0.0
        local_weight = editorial_preferences.geography.local if editorial_preferences is not None else 0.0
        return min(
            (local_weight / 100.0) * self.regional_preference_influence_strength,
            self.max_preference_adjustment_per_story,
        )

    def _regional_preference_applies(
        self,
        editorial_preferences: EditorialPreferenceProfile | None,
        personalization: UserPersonalization | None,
    ) -> bool:
        if editorial_preferences is None or editorial_preferences.is_neutral() or personalization is None:
            return False
        if editorial_preferences.geography.local <= 0:
            return False
        return personalization.local_editorial_anchor_scope() == "region"

    def _regional_preference_summary(
        self,
        cluster: ScoredStoryCluster,
        editorial_preferences: EditorialPreferenceProfile | None,
        personalization: UserPersonalization | None,
        top_score: float,
    ) -> str | None:
        if not self._regional_preference_applies(editorial_preferences, personalization):
            return None
        score_gap = max(top_score - cluster.score_total, 0.0)
        if score_gap > self.preference_near_tie_tolerance:
            return None
        if self._infer_regional_relevance(cluster, personalization) != "region_match":
            return None
        region = personalization.local_editorial_anchor()
        if not region:
            return None
        return f"Cluster favored because it matched user's region: {region}."

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
        if best_domain == "general" and inferred_topic in {"politics", "economy", "justice", "sport"}:
            return inferred_topic
        return best_domain

    def _infer_geography(self, cluster: ScoredStoryCluster) -> str:
        if cluster.local_county_tag:
            return cluster.local_county_tag
        if any(member.is_local_source for member in cluster.cluster.member_articles):
            return "local"
        text = self._cluster_text(cluster)
        best_label = "international"
        best_matches = 0
        for geography, keywords in self.geography_labels.items():
            matches = sum(1 for keyword in keywords if keyword.lower() in text)
            if matches > best_matches:
                best_matches = matches
                best_label = geography
        return best_label

    def _infer_regional_relevance(
        self,
        cluster: ScoredStoryCluster,
        personalization: UserPersonalization | None,
    ) -> str:
        if personalization is None or personalization.local_editorial_anchor_scope() != "region":
            return "unknown"
        if any(member.is_local_source for member in cluster.cluster.member_articles):
            return "region_match"
        anchor = personalization.local_editorial_anchor()
        if not anchor:
            return "unknown"
        text = self._cluster_text(cluster)
        for alias in self._regional_aliases(anchor):
            if alias in text:
                return "region_match"
        geography_label = self._infer_geography(cluster)
        if geography_label == "national":
            return "national"
        if geography_label == "international":
            return "international"
        return "unknown"

    def _regional_aliases(self, region: str) -> set[str]:
        normalized = self._normalize_text(region)
        aliases = {normalized}
        stripped = normalized
        for token in ["county", "judetul", "judet", "region", "regiunea"]:
            stripped = stripped.replace(token, " ")
        stripped = " ".join(stripped.split())
        if stripped:
            aliases.add(stripped)
        return {alias for alias in aliases if alias}

    def _source_labels(self, cluster: ScoredStoryCluster) -> list[str]:
        return sorted({member.source for member in cluster.cluster.member_articles})

    def _cluster_scopes(self, cluster: ScoredStoryCluster) -> set[str]:
        return {
            member.source_scope or ("local" if member.is_local_source else "unknown")
            for member in cluster.cluster.member_articles
        }

    def _has_local_relevance(self, cluster: ScoredStoryCluster) -> bool:
        return (
            "local" in self._cluster_scopes(cluster)
            or cluster.local_relevance_boost > 0
            or bool(cluster.local_county_tag)
        )

    def _cluster_categories(self, cluster: ScoredStoryCluster) -> set[str]:
        return {
            (member.source_category or "general").lower()
            for member in cluster.cluster.member_articles
        }

    def _unique_source_count(self, cluster: ScoredStoryCluster) -> int:
        return len({member.source for member in cluster.cluster.member_articles})

    def _best_editorial_priority(self, cluster: ScoredStoryCluster) -> int:
        priorities = [member.editorial_priority for member in cluster.cluster.member_articles]
        return min(priorities) if priorities else 5

    def _is_anchor_candidate(self, cluster: ScoredStoryCluster) -> bool:
        return self._unique_source_count(cluster) >= self.anchor_min_unique_sources

    def _selection_sort_key(self, cluster: ScoredStoryCluster) -> tuple[float, float, float, float, float]:
        anchor_bonus = 1.0 if self._is_anchor_candidate(cluster) else 0.0
        unique_sources = float(self._unique_source_count(cluster))
        priority_bonus = float(6 - self._best_editorial_priority(cluster))
        adjusted_score = self._selection_adjusted_score(cluster)
        domestic_priority = self._national_domestic_priority(cluster)
        return (adjusted_score, domestic_priority, anchor_bonus, unique_sources, priority_bonus)


    def _dominant_national_bucket(self, cluster: ScoredStoryCluster) -> str | None:
        national_buckets = [
            member.national_preference_bucket
            for member in cluster.cluster.member_articles
            if member.source_scope == "national" and member.national_preference_bucket
        ]
        if not national_buckets:
            return None
        return Counter(national_buckets).most_common(1)[0][0]

    def _single_source_national_exception(self, cluster: ScoredStoryCluster) -> bool:
        if "national" not in self._cluster_scopes(cluster):
            return False
        bucket = self._dominant_national_bucket(cluster)
        if bucket == "domestic_hard_news":
            return (
                cluster.domestic_purity_score >= 0.34
                or len(cluster.romania_impact_evidence_hits) >= 2
                or cluster.title_only_domestic_boost > 0
            )
        return (
            bucket == "off_target"
            and cluster.domestic_purity_score >= 0.45
            and len(cluster.romania_impact_evidence_hits) >= 2
            and cluster.external_penalty_applied <= 0.0
        )

    def _national_domestic_priority(self, cluster: ScoredStoryCluster) -> float:
        bucket = self._dominant_national_bucket(cluster)
        if "national" not in self._cluster_scopes(cluster):
            return 0.0
        if bucket == "domestic_hard_news":
            return 2.5 + (cluster.domestic_purity_score * 2.5)
        if bucket == "external_direct_impact":
            return 0.8 + max(0.0, (len(cluster.romania_impact_evidence_hits) - 1) * 0.3) - cluster.external_penalty_applied
        return max(0.0, cluster.domestic_purity_score - cluster.external_penalty_applied)

    def _selection_adjusted_score(self, cluster: ScoredStoryCluster) -> float:
        bucket = self._dominant_national_bucket(cluster)
        adjusted = cluster.score_total
        if "national" in self._cluster_scopes(cluster):
            persistence_boost = self._persistence_boost_for_cluster(cluster)
            cluster.persistence_boost_applied = persistence_boost
            adjusted += cluster.domestic_purity_score * 4.0
            adjusted += min(cluster.title_only_domestic_boost, 1.5)
            adjusted += persistence_boost
            adjusted -= cluster.external_penalty_applied * 5.0
            if bucket == "domestic_hard_news":
                adjusted += 3.0
            elif bucket == "external_direct_impact" and len(cluster.romania_impact_evidence_hits) < 2:
                adjusted -= 2.5
        return round(adjusted, 2)

    def _is_all_national_input(self, clusters: list[ScoredStoryCluster]) -> bool:
        if not clusters:
            return False
        return all(self._cluster_scopes(cluster) <= {"national"} for cluster in clusters)

    def _is_credible_domestic_candidate(self, cluster: ScoredStoryCluster) -> bool:
        bucket = self._dominant_national_bucket(cluster)
        if bucket == "domestic_hard_news":
            return cluster.domestic_purity_score >= 0.3 or len(cluster.romania_impact_evidence_hits) >= 2 or cluster.title_only_domestic_boost > 0
        return (
            bucket == "off_target"
            and cluster.domestic_purity_score >= 0.45
            and len(cluster.romania_impact_evidence_hits) >= 2
            and cluster.external_penalty_applied <= 0.0
        )

    def _rebalance_national_domestic_selection(
        self,
        selected: list[ScoredStoryCluster],
        ordered_clusters: list[ScoredStoryCluster],
        max_stories: int,
    ) -> list[ScoredStoryCluster]:
        if not self._is_all_national_input(ordered_clusters):
            return selected
        domestic_candidates = [cluster for cluster in ordered_clusters if self._is_credible_domestic_candidate(cluster)]
        if len(domestic_candidates) < 2:
            return selected
        selected_ids = {cluster.cluster.cluster_id for cluster in selected}
        selected_domestic = [cluster for cluster in selected if self._is_credible_domestic_candidate(cluster)]
        if len(selected_domestic) >= 2:
            return selected
        replacement_pool = [cluster for cluster in domestic_candidates if cluster.cluster.cluster_id not in selected_ids]
        if not replacement_pool:
            return selected
        external_selected = [
            cluster for cluster in selected
            if self._dominant_national_bucket(cluster) != "domestic_hard_news"
        ]
        external_selected.sort(key=lambda cluster: (self._selection_adjusted_score(cluster), -cluster.external_penalty_applied))
        while len(selected_domestic) < 2 and replacement_pool and external_selected:
            incoming = replacement_pool.pop(0)
            outgoing = external_selected.pop(0)
            selected = [incoming if item.cluster.cluster_id == outgoing.cluster.cluster_id else item for item in selected]
            selected_ids.discard(outgoing.cluster.cluster_id)
            selected_ids.add(incoming.cluster.cluster_id)
            selected_domestic = [cluster for cluster in selected if self._is_credible_domestic_candidate(cluster)]
        return selected[:max_stories]


    def _load_romanian_event_persistence_state(self) -> dict[str, object]:
        if not ROMANIAN_EVENT_PERSISTENCE_PATH.exists():
            return {"hints": {}, "updated_at": None}
        try:
            return json.loads(ROMANIAN_EVENT_PERSISTENCE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"hints": {}, "updated_at": None}

    def _persist_romanian_event_persistence_state(self, selected: list[ScoredStoryCluster], selected_at: datetime) -> None:
        if not self._is_all_national_input(selected):
            return
        hints_payload: dict[str, dict[str, object]] = {}
        selected_hints = {
            hint
            for cluster in selected
            for hint in (cluster.cluster_event_family_hints or [])
            if hint in ROMANIAN_PERSISTENCE_HINTS
        }
        previous_hints = (self._romanian_event_persistence_state or {}).get("hints", {})
        for hint in selected_hints:
            previous_streak = int((previous_hints.get(hint) or {}).get("streak", 0))
            hints_payload[hint] = {
                "streak": previous_streak + 1,
                "last_seen_at": selected_at.isoformat(),
            }
        ROMANIAN_EVENT_PERSISTENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": selected_at.isoformat(), "hints": hints_payload}
        ROMANIAN_EVENT_PERSISTENCE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._romanian_event_persistence_state = payload

    def _persistence_boost_for_cluster(self, cluster: ScoredStoryCluster) -> float:
        if "national" not in self._cluster_scopes(cluster):
            return 0.0
        previous_hints = (self._romanian_event_persistence_state or {}).get("hints", {})
        streaks = [
            int((previous_hints.get(hint) or {}).get("streak", 0))
            for hint in (cluster.cluster_event_family_hints or [])
            if hint in ROMANIAN_PERSISTENCE_HINTS
        ]
        if not streaks:
            return 0.0
        longest = max(streaks)
        boost = min(2.4, 0.8 + (longest * 0.4))
        if longest >= 2 and any(hint in JUSTICE_PERSISTENCE_HINTS for hint in (cluster.cluster_event_family_hints or [])):
            boost = min(2.6, boost + 0.2)
        return round(boost, 2)

    def _set_recovery_rejection(
        self,
        cluster: ScoredStoryCluster,
        reason: str,
        threshold_name: str,
        required_value: float | str | None,
        current_value: float | str | None,
    ) -> bool:
        cluster.recovery_rejection_reason = reason
        cluster.failed_threshold_name = threshold_name
        cluster.threshold_required_value = required_value
        cluster.candidate_current_value = current_value
        cluster.recovered_domestic_candidate = False
        return False

    def _near_miss_domestic_eligible(self, cluster: ScoredStoryCluster) -> bool:
        if "national" not in self._cluster_scopes(cluster):
            current_scope = ", ".join(sorted(self._cluster_scopes(cluster))) or "unknown"
            return self._set_recovery_rejection(cluster, "candidate is not in the Romanian national scope", "scope", "national", current_scope)
        bucket = self._dominant_national_bucket(cluster)
        if bucket not in {"off_target", "external_direct_impact"}:
            return self._set_recovery_rejection(cluster, "candidate is already classified outside the near-miss recovery buckets", "bucket", "off_target|external_direct_impact", bucket or "none")
        purity = cluster.domestic_purity_score
        justice_hint_present = any(hint in JUSTICE_PERSISTENCE_HINTS for hint in (cluster.cluster_event_family_hints or []))
        required_purity = ROMANIAN_JUSTICE_RECOVERY_MIN_PURITY if justice_hint_present else ROMANIAN_RECOVERY_MIN_PURITY
        if purity < required_purity:
            return self._set_recovery_rejection(cluster, f"purity={purity:.2f} < required={required_purity:.2f}", "domestic_purity_score", required_purity, round(purity, 2))
        impact_hits = len(cluster.romania_impact_evidence_hits or [])
        if impact_hits < ROMANIAN_RECOVERY_REQUIRED_IMPACT_HITS:
            return self._set_recovery_rejection(cluster, f"romania_impact_hits={impact_hits} < required={ROMANIAN_RECOVERY_REQUIRED_IMPACT_HITS}", "romania_impact_evidence_hits", ROMANIAN_RECOVERY_REQUIRED_IMPACT_HITS, impact_hits)
        return True

    def _mini_domestic_recovery_score(self, cluster: ScoredStoryCluster, leading_domestic_score: float) -> float:
        hints = set(cluster.cluster_event_family_hints or []) & ROMANIAN_RECOVERY_HINTS
        priority_hints = set(cluster.cluster_event_family_hints or []) & ROMANIAN_PRIORITY_RECOVERY_HINTS
        institutional_count = len([hit for hit in (cluster.romania_impact_evidence_hits or []) if hit in ROMANIAN_RECOVERY_INSTITUTIONS])
        policy_count = len([hit for hit in (cluster.romania_impact_evidence_hits or []) if hit in ROMANIAN_RECOVERY_POLICY_TERMS])
        score = (
            (cluster.domestic_purity_score * 48.0)
            + (min(len(hints), 3) * 9.0)
            + (min(len(priority_hints), 2) * 8.0)
            + (min(institutional_count, 3) * 9.0)
            + (min(policy_count, 3) * 8.0)
            + min(cluster.title_only_domestic_boost, 1.5) * 8.0
            + min(cluster.persistence_boost_applied, 2.4) * 5.0
        )
        if leading_domestic_score > 0:
            score += min(18.0, (cluster.score_total / leading_domestic_score) * 18.0)
        return round(score, 2)

    def _recover_near_miss_domestic_candidates(
        self,
        selected: list[ScoredStoryCluster],
        rejected: list[ScoredStoryCluster],
        ordered_clusters: list[ScoredStoryCluster],
        max_stories: int,
    ) -> list[ScoredStoryCluster]:
        if not self._is_all_national_input(ordered_clusters):
            return selected
        domestic_selected = [cluster for cluster in selected if self._dominant_national_bucket(cluster) == "domestic_hard_news"]
        leading_domestic_score = max((cluster.score_total for cluster in domestic_selected), default=0.0)
        recovery_pool: list[ScoredStoryCluster] = []
        for cluster in ordered_clusters:
            cluster.recovery_score = 0.0
            cluster.recovery_rejection_reason = None
            cluster.failed_threshold_name = None
            cluster.threshold_required_value = None
            cluster.candidate_current_value = None
            if cluster in selected:
                continue
            if not self._near_miss_domestic_eligible(cluster):
                continue
            recovery_score = self._mini_domestic_recovery_score(cluster, leading_domestic_score)
            cluster.recovery_score = recovery_score
            required_score = round(leading_domestic_score * ROMANIAN_RECOVERY_SCORE_RATIO, 2) if leading_domestic_score > 0 else 0.0
            hints = set(cluster.cluster_event_family_hints or [])
            impact_hits = len(cluster.romania_impact_evidence_hits or [])
            if not hints & ROMANIAN_PRIORITY_RECOVERY_HINTS and impact_hits < 2:
                self._set_recovery_rejection(cluster, "missing required justice/fiscal event hint or second Romania impact signal", "priority_hint_or_impact_hits", "priority hint or 2 impact hits", f"hints={sorted(hints)}, impact_hits={impact_hits}")
                continue
            if leading_domestic_score > 0 and recovery_score < required_score:
                self._set_recovery_rejection(cluster, f"recovery_score={recovery_score} < required={required_score}", "recovery_score_ratio", required_score, recovery_score)
                continue
            cluster.recovered_domestic_candidate = True
            cluster.top5_balance_adjustment_reason = (
                f"Recovered as Romanian near-miss domestic candidate (recovery_score={recovery_score}, leading_domestic_score={leading_domestic_score})"
            )
            recovery_pool.append(cluster)
        recovery_pool.sort(key=lambda cluster: (cluster.recovery_score, self._selection_adjusted_score(cluster)), reverse=True)
        recovered_limit = 2
        replacements = 0
        selected_ids = {cluster.cluster.cluster_id for cluster in selected}
        for candidate in recovery_pool:
            if replacements >= recovered_limit or candidate.cluster.cluster_id in selected_ids:
                continue
            weak_external = [
                cluster for cluster in selected
                if self._dominant_national_bucket(cluster) in {"external_direct_impact", "off_target"}
                and self._selection_adjusted_score(cluster) <= self._selection_adjusted_score(candidate) + 8.0
            ]
            weak_external.sort(key=lambda cluster: (self._selection_adjusted_score(cluster), cluster.external_penalty_applied))
            if len(selected) < max_stories:
                selected.append(candidate)
                selected_ids.add(candidate.cluster.cluster_id)
                replacements += 1
                continue
            if weak_external:
                outgoing = weak_external[0]
                selected = [candidate if item.cluster.cluster_id == outgoing.cluster.cluster_id else item for item in selected]
                selected_ids.discard(outgoing.cluster.cluster_id)
                selected_ids.add(candidate.cluster.cluster_id)
                replacements += 1
        return selected[:max_stories]


    def _enforce_local_geography_diversity_cap(
        self,
        selected: list[ScoredStoryCluster],
        ordered_clusters: list[ScoredStoryCluster],
        max_stories: int,
    ) -> list[ScoredStoryCluster]:
        if not selected or not any(cluster.editorial_profile_used == "local" for cluster in ordered_clusters):
            return selected[:max_stories]
        geography_cap = 2
        geography_counts = Counter(
            (cluster.local_county_tag or cluster.geographic_signal_detected)
            for cluster in selected
            if (cluster.local_county_tag or cluster.geographic_signal_detected)
        )
        if not any(count > geography_cap for count in geography_counts.values()):
            return selected[:max_stories]

        selected_ids = {cluster.cluster.cluster_id for cluster in selected}
        replacement_pool = [
            cluster for cluster in ordered_clusters
            if cluster.cluster.cluster_id not in selected_ids
        ]
        replacement_pool.sort(key=self._selection_sort_key, reverse=True)
        adjusted_selected = sorted(selected, key=self._selection_sort_key, reverse=True)

        for geography_tag, count in list(geography_counts.items()):
            if not geography_tag or count <= geography_cap:
                continue
            geography_members = [
                cluster for cluster in adjusted_selected
                if (cluster.local_county_tag or cluster.geographic_signal_detected) == geography_tag
            ]
            for outgoing in geography_members[geography_cap:]:
                adjusted_selected = [
                    cluster for cluster in adjusted_selected
                    if cluster.cluster.cluster_id != outgoing.cluster.cluster_id
                ]
                selected_ids.discard(outgoing.cluster.cluster_id)
                geography_counts[geography_tag] -= 1

                replacement_index = next(
                    (
                        index for index, candidate in enumerate(replacement_pool)
                        if not (candidate.local_county_tag or candidate.geographic_signal_detected)
                        or geography_counts[(candidate.local_county_tag or candidate.geographic_signal_detected)] < geography_cap
                    ),
                    None,
                )
                if replacement_index is None:
                    continue
                incoming = replacement_pool.pop(replacement_index)
                incoming.top5_balance_adjustment_reason = (
                    incoming.top5_balance_adjustment_reason
                    or f"Selected under local geography diversity cap replacing '{outgoing.cluster.representative_title}'"
                )
                adjusted_selected.append(incoming)
                adjusted_selected = sorted(adjusted_selected, key=self._selection_sort_key, reverse=True)
                selected_ids.add(incoming.cluster.cluster_id)
                incoming_tag = incoming.local_county_tag or incoming.geographic_signal_detected
                if incoming_tag:
                    geography_counts[incoming_tag] += 1

        return adjusted_selected[:max_stories]


    def _enforce_story_family_diversity_cap(
        self,
        selected: list[ScoredStoryCluster],
        ordered_clusters: list[ScoredStoryCluster],
        max_stories: int,
    ) -> list[ScoredStoryCluster]:
        family_cap = 2
        family_counts = Counter(
            cluster.story_family_id
            for cluster in selected
            if cluster.story_family_id
        )
        if not any(count > family_cap for count in family_counts.values()):
            return selected[:max_stories]

        selected_ids = {cluster.cluster.cluster_id for cluster in selected}
        replacement_pool = [
            cluster for cluster in ordered_clusters
            if cluster.cluster.cluster_id not in selected_ids
        ]
        replacement_pool.sort(key=self._selection_sort_key, reverse=True)
        adjusted_selected = sorted(selected, key=self._selection_sort_key, reverse=True)

        for family_id, count in list(family_counts.items()):
            if not family_id or count <= family_cap:
                continue
            family_members = [cluster for cluster in adjusted_selected if cluster.story_family_id == family_id]
            for outgoing in family_members[family_cap:]:
                adjusted_selected = [
                    cluster for cluster in adjusted_selected
                    if cluster.cluster.cluster_id != outgoing.cluster.cluster_id
                ]
                selected_ids.discard(outgoing.cluster.cluster_id)
                family_counts[family_id] -= 1

                replacement_index = next(
                    (
                        index for index, candidate in enumerate(replacement_pool)
                        if not candidate.story_family_id or family_counts[candidate.story_family_id] < family_cap
                    ),
                    None,
                )
                if replacement_index is None:
                    continue
                incoming = replacement_pool.pop(replacement_index)
                incoming.top5_balance_adjustment_reason = (
                    incoming.top5_balance_adjustment_reason
                    or f"Selected under story-family diversity cap replacing '{outgoing.cluster.representative_title}'"
                )
                adjusted_selected.append(incoming)
                adjusted_selected = sorted(adjusted_selected, key=self._selection_sort_key, reverse=True)
                selected_ids.add(incoming.cluster.cluster_id)
                if incoming.story_family_id:
                    family_counts[incoming.story_family_id] += 1

        return adjusted_selected[:max_stories]

    def _apply_soft_external_cap(
        self,
        selected: list[ScoredStoryCluster],
        ordered_clusters: list[ScoredStoryCluster],
        max_stories: int,
    ) -> list[ScoredStoryCluster]:
        if not self._is_all_national_input(ordered_clusters):
            return selected
        domestic_count = sum(1 for cluster in ordered_clusters if self._dominant_national_bucket(cluster) == "domestic_hard_news")
        if domestic_count >= 3:
            external_cap = 1
        elif domestic_count == 2:
            external_cap = 2
        else:
            return selected
        external_selected = [cluster for cluster in selected if self._dominant_national_bucket(cluster) == "external_direct_impact"]
        if len(external_selected) <= external_cap:
            return selected
        selected_ids = {cluster.cluster.cluster_id for cluster in selected}
        replacement_pool = [
            cluster for cluster in ordered_clusters
            if cluster.cluster.cluster_id not in selected_ids
            and self._dominant_national_bucket(cluster) != "external_direct_impact"
        ]
        replacement_pool.sort(key=self._selection_sort_key, reverse=True)
        for outgoing in sorted(external_selected, key=self._selection_sort_key)[: max(0, len(external_selected) - external_cap)]:
            if not replacement_pool:
                break
            incoming = replacement_pool.pop(0)
            incoming.top5_balance_adjustment_reason = (
                incoming.top5_balance_adjustment_reason
                or f"Selected under soft external cap replacing '{outgoing.cluster.representative_title}'"
            )
            selected = [incoming if item.cluster.cluster_id == outgoing.cluster.cluster_id else item for item in selected]
            selected_ids.discard(outgoing.cluster.cluster_id)
            selected_ids.add(incoming.cluster.cluster_id)
        return selected[:max_stories]

    def _cluster_text(self, cluster: ScoredStoryCluster) -> str:
        titles = " ".join(member.title for member in cluster.cluster.member_articles)
        urls = " ".join(member.url for member in cluster.cluster.member_articles)
        sources = " ".join(member.source for member in cluster.cluster.member_articles)
        return self._normalize_text(
            f"{cluster.cluster.representative_title} {titles} {urls} {sources}"
        )

    def _normalize_text(self, text: str) -> str:
        lowered = text.lower()
        lowered = lowered.replace("-", " ").replace("_", " ").replace("/", " ")
        return re.sub(r"\s+", " ", lowered).strip()

    def _is_commentary_like(self, cluster: ScoredStoryCluster) -> bool:
        title = cluster.cluster.representative_title.lower()
        return any(term in title for term in self.commentary_like_title_terms)


    def _is_soft_news_cluster(self, cluster: ScoredStoryCluster) -> bool:
        categories = self._cluster_categories(cluster)
        if "local" in self._cluster_scopes(cluster):
            return False
        return any(category in {"sport", "entertainment", "lifestyle"} for category in categories)

    def _is_placeholder_headline(self, title: str) -> bool:
        normalized = self._normalize_text(title)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return bool(self.placeholder_headline_pattern.fullmatch(normalized))

    def _build_decision(
        self,
        cluster: ScoredStoryCluster,
        status: str,
        reason: str,
        topic_label: str,
        domain_label: str,
        geography_label: str,
        regional_relevance: str,
        source_labels: list[str],
        preference_influence_used: bool,
        preference_influence_summary: str | None,
        regional_preference_used: bool,
        regional_preference_summary: str | None,
    ) -> StorySelectionDecision:
        explanation = self._decision_explanation(
            cluster=cluster,
            status=status,
            reason=reason,
            topic_label=topic_label,
            domain_label=domain_label,
            geography_label=geography_label,
            regional_relevance=regional_relevance,
            source_labels=source_labels,
            preference_influence_used=preference_influence_used,
            preference_influence_summary=preference_influence_summary,
            regional_preference_used=regional_preference_used,
            regional_preference_summary=regional_preference_summary,
        )
        return StorySelectionDecision(
            cluster_id=cluster.cluster.cluster_id,
            status=status,
            reason=reason,
            score_total=cluster.score_total,
            topic_label=topic_label,
            domain_label=domain_label,
            geography_label=geography_label,
            regional_relevance=regional_relevance,
            source_labels=source_labels,
            preference_influence_used=preference_influence_used,
            preference_influence_summary=preference_influence_summary,
            regional_preference_used=regional_preference_used,
            regional_preference_summary=regional_preference_summary,
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
        regional_relevance: str,
        source_labels: list[str],
        preference_influence_used: bool,
        preference_influence_summary: str | None,
        regional_preference_used: bool,
        regional_preference_summary: str | None,
    ) -> str:
        title = cluster.cluster.representative_title
        sources = ", ".join(source_labels) or "unknown source"
        preference_clause = ""
        if preference_influence_used and preference_influence_summary:
            preference_clause = f" Preference influence: {preference_influence_summary}"
        regional_clause = ""
        if regional_preference_used and regional_preference_summary:
            regional_clause = f" Regional preference: {regional_preference_summary}"

        if status == "selected":
            return (
                f"Selected '{title}' because it cleared the score threshold with {cluster.score_total} points "
                f"and fit the current mix for topic '{topic_label}', domain '{domain_label}', geography '{geography_label}', "
                f"regional relevance '{regional_relevance}' across sources {sources}."
                f"{preference_clause}{regional_clause}"
            )

        reason_map = {
            "below_minimum_score_threshold": "its score was below the minimum editorial threshold",
            "low_value_headline_cluster": "its headline pattern looked too low-value or SEO-style for bulletin inclusion",
            "english_heavy_headline_cluster": "its headline remained too English-heavy for the default Romanian bulletin",
            "low_priority_source_cluster": "its source priority was too low for inclusion without local relevance",
            "low_editorial_fit_cluster": "its source category, scope, and headline quality did not clear the editorial-fit bar",
            "soft_news_cluster_below_editorial_bar": "it was a soft-news cluster that did not clear the higher editorial-fit bar",
            "placeholder_headline_cluster": "its representative title was a section label or placeholder, not a usable story headline",
            "non_hard_news_national_cluster": "it belonged to a non-hard-news category that is excluded from national hard-news selection",
            "selection_limit_reached": "the candidate set had already reached the story limit",
            "rejected_by_topic_diversity_soft_cap": "a similar-topic cluster with a close score had already been kept",
            "rejected_by_source_diversity_soft_cap": "other close-scoring clusters already represented the same source mix",
            "commentary_like_cluster_below_editorial_bar": "its title looked commentary-like and it did not clear the higher bar for inclusion",
            "rejected_by_editorial_preferences_soft_target": "a near-tie cluster better matched the requested editorial preferences",
            "single_source_cluster_without_local_relevance": "it was supported by only one source and did not have clear local relevance",
            "missing_local_geographic_signal": "it did not show a county, city, or locality signal strong enough for the local bulletin",
        }
        detail = reason_map.get(reason, reason)
        return (
            f"Rejected '{title}' because {detail}. The cluster scored {cluster.score_total} points, "
            f"topic '{topic_label}', domain '{domain_label}', geography '{geography_label}', regional relevance '{regional_relevance}', "
            f"sources {sources}.{preference_clause}{regional_clause}"
        )

    def _build_selection_explanation(
        self,
        selected: list[ScoredStoryCluster],
        rejected: list[ScoredStoryCluster],
        stats: StorySelectionStats,
        editorial_preferences: EditorialPreferenceProfile | None,
        personalization: UserPersonalization | None,
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
        if editorial_preferences is not None and not editorial_preferences.is_neutral():
            preference_note = (
                "Preferences were applied conservatively as soft near-tie signals for geography and domain mix, "
                "without overriding clearly stronger stories."
            )
        regional_note = ""
        if self._regional_preference_applies(editorial_preferences, personalization):
            regional_note = (
                f" Regional local matching was also available as a county or region-first soft signal for "
                f"'{personalization.local_editorial_anchor()}'."
            )
        return (
            f"Selected {stats.selected_count} of {stats.total_input_clusters} scored clusters using a "
            f"minimum score of {stats.minimum_score_threshold}, a minimum of {self.minimum_unique_sources} unique source(s) for normal stories, "
            f"and an anchor preference of {self.anchor_min_unique_sources}+ unique sources for Story 1. "
            f"Top selected titles: {top_titles}. {preference_note}{regional_note}"
        )
