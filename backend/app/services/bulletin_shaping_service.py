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
                radio_priority_score=self._radio_priority_score(lead, profile_name),
                ordering_signals=self._ordering_signals(lead, profile_name),
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
                    radio_priority_score=self._radio_priority_score(candidate, profile_name),
                    ordering_signals=self._ordering_signals(candidate, profile_name),
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
        radio_priority = self._radio_priority_score(cluster, profile_name)

        lead_score = base
        bucket_priority = 1
        dominant_scope = self._dominant_scope(cluster)
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
        if profile_name == "generalist":
            lead_score += domestic_score + local_relevance + family_run_count + lifecycle + romanian_sources + multi_source_bonus + (radio_priority * 2.4)
            europe_romania_impact = float(
                getattr(getattr(cluster, "score_breakdown", None), "europe_romania_impact", None).contribution
                if getattr(getattr(cluster, "score_breakdown", None), "europe_romania_impact", None)
                else 0.0
            )
            if local_relevance > 0 or dominant_scope == "local":
                bucket_priority = 5
                lead_score += 12
            elif dominant_scope == "national" and self._has_romania_focus(cluster):
                bucket_priority = 4
                lead_score += 12
            elif dominant_scope == "national" and national_bucket == "domestic_hard_news":
                bucket_priority = 3
                lead_score += 10
            elif dominant_scope == "national":
                bucket_priority = 2
                lead_score += 4
            elif dominant_scope == "international" and (national_bucket == "external_direct_impact" or europe_romania_impact >= 4.0):
                bucket_priority = 2
                lead_score += 4
            elif dominant_scope == "international":
                bucket_priority = 1
                lead_score -= 4
            if local_relevance > 0:
                lead_score += 4
            if national_bucket == "domestic_hard_news":
                lead_score += 6
            elif national_bucket == "external_direct_impact":
                lead_score += 2
            elif national_bucket == "off_target":
                lead_score -= 6
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
    ) -> tuple[float, float, float, float, float, str]:
        previous = ordered[-1]
        candidate_scope = self._dominant_scope(candidate)
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

        early_scope_penalty = 0.0
        scope_run_penalty = 0.0
        opening_hook_bonus = 0.0
        if profile_name == "generalist":
            target_position = len(ordered) + 1
            if target_position <= 3 and candidate_scope == "international":
                early_scope_penalty = 2.5
            elif target_position <= 5 and candidate_scope == "international":
                early_scope_penalty = 1.5
            recent_scopes = [self._dominant_scope(item) for item in ordered[-2:]] if len(ordered) >= 2 else [self._dominant_scope(previous)]
            if recent_scopes and all(scope == candidate_scope for scope in recent_scopes):
                scope_run_penalty = 1.2 if candidate_scope == "local" else 0.9
            if target_position <= 3:
                covered_tags = set().union(*(self._opening_hook_tags(item) for item in ordered[: target_position - 1])) if ordered else set()
                candidate_tags = self._opening_hook_tags(candidate)
                focus_tags = {"health", "money", "traffic", "safety"}
                if len(covered_tags & focus_tags) < 2:
                    if candidate_tags & (focus_tags - covered_tags):
                        opening_hook_bonus = -1.6
                    else:
                        opening_hook_bonus = 1.6

        radio_priority = self._radio_priority_score(candidate, profile_name)
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
        elif profile_name == "generalist":
            dominant_scope = self._dominant_scope(candidate)
            national_bucket = self._dominant_national_bucket(candidate)
            if dominant_scope in {"national", "local"}:
                editorial_strength += 4
            elif dominant_scope == "international":
                editorial_strength += 1
            if getattr(candidate, "local_relevance_boost", 0.0) > 0:
                editorial_strength += 3
            if national_bucket == "domestic_hard_news":
                editorial_strength += 4
            elif national_bucket == "external_direct_impact":
                editorial_strength += 2
            elif national_bucket == "off_target":
                editorial_strength -= 4

        return (
            family_penalty,
            topic_penalty,
            recent_family_penalty,
            recent_topic_penalty,
            early_scope_penalty,
            scope_run_penalty,
            opening_hook_bonus,
            -round(radio_priority, 3),
            -round(editorial_strength, 3),
            candidate.cluster.cluster_id,
        )

    def _opening_hook_tags(self, cluster: ScoredStoryCluster) -> set[str]:
        title = (cluster.cluster.representative_title or "").lower()
        hits = set(getattr(cluster, "romania_impact_evidence_hits", []) or [])
        tags: set[str] = set()
        if any(term in title for term in ("spital", "urgente", "sanat", "avc")) or hits & {"spital", "urgente", "sanatate"}:
            tags.add("health")
        if any(term in title for term in ("preturi", "facturi", "energie", "alimente", "tva", "buget")) or hits & {"preturi", "facturi", "energie", "buget", "tva", "alimente"}:
            tags.add("money")
        if any(term in title for term in ("trafic", "drum", "pasaj", "transport", "lucrari", "tren")) or hits & {"trafic", "drum", "transport"}:
            tags.add("traffic")
        if any(term in title for term in ("isu", "incend", "siguranta", "controale", "nato", "securitate")) or hits & {"incend", "isu", "siguranta", "securitate"}:
            tags.add("safety")
        return tags

    def _lead_reason(self, cluster: ScoredStoryCluster, profile_name: str) -> str:
        reasons: list[str] = [f"score_total={cluster.score_total or 0.0:.2f}", f"radio_priority={self._radio_priority_score(cluster, profile_name):.2f}"]
        if profile_name == "national_ro":
            reasons.append(f"domestic_purity={getattr(cluster, 'domestic_purity_score', 0.0):.2f}")
            reasons.append(f"family_run_count={getattr(cluster, 'family_run_count', 0)}")
            reasons.append(f"lifecycle_boost={getattr(cluster, 'family_lifecycle_boost', 0.0):.2f}")
            reasons.append(f"romanian_source_count={getattr(cluster, 'romanian_source_count', 0)}")
            reasons.append(f"national_bucket={self._dominant_national_bucket(cluster) or 'none'}")
        elif profile_name == "generalist":
            reasons.append(f"dominant_scope={self._dominant_scope(cluster)}")
            reasons.append(f"romania_focus={self._has_romania_focus(cluster)}")
            reasons.append(f"national_bucket={self._dominant_national_bucket(cluster) or 'none'}")
            reasons.append(f"local_relevance_boost={getattr(cluster, 'local_relevance_boost', 0.0):.2f}")
            reasons.append(f"romanian_source_count={getattr(cluster, 'romanian_source_count', 0)}")
            reasons.append(f"family_run_count={getattr(cluster, 'family_run_count', 0)}")
            reasons.append(f"lifecycle_boost={getattr(cluster, 'family_lifecycle_boost', 0.0):.2f}")
        elif profile_name == "local":
            reasons.append(f"local_relevance_boost={getattr(cluster, 'local_relevance_boost', 0.0):.2f}")
            reasons.append(f"county={getattr(cluster, 'local_county_tag', None) or 'none'}")
        else:
            reasons.append(f"family_run_count={getattr(cluster, 'family_run_count', 0)}")
            reasons.append(f"lifecycle_boost={getattr(cluster, 'family_lifecycle_boost', 0.0):.2f}")
        top_signals = self._top_signal_labels(self._ordering_signals(cluster, profile_name))
        if top_signals:
            reasons.append(f"signals={','.join(top_signals)}")
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
        reasons.append(f"radio_priority={self._radio_priority_score(candidate, profile_name):.2f}")
        top_signals = self._top_signal_labels(self._ordering_signals(candidate, profile_name))
        if top_signals:
            reasons.append(f"impact_order={','.join(top_signals)}")
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

    def _ordering_signals(self, cluster: ScoredStoryCluster, profile_name: str) -> dict[str, float]:
        if profile_name != "generalist":
            return {}
        title = (cluster.cluster.representative_title or "").lower()
        hints = set(getattr(cluster, "cluster_event_family_hints", []) or [])
        impact_hits = set(getattr(cluster, "romania_impact_evidence_hits", []) or [])
        dominant_scope = self._dominant_scope(cluster)
        local_relevance = float(getattr(cluster, "local_relevance_boost", 0.0) or 0.0)
        europe_romania_impact = float(
            getattr(getattr(cluster, "score_breakdown", None), "europe_romania_impact", None).contribution
            if getattr(getattr(cluster, "score_breakdown", None), "europe_romania_impact", None)
            else 0.0
        )
        recency = float(
            getattr(getattr(cluster, "score_breakdown", None), "recency", None).contribution
            if getattr(getattr(cluster, "score_breakdown", None), "recency", None)
            else 0.0
        )

        def hits(*terms: str) -> bool:
            return any(term in title for term in terms) or any(term in impact_hits for term in terms)

        signals = {
            "direct_listener_impact_score": 3.0 if local_relevance > 0.4 or hits("facturi", "preturi", "trafic", "spital", "burse", "catalog") else 1.5 if dominant_scope in {"local", "national"} else 0.5,
            "urgency_score": min(3.0, recency / 2.4) + (1.2 if hits("urgent", "urgente", "restrictii", "controale", "incepe", "intra") else 0.0),
            "emotional_proximity_score": 2.5 if dominant_scope == "local" else 1.4 if local_relevance > 0 else 0.6,
            "cost_of_living_score": 3.2 if hits("energie", "facturi", "preturi", "alimente", "seceta", "tva", "anaf", "buget") else 0.0,
            "health_and_safety_score": 3.4 if hits("spital", "urgente", "incend", "isu", "siguranta", "sanat") else 0.0,
            "traffic_and_daily_life_score": 3.0 if hits("trafic", "pasaj", "drum", "transport", "lucrari", "statii", "catalog", "burse") else 0.0,
            "romania_relevance_score": max(0.0, europe_romania_impact) + (2.0 if self._has_romania_focus(cluster) else 0.0),
            "locality_proximity_score": (local_relevance * 4.0) + (2.0 if dominant_scope == "local" else 0.0),
            "long_term_vs_immediate_penalty": 1.8 if hits("treptat", "de anul viitor", "cipuri", "exporturile") else 0.8 if hits("schema", "proiect") else 0.0,
        }
        if hints & {"public_safety_local_admin", "romanian_infrastructure_issue"}:
            signals["health_and_safety_score"] += 1.0
        if hints & {"fiscal_policy_ro", "economic_policy_ro", "romanian_budget_fiscal"}:
            signals["cost_of_living_score"] += 1.0
        if hints & {"justice_procedure", "romanian_justice", "romanian_anti_corruption_case"}:
            signals["direct_listener_impact_score"] += 0.6
        return {key: round(value, 2) for key, value in signals.items()}

    def _radio_priority_score(self, cluster: ScoredStoryCluster, profile_name: str) -> float:
        if profile_name != "generalist":
            return round(cluster.score_total or 0.0, 2)
        signals = self._ordering_signals(cluster, profile_name)
        score = (
            signals.get("direct_listener_impact_score", 0.0) * 1.7
            + signals.get("urgency_score", 0.0) * 1.4
            + signals.get("health_and_safety_score", 0.0) * 1.8
            + signals.get("cost_of_living_score", 0.0) * 1.5
            + signals.get("traffic_and_daily_life_score", 0.0) * 1.35
            + signals.get("romania_relevance_score", 0.0) * 1.15
            + signals.get("locality_proximity_score", 0.0) * 1.2
            + signals.get("emotional_proximity_score", 0.0) * 0.9
            - signals.get("long_term_vs_immediate_penalty", 0.0) * 1.2
        )
        return round(score, 2)

    def _top_signal_labels(self, signals: dict[str, float]) -> list[str]:
        ranked = sorted(((label, value) for label, value in signals.items() if value > 0), key=lambda item: item[1], reverse=True)
        return [label for label, _ in ranked[:3]]

    def _topic_bucket(self, cluster: ScoredStoryCluster, profile_name: str) -> str:
        national_bucket = self._dominant_national_bucket(cluster)
        dominant_scope = self._dominant_scope(cluster)
        if profile_name == "national_ro":
            if national_bucket == "external_direct_impact":
                return "international_impact"
            if national_bucket == "off_target":
                return "general"
        if profile_name == "generalist":
            if getattr(cluster, "local_relevance_boost", 0.0) > 0 or dominant_scope == "local":
                return "local_public_interest"
            if dominant_scope == "international":
                return "international_impact"

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


    def _has_romania_focus(self, cluster: ScoredStoryCluster) -> bool:
        title = (cluster.cluster.representative_title or "").lower()
        romania_terms = (
            "romania", "roman", "guvern", "guvernul", "parlament", "presed", "minister", "anaf", "csat",
            "bucuresti", "capitala", "primar", "consiliul general", "romani", "romaniei"
        )
        if any(term in title for term in romania_terms):
            return True
        for member in cluster.cluster.member_articles:
            region = str(getattr(member, "source_region", "") or "").lower()
            if region in {"cluj", "iasi", "bucuresti", "timis", "constanta", "brasov", "prahova"}:
                return True
        return False

    def _dominant_national_bucket(self, cluster: ScoredStoryCluster) -> str | None:
        buckets: dict[str, int] = {}
        for member in cluster.cluster.member_articles:
            if not member.national_preference_bucket:
                continue
            buckets[member.national_preference_bucket] = buckets.get(member.national_preference_bucket, 0) + 1
        if not buckets:
            return None
        return max(sorted(buckets), key=lambda bucket: buckets[bucket])

    def _dominant_scope(self, cluster: ScoredStoryCluster) -> str:
        scopes: dict[str, int] = {}
        for member in cluster.cluster.member_articles:
            scope = member.source_scope or ("local" if member.is_local_source else "unknown")
            scopes[scope] = scopes.get(scope, 0) + 1
        if not scopes:
            return "unknown"
        return max(sorted(scopes), key=lambda scope: scopes[scope])

