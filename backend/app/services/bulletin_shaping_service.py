from __future__ import annotations

from app.models.bulletin_shaping import BulletinShapingDecision, BulletinShapingResult
from app.models.story_score import ScoredStoryCluster


class BulletinShapingService:
    def shape_selected_clusters(
        self,
        selected_clusters: list[ScoredStoryCluster],
        profile_name: str,
    ) -> BulletinShapingResult:
        if not selected_clusters:
            return BulletinShapingResult(
                profile_name=profile_name,
                ordered_clusters=[],
                lead_cluster_id=None,
                shaping_explanation="No selected stories were available for editorial shaping.",
                decisions=[],
            )

        remaining = list(selected_clusters)
        lead = max(remaining, key=lambda cluster: self._lead_priority(cluster, profile_name))
        remaining.remove(lead)

        ordered = [lead]
        decisions = [
            BulletinShapingDecision(
                position=1,
                cluster_id=lead.cluster.cluster_id,
                headline=lead.cluster.representative_title,
                topic_bucket=self._topic_bucket(lead, profile_name),
                story_family_id=lead.story_family_id,
                decision_reason=self._lead_reason(lead, profile_name),
            )
        ]

        while remaining:
            candidate = min(
                remaining,
                key=lambda cluster: self._ordering_key(ordered, cluster, profile_name),
            )
            remaining.remove(candidate)
            ordered.append(candidate)
            decisions.append(
                BulletinShapingDecision(
                    position=len(ordered),
                    cluster_id=candidate.cluster.cluster_id,
                    headline=candidate.cluster.representative_title,
                    topic_bucket=self._topic_bucket(candidate, profile_name),
                    story_family_id=candidate.story_family_id,
                    decision_reason=self._placement_reason(ordered[:-1], candidate, profile_name),
                )
            )

        explanation = self._build_explanation(profile_name, decisions, lead)
        return BulletinShapingResult(
            profile_name=profile_name,
            ordered_clusters=ordered,
            lead_cluster_id=lead.cluster.cluster_id,
            shaping_explanation=explanation,
            decisions=decisions,
        )

    def _lead_priority(self, cluster: ScoredStoryCluster, profile_name: str) -> tuple[float, float, str]:
        base = cluster.score_total or 0.0
        domestic_score = float(getattr(cluster, "domestic_purity_score", 0.0) or 0.0) * 12
        family_run_count = float(getattr(cluster, "family_run_count", 0) or 0) * 0.35
        lifecycle = float(getattr(cluster, "family_lifecycle_boost", 0.0) or 0.0) * 12
        romanian_sources = float(getattr(cluster, "romanian_source_count", 0) or 0) * 1.5
        multi_source_bonus = float(getattr(cluster, "romanian_multi_source_bonus_applied", 0.0) or 0.0) * 20
        local_relevance = float(getattr(cluster, "local_relevance_boost", 0.0) or 0.0) * 12
        national_bucket = self._dominant_national_bucket(cluster)

        lead_score = base
        bucket_priority = 1
        if profile_name == "national_ro":
            lead_score += domestic_score + family_run_count + lifecycle + romanian_sources + multi_source_bonus
            if national_bucket == "domestic_hard_news":
                bucket_priority = 3
                lead_score += 14
            elif national_bucket == "external_direct_impact":
                bucket_priority = 2
                lead_score += 5
            elif national_bucket == "off_target":
                bucket_priority = 1
                lead_score -= 16
            else:
                bucket_priority = 1
            return (bucket_priority, round(lead_score, 3), base, cluster.cluster.cluster_id)
        if profile_name == "local":
            lead_score += local_relevance + family_run_count + lifecycle
        else:
            lead_score += family_run_count + lifecycle + multi_source_bonus

        return (round(lead_score, 3), base, cluster.cluster.cluster_id)

    def _ordering_key(
        self,
        ordered: list[ScoredStoryCluster],
        candidate: ScoredStoryCluster,
        profile_name: str,
    ) -> tuple[float, float, float, float, str]:
        previous = ordered[-1]
        previous_topic = self._topic_bucket(previous, profile_name)
        candidate_topic = self._topic_bucket(candidate, profile_name)
        family_penalty = 2.0 if previous.story_family_id and previous.story_family_id == candidate.story_family_id else 0.0
        topic_penalty = 1.5 if previous_topic == candidate_topic else 0.0

        recent_family_penalty = 0.0
        recent_topic_penalty = 0.0
        if len(ordered) >= 2:
            second_previous = ordered[-2]
            if second_previous.story_family_id and second_previous.story_family_id == candidate.story_family_id:
                recent_family_penalty = 0.5
            if self._topic_bucket(second_previous, profile_name) == candidate_topic:
                recent_topic_penalty = 0.5

        editorial_strength = candidate.score_total or 0.0
        editorial_strength += float(getattr(candidate, "family_run_count", 0) or 0) * 0.15
        editorial_strength += float(getattr(candidate, "family_lifecycle_boost", 0.0) or 0.0) * 6
        editorial_strength += float(getattr(candidate, "romanian_source_count", 0) or 0) * 0.8
        editorial_strength += float(getattr(candidate, "romanian_multi_source_bonus_applied", 0.0) or 0.0) * 10
        if profile_name == "national_ro":
            national_bucket = self._dominant_national_bucket(candidate)
            if national_bucket == "domestic_hard_news":
                editorial_strength += 6
            elif national_bucket == "external_direct_impact":
                editorial_strength += 2
            elif national_bucket == "off_target":
                editorial_strength -= 8

        return (
            family_penalty,
            topic_penalty,
            recent_family_penalty,
            recent_topic_penalty,
            -round(editorial_strength, 3),
            candidate.cluster.cluster_id,
        )

    def _lead_reason(self, cluster: ScoredStoryCluster, profile_name: str) -> str:
        reasons: list[str] = [f"score_total={cluster.score_total or 0.0:.2f}"]
        if profile_name == "national_ro":
            reasons.append(f"domestic_purity={getattr(cluster, 'domestic_purity_score', 0.0):.2f}")
            reasons.append(f"family_run_count={getattr(cluster, 'family_run_count', 0)}")
            reasons.append(f"lifecycle_boost={getattr(cluster, 'family_lifecycle_boost', 0.0):.2f}")
            reasons.append(f"romanian_source_count={getattr(cluster, 'romanian_source_count', 0)}")
            reasons.append(f"national_bucket={self._dominant_national_bucket(cluster) or 'none'}")
        elif profile_name == "local":
            reasons.append(f"local_relevance_boost={getattr(cluster, 'local_relevance_boost', 0.0):.2f}")
            reasons.append(f"county={getattr(cluster, 'local_county_tag', None) or 'none'}")
        else:
            reasons.append(f"family_run_count={getattr(cluster, 'family_run_count', 0)}")
            reasons.append(f"lifecycle_boost={getattr(cluster, 'family_lifecycle_boost', 0.0):.2f}")
        return "lead_story_selected: " + ", ".join(reasons)

    def _placement_reason(
        self,
        ordered: list[ScoredStoryCluster],
        candidate: ScoredStoryCluster,
        profile_name: str,
    ) -> str:
        previous = ordered[-1]
        reasons: list[str] = []
        if previous.story_family_id and previous.story_family_id == candidate.story_family_id:
            reasons.append("no_family_alternative_available")
        else:
            reasons.append("family_separation_applied")
        if self._topic_bucket(previous, profile_name) == self._topic_bucket(candidate, profile_name):
            reasons.append("topic_repeat_unavoidable")
        else:
            reasons.append("topic_diversity_applied")
        if abs((previous.score_total or 0.0) - (candidate.score_total or 0.0)) <= 4.0:
            reasons.append(
                f"confidence_tiebreak=romanian_source_count:{getattr(candidate, 'romanian_source_count', 0)},family_run_count:{getattr(candidate, 'family_run_count', 0)}"
            )
        return "; ".join(reasons)

    def _build_explanation(
        self,
        profile_name: str,
        decisions: list[BulletinShapingDecision],
        lead: ScoredStoryCluster,
    ) -> str:
        reorders = max(len(decisions) - 1, 0)
        return (
            f"Bulletin shaping used profile '{profile_name}' across {len(decisions)} selected stories. "
            f"Lead story chosen: '{lead.cluster.representative_title}' ({self._lead_reason(lead, profile_name)}). "
            f"Applied deterministic family separation, topic diversity ordering, and confidence-aware tie-breaking across {reorders} later placements."
        )

    def _topic_bucket(self, cluster: ScoredStoryCluster, profile_name: str) -> str:
        national_bucket = self._dominant_national_bucket(cluster)
        if profile_name == "national_ro":
            if national_bucket == "external_direct_impact":
                return "international_impact"
            if national_bucket == "off_target":
                return "general"

        hints = set(getattr(cluster, "cluster_event_family_hints", []) or [])
        impact_hits = set(getattr(cluster, "romania_impact_evidence_hits", []) or [])
        title = (cluster.cluster.representative_title or "").lower()
        if hints & {"justice_procedure", "romanian_justice", "romanian_justice_case", "romanian_anti_corruption_case", "romanian_prosecutor_decision", "romanian_high_court_decision"} or impact_hits & {"dna", "diicot", "iccj", "parchet", "procuror", "rechizitoriu", "arest", "arestari", "perchezitii"}:
            return "justice"
        if hints & {"fiscal_policy_ro", "economic_policy_ro", "romanian_budget_fiscal", "romanian_fiscal_policy_2026", "romanian_economic_policy", "romanian_eu_funds_loss"} or impact_hits & {"anaf", "bnr", "taxe", "tva", "buget", "deficit", "impozit"}:
            return "economy"
        if hints & {"public_safety_local_admin", "romanian_infrastructure_issue"} or any(term in title for term in ("petarde", "artificii", "incendiu", "accident", "trafic")):
            return "public_safety"
        if hints & {"romanian_domestic_politics", "government_coalition", "romanian_major_policy_decision"} or any(term in title for term in ("guvern", "parlament", "coalitie", "consiliul general", "primar")):
            return "politics_government"
        if profile_name == "national_ro" and national_bucket == "external_direct_impact":
            return "international_impact"
        if profile_name == "local":
            return "local_public_interest"
        categories = {member.source_category or "general" for member in cluster.cluster.member_articles}
        if "economy" in categories:
            return "economy"
        return "general"

    def _dominant_national_bucket(self, cluster: ScoredStoryCluster) -> str | None:
        buckets: dict[str, int] = {}
        for member in cluster.cluster.member_articles:
            if not member.national_preference_bucket:
                continue
            buckets[member.national_preference_bucket] = buckets.get(member.national_preference_bucket, 0) + 1
        if not buckets:
            return None
        return max(sorted(buckets), key=lambda bucket: buckets[bucket])
