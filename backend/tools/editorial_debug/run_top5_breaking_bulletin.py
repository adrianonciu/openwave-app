from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations
from pathlib import Path
import json
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.article_fetch import FetchedArticle
from app.services.editorial_pipeline_service import EditorialPipelineService
from run_top5_scope_selection import (
    _build_articles,
    _build_personalization,
    _cluster_signals,
    _serialize_candidate,
)

OUTPUT_DIR = BACKEND_ROOT / "debug_output"
TEXT_OUTPUT_PATH = OUTPUT_DIR / "top5_breaking_bulletin.txt"
JSON_OUTPUT_PATH = OUTPUT_DIR / "top5_breaking_bulletin.json"
ROMANIAN_SOURCE_COVERAGE_JSON_PATH = OUTPUT_DIR / "romanian_source_coverage.json"
ROMANIAN_SOURCE_COVERAGE_TEXT_PATH = OUTPUT_DIR / "romanian_source_coverage.txt"
ROMANIAN_CANDIDATE_POOL_AUDIT_JSON_PATH = OUTPUT_DIR / "romanian_candidate_pool_audit.json"

EXCLUDED_NATIONAL_CATEGORIES = {"sport", "entertainment", "lifestyle", "culture", "tv"}
PLACEHOLDER_HEADLINES = {"actualitate", "stiri", "live", "breaking", "updates", "context"}



JUSTICE_HINTS = {
    "romanian_justice",
    "romanian_justice_case",
    "romanian_prosecutor_decision",
    "romanian_high_court_decision",
    "romanian_anti_corruption_case",
}


def _justice_boost_reason(item: dict[str, object]) -> str:
    reasons: list[str] = []
    hints = [hint for hint in (item.get("cluster_event_family_hints") or []) if hint in JUSTICE_HINTS]
    if hints:
        reasons.append(hints[0])
    if item.get("recovered_domestic_candidate"):
        reasons.append("recovery")
    if (item.get("persistence_boost_applied") or 0.0) > 0:
        reasons.append("persistence")
    if hints and not item.get("recovered_domestic_candidate") and (item.get("persistence_boost_applied") or 0.0) <= 0:
        reasons.append("justice hint scoring")
    return " + ".join(reasons) or "justice hint scoring"


def _justice_entered_via(item: dict[str, object]) -> str:
    if item.get("recovered_domestic_candidate"):
        return "recovery"
    if (item.get("persistence_boost_applied") or 0.0) > 0:
        return "persistence"
    return "first_pass"


def _is_placeholder(title: str) -> bool:
    return (title or "").strip().lower() in PLACEHOLDER_HEADLINES


def _dominant_category(scored_cluster) -> str:
    categories = [member.source_category or "general" for member in scored_cluster.cluster.member_articles]
    return Counter(categories).most_common(1)[0][0] if categories else "general"


def _is_usable_breaking_candidate(scored_cluster, scope: str) -> bool:
    headline = (scored_cluster.cluster.representative_title or "").strip()
    if not headline or _is_placeholder(headline):
        return False
    category = _dominant_category(scored_cluster).lower()
    if scope == "national" and category in EXCLUDED_NATIONAL_CATEGORIES:
        return False
    if scope == "national":
        buckets = [member.national_preference_bucket for member in scored_cluster.cluster.member_articles if member.national_preference_bucket]
        dominant_bucket = Counter(buckets).most_common(1)[0][0] if buckets else None
        if dominant_bucket == "off_target":
            if getattr(scored_cluster, "recovered_domestic_candidate", False):
                return True
            domestic_purity = getattr(scored_cluster, "domestic_purity_score", 0.0)
            impact_hits = getattr(scored_cluster, "romania_impact_evidence_hits", []) or []
            title_only_boost = getattr(scored_cluster, "title_only_domestic_boost", 0.0)
            if domestic_purity < 0.4 and len(impact_hits) < 2 and title_only_boost <= 0:
                return False
    return True


def _breaking_entry(scored_cluster, article_by_url, clustering_service, rank: int) -> dict[str, object]:
    serialized = _serialize_candidate(scored_cluster, selection_status="selected")
    signals = _cluster_signals(scored_cluster, article_by_url, clustering_service)
    return {
        "rank": rank,
        "cluster_id": serialized["cluster_id"],
        "headline": serialized["top_headline"],
        "normalized_headline": signals["normalized_headline"],
        "source_list": serialized["source_list"],
        "unique_source_count": serialized["unique_source_count"],
        "event_family": signals["event_families"],
        "regional_bucket": signals["regional_buckets"],
        "freshness_score": serialized["freshness_score"],
        "final_score": serialized["final_score"],
        "domestic_purity_score": getattr(scored_cluster, "domestic_purity_score", 0.0),
        "romania_impact_evidence_hits": getattr(scored_cluster, "romania_impact_evidence_hits", []),
        "romanian_source_count": getattr(scored_cluster, "romanian_source_count", 0),
        "romanian_multi_source_bonus_applied": getattr(scored_cluster, "romanian_multi_source_bonus_applied", 0.0),
        "external_penalty_applied": getattr(scored_cluster, "external_penalty_applied", 0.0),
        "title_only_domestic_boost": getattr(scored_cluster, "title_only_domestic_boost", 0.0),
        "cluster_event_family_hints": getattr(scored_cluster, "cluster_event_family_hints", []),
        "domestic_vs_external_rank_reason": getattr(scored_cluster, "domestic_vs_external_rank_reason", None),
        "recovery_score": getattr(scored_cluster, "recovery_score", 0.0),
        "recovered_domestic_candidate": getattr(scored_cluster, "recovered_domestic_candidate", False),
        "persistence_boost_applied": getattr(scored_cluster, "persistence_boost_applied", 0.0),
        "top5_balance_adjustment_reason": getattr(scored_cluster, "top5_balance_adjustment_reason", None),
        "recovery_rejection_reason": getattr(scored_cluster, "recovery_rejection_reason", None),
        "failed_threshold_name": getattr(scored_cluster, "failed_threshold_name", None),
        "threshold_required_value": getattr(scored_cluster, "threshold_required_value", None),
        "candidate_current_value": getattr(scored_cluster, "candidate_current_value", None),
        "national_preference_bucket": Counter([member.national_preference_bucket for member in scored_cluster.cluster.member_articles if member.national_preference_bucket]).most_common(1)[0][0] if [member.national_preference_bucket for member in scored_cluster.cluster.member_articles if member.national_preference_bucket] else None,
        "attached_story_family": getattr(scored_cluster, "story_family_id", None),
        "family_attach_reason": getattr(scored_cluster, "family_attach_reason", None),
        "editorial_profile_used": getattr(scored_cluster, "editorial_profile_used", None),
        "profile_config_name": getattr(scored_cluster, "profile_config_name", None),
        "shared_core_path_used": getattr(scored_cluster, "shared_core_path_used", False),
        "family_first_seen": getattr(scored_cluster, "family_first_seen", None),
        "family_last_seen": getattr(scored_cluster, "family_last_seen", None),
        "family_run_count": getattr(scored_cluster, "family_run_count", 0),
        "family_age_hours": getattr(scored_cluster, "family_age_hours", 0.0),
        "family_lifecycle_boost": getattr(scored_cluster, "family_lifecycle_boost", 0.0),
        "geographic_signal_detected": getattr(scored_cluster, "geographic_signal_detected", None),
        "local_relevance_boost": getattr(scored_cluster, "local_relevance_boost", 0.0),
        "local_domain_signal_hits": getattr(scored_cluster, "local_domain_signal_hits", []),
        "local_county_tag": getattr(scored_cluster, "local_county_tag", None),
    }


def _pick_top5(selected_clusters: list, candidates: list, article_by_url, clustering_service, scope: str) -> list[dict[str, object]]:
    picked = []
    seen_ids = set()
    for cluster in selected_clusters:
        if not _is_usable_breaking_candidate(cluster, scope):
            continue
        picked.append(_breaking_entry(cluster, article_by_url, clustering_service, len(picked) + 1))
        seen_ids.add(cluster.cluster.cluster_id)
        if len(picked) == 5:
            return picked

    multi_source_fallback = [
        cluster for cluster in candidates
        if cluster.cluster.cluster_id not in seen_ids
        and _is_usable_breaking_candidate(cluster, scope)
        and len({member.source for member in cluster.cluster.member_articles}) >= 2
    ]
    single_source_fallback = [
        cluster for cluster in candidates
        if cluster.cluster.cluster_id not in seen_ids
        and _is_usable_breaking_candidate(cluster, scope)
        and len({member.source for member in cluster.cluster.member_articles}) < 2
    ]

    for cluster in [*multi_source_fallback, *single_source_fallback]:
        picked.append(_breaking_entry(cluster, article_by_url, clustering_service, len(picked) + 1))
        seen_ids.add(cluster.cluster.cluster_id)
        if len(picked) == 5:
            break
    return picked


def _representative_article(cluster, article_by_url: dict[str, FetchedArticle]) -> FetchedArticle | None:
    for member in cluster.cluster.member_articles:
        article = article_by_url.get(member.url)
        if article is not None:
            return article
    return None


def _cluster_named_entities(cluster, article_by_url: dict[str, FetchedArticle], clustering_service) -> list[str]:
    entities: set[str] = set()
    for member in cluster.cluster.member_articles:
        article = article_by_url.get(member.url)
        if article is None:
            continue
        signal = clustering_service._build_signals(clustering_service._normalize_article(article))
        entities.update(signal.entities)
    return sorted(entities)[:10]


def _cluster_similarity_score(cluster, article_by_url: dict[str, FetchedArticle], clustering_service) -> float:
    articles = []
    for member in cluster.cluster.member_articles:
        article = article_by_url.get(member.url)
        if article is not None:
            articles.append(article)
    if len(articles) < 2:
        return 0.0
    scores = []
    for left, right in combinations(articles, 2):
        decision = clustering_service.explain_pair(left, right)
        scores.append(clustering_service._decision_score(decision))
    return round(sum(scores) / len(scores), 3) if scores else 0.0



def _story_family_summary(scored_clusters: list) -> list[dict[str, object]]:
    families: dict[str, dict[str, object]] = {}
    for cluster in scored_clusters:
        family_id = getattr(cluster, "story_family_id", None)
        if not family_id:
            continue
        entry = families.setdefault(
            family_id,
            {
                "family_id": family_id,
                "story_count": 0,
                "sources": set(),
                "event_hints": set(),
            },
        )
        entry["story_count"] += 1
        entry["sources"].update(member.source for member in cluster.cluster.member_articles)
        entry["event_hints"].update(getattr(cluster, "cluster_event_family_hints", []) or [])
    payload = []
    for family_id, entry in families.items():
        payload.append(
            {
                "family_id": family_id,
                "stories": entry["story_count"],
                "sources": sorted(entry["sources"]),
                "event_hints": sorted(entry["event_hints"]),
                "first_seen": min((getattr(cluster, "family_first_seen", None) for cluster in scored_clusters if getattr(cluster, "story_family_id", None) == family_id), default=None),
                "last_seen": max((getattr(cluster, "family_last_seen", None) for cluster in scored_clusters if getattr(cluster, "story_family_id", None) == family_id), default=None),
                "run_count": max((getattr(cluster, "family_run_count", 0) for cluster in scored_clusters if getattr(cluster, "story_family_id", None) == family_id), default=0),
                "age_hours": max((getattr(cluster, "family_age_hours", 0.0) for cluster in scored_clusters if getattr(cluster, "story_family_id", None) == family_id), default=0.0),
            }
        )
    payload.sort(key=lambda item: (-item["stories"], -len(item["sources"]), item["family_id"]))
    return payload


def _write_romanian_source_coverage(source_coverage: dict[str, dict[str, object]], national_candidates: list, clustering_service) -> None:
    coverage_by_normalized_source = {
        clustering_service._normalize_source_identity(coverage["source_name"]): coverage
        for coverage in source_coverage.values()
        if coverage["source_scope"] == "national"
    }

    for cluster in national_candidates:
        source_ids_in_cluster: set[str] = set()
        for member in cluster.cluster.member_articles:
            normalized_member_source = clustering_service._normalize_source_identity(member.source)
            coverage = coverage_by_normalized_source.get(normalized_member_source)
            if coverage is not None:
                source_ids_in_cluster.add(coverage["source_id"])
        for source_id in source_ids_in_cluster:
            source_coverage[source_id]["clusters_contributed_to"] += 1
            if len({member.source for member in cluster.cluster.member_articles}) >= 2:
                source_coverage[source_id]["multi_source_clusters_contributed_to"] += 1

    romanian_sources = [
        coverage
        for coverage in source_coverage.values()
        if coverage["source_scope"] == "national"
    ]
    romanian_sources.sort(
        key=lambda item: (
            -item["candidate_articles_produced"],
            -item["articles_fetched_successfully"],
            -item["clusters_contributed_to"],
            item["source_name"].lower(),
        )
    )

    payload = {
        "romanian_source_count": len(romanian_sources),
        "sources": romanian_sources,
    }
    ROMANIAN_SOURCE_COVERAGE_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "ROMANIAN SOURCE COVERAGE",
        "",
        f"romanian_source_count: {payload['romanian_source_count']}",
        "",
    ]
    for index, item in enumerate(romanian_sources, start=1):
        lines.extend([
            f"{index}. {item['source_name']}",
            f"   source_category: {item['source_category']}",
            f"   editorial_priority: {item['editorial_priority']}",
            f"   articles_discovered: {item['articles_discovered']}",
            f"   recent_feed_items_considered: {item.get('recent_feed_items_considered', 0)}",
            f"   articles_fetched_successfully: {item['articles_fetched_successfully']}",
            f"   candidate_articles_produced: {item['candidate_articles_produced']}",
            f"   clusters_contributed_to: {item['clusters_contributed_to']}",
            f"   multi_source_clusters_contributed_to: {item['multi_source_clusters_contributed_to']}",
            f"   selected_national_preference_bucket: {item.get('selected_national_preference_bucket') or 'none'}",
            f"   selected_national_preference_reason: {item.get('selected_national_preference_reason') or 'none'}",
            f"   selected_primary_candidate: {item.get('selected_primary_candidate') or 'none'}",
            f"   competing_candidate_titles: {', '.join(item.get('competing_candidate_titles') or []) or 'none'}",
            f"   selected_event_family_hint: {item.get('selected_event_family_hint') or 'none'}",
            f"   institutional_signal_hits: {', '.join(item.get('institutional_signal_hits') or []) or 'none'}",
            f"   romania_impact_evidence_hits: {', '.join(item.get('romania_impact_evidence_hits') or []) or 'none'}",
            f"   title_only_domestic_boost: {item.get('title_only_domestic_boost', 0.0)}",
            f"   selection_reason: {item.get('selection_reason') or 'none'}",
            f"   overlapping_sources_for_same_event: {', '.join(item.get('overlapping_sources_for_same_event') or []) or 'none'}",
            "",
        ])
    ROMANIAN_SOURCE_COVERAGE_TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_romanian_candidate_pool_audit(national_candidates: list, article_by_url: dict[str, FetchedArticle], clustering_service) -> None:
    payload_clusters = []
    for cluster in national_candidates:
        buckets = [member.national_preference_bucket for member in cluster.cluster.member_articles if member.national_preference_bucket]
        reasons = [member.national_preference_reason for member in cluster.cluster.member_articles if member.national_preference_reason]
        cluster_articles = [
            article_by_url.get(member.url, member)
            for member in cluster.cluster.member_articles
        ]
        positive_signals = sorted({
            signal
            for article in cluster_articles
            for signal in getattr(article, "domestic_hard_news_positive_signals", [])
        })
        negative_signals = sorted({
            signal
            for article in cluster_articles
            for signal in getattr(article, "domestic_hard_news_negative_signals", [])
        })
        dominant_bucket = Counter(buckets).most_common(1)[0][0] if buckets else None
        dominant_bucket_articles = [
            article for article in cluster_articles
            if getattr(article, "national_preference_bucket", None) == dominant_bucket
        ]
        debug_article = max(
            dominant_bucket_articles or cluster_articles,
            key=lambda article: getattr(article, "domestic_score_total", float('-inf')) if getattr(article, "domestic_score_total", None) is not None else float('-inf'),
        ) if cluster_articles else None
        payload_clusters.append({
            "cluster_id": cluster.cluster.cluster_id,
            "headline": cluster.cluster.representative_title,
            "source_list": sorted({member.source for member in cluster.cluster.member_articles}),
            "unique_source_count": len({member.source for member in cluster.cluster.member_articles}),
            "named_entities_detected": _cluster_named_entities(cluster, article_by_url, clustering_service),
            "cluster_similarity_score": _cluster_similarity_score(cluster, article_by_url, clustering_service),
            "national_preference_bucket": dominant_bucket,
            "national_preference_reason": getattr(debug_article, "national_preference_reason", None) if debug_article is not None else (reasons[0] if reasons else None),
            "domestic_hard_news_positive_signals": positive_signals,
            "domestic_hard_news_negative_signals": negative_signals,
            "domestic_score_total": getattr(debug_article, "domestic_score_total", None) if debug_article is not None else None,
            "headline_gate_passed": getattr(debug_article, "headline_gate_passed", None) if debug_article is not None else None,
            "romanian_entity_hits_count": getattr(debug_article, "romanian_entity_hits_count", None) if debug_article is not None else None,
            "public_interest_hits_count": getattr(debug_article, "public_interest_hits_count", None) if debug_article is not None else None,
            "negative_signal_count": getattr(debug_article, "negative_signal_count", None) if debug_article is not None else None,
            "candidate_event_family_hints": getattr(debug_article, "romanian_event_family_hints", None) if debug_article is not None else None,
            "institutional_signal_hits": getattr(debug_article, "institutional_signal_hits", None) if debug_article is not None else None,
            "romania_impact_evidence_hits": getattr(cluster, "romania_impact_evidence_hits", None),
            "domestic_purity_score": getattr(cluster, "domestic_purity_score", None),
            "external_penalty_applied": getattr(cluster, "external_penalty_applied", None),
            "title_only_domestic_boost": getattr(cluster, "title_only_domestic_boost", None),
            "cluster_event_family_hints": getattr(cluster, "cluster_event_family_hints", None),
            "domestic_vs_external_rank_reason": getattr(cluster, "domestic_vs_external_rank_reason", None),
            "recovery_score": getattr(cluster, "recovery_score", 0.0),
            "recovered_domestic_candidate": getattr(cluster, "recovered_domestic_candidate", False),
            "persistence_boost_applied": getattr(cluster, "persistence_boost_applied", 0.0),
            "top5_balance_adjustment_reason": getattr(cluster, "top5_balance_adjustment_reason", None),
            "recovery_rejection_reason": getattr(cluster, "recovery_rejection_reason", None),
            "failed_threshold_name": getattr(cluster, "failed_threshold_name", None),
            "threshold_required_value": getattr(cluster, "threshold_required_value", None),
            "candidate_current_value": getattr(cluster, "candidate_current_value", None),
            "classifier_decision_reason": getattr(debug_article, "classifier_decision_reason", None) if debug_article is not None else None,
            "attached_story_family": getattr(cluster, "story_family_id", None),
            "family_attach_reason": getattr(cluster, "family_attach_reason", None),
            "editorial_profile_used": getattr(cluster, "editorial_profile_used", None),
            "profile_config_name": getattr(cluster, "profile_config_name", None),
            "shared_core_path_used": getattr(cluster, "shared_core_path_used", False),
            "family_first_seen": getattr(cluster, "family_first_seen", None),
            "family_last_seen": getattr(cluster, "family_last_seen", None),
            "family_run_count": getattr(cluster, "family_run_count", 0),
            "family_age_hours": getattr(cluster, "family_age_hours", 0.0),
            "family_lifecycle_boost": getattr(cluster, "family_lifecycle_boost", 0.0),
            "final_score": cluster.score_total,
        })

    bucket_distribution = Counter(item["national_preference_bucket"] or "none" for item in payload_clusters)
    payload = {
        "national_cluster_count": len(payload_clusters),
        "multi_source_clusters": sum(1 for item in payload_clusters if item["unique_source_count"] >= 2),
        "national_preference_bucket_distribution": dict(sorted(bucket_distribution.items())),
        "clusters": payload_clusters,
    }
    ROMANIAN_CANDIDATE_POOL_AUDIT_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug breaking bulletin by editorial profile.")
    parser.add_argument(
        "--profile",
        choices=("all", "national", "international", "local"),
        default="all",
        help="Editorial profile to route through the shared core. 'all' preserves the combined national + international bulletin view.",
    )
    return parser.parse_args()


def _profile_names_from_arg(profile_arg: str) -> list[str]:
    mapping = {
        "national": ["national_ro"],
        "international": ["international"],
        "local": ["local"],
        "all": ["national_ro", "international"],
    }
    return mapping[profile_arg]


def _section_title(profile_name: str) -> str:
    return {
        "national_ro": "TOP 5 NATIONAL",
        "international": "TOP 5 INTERNATIONAL",
        "local": "TOP 5 LOCAL",
    }[profile_name]


def main() -> None:
    args = _parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    personalization = _build_personalization(args.profile)
    pipeline_service = EditorialPipelineService()
    core_service = pipeline_service.editorial_selection_core_service

    articles, _, source_coverage = _build_articles(personalization)
    article_by_url = {article.url: article for article in articles}
    story_clusters = pipeline_service.clustering_service.cluster_articles(articles)
    scored_clusters = pipeline_service.scoring_service.score_clusters(story_clusters)
    pipeline_service.story_family_service.attach_story_families(scored_clusters)

    profile_names = _profile_names_from_arg(args.profile)
    core_results: dict[str, object] = {}
    top5_by_profile: dict[str, list[dict[str, object]]] = {}

    for profile_name in profile_names:
        core_result = core_service.run_profile(
            scored_clusters,
            profile_name,
            max_stories=5,
            editorial_preferences=personalization.editorial_preferences,
            personalization=personalization,
        )
        core_results[profile_name] = core_result
        top5_by_profile[profile_name] = _pick_top5(
            core_result.selection_result.selected_clusters,
            core_result.candidate_clusters,
            article_by_url,
            pipeline_service.clustering_service,
            core_result.profile.scope,
        )

    national_candidates = core_results.get("national_ro").candidate_clusters if "national_ro" in core_results else []
    if national_candidates:
        _write_romanian_source_coverage(source_coverage, national_candidates, pipeline_service.clustering_service)
        _write_romanian_candidate_pool_audit(national_candidates, article_by_url, pipeline_service.clustering_service)

    payload = {
        "editorial_profiles_run": profile_names,
        "top5_by_profile": top5_by_profile,
    }
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    primary_profile = profile_names[0]
    primary_top5 = top5_by_profile.get(primary_profile, [])
    lines = [
        _section_title(primary_profile),
        "",
        f"Editorial profile used: {core_results[primary_profile].debug_metadata['editorial_profile_used']}",
        f"Profile config name: {core_results[primary_profile].debug_metadata['profile_config_name']}",
        f"Shared core path used: {core_results[primary_profile].debug_metadata['shared_core_path_used']}",
        "",
    ]
    for item in primary_top5:
        lines.extend([
            f"{item['rank']}.",
            f"Headline: {item['headline']}",
            f"Normalized headline: {item['normalized_headline']}",
            f"Sources: {', '.join(item['source_list'])}",
            f"Unique sources: {item['unique_source_count']}",
            f"Event family: {', '.join(item['event_family']) or 'none'}",
            f"Regional bucket: {', '.join(item['regional_bucket']) or 'none'}",
            f"Domestic purity: {item.get('domestic_purity_score', 0.0)}",
            f"Romania impact hits: {', '.join(item.get('romania_impact_evidence_hits') or []) or 'none'}",
            f"Romanian source count: {item.get('romanian_source_count', 0)}",
            f"Romanian multi-source bonus: {item.get('romanian_multi_source_bonus_applied', 0.0)}",
            f"External penalty: {item.get('external_penalty_applied', 0.0)}",
            f"Title-only domestic boost: {item.get('title_only_domestic_boost', 0.0)}",
            f"Rank reason: {item.get('domestic_vs_external_rank_reason') or 'none'}",
            f"Recovery score: {item.get('recovery_score', 0.0)}",
            f"Recovered domestic: {item.get('recovered_domestic_candidate', False)}",
            f"Persistence boost: {item.get('persistence_boost_applied', 0.0)}",
            f"Balance adjustment: {item.get('top5_balance_adjustment_reason') or 'none'}",
            f"Editorial profile used: {item.get('editorial_profile_used') or 'none'}",
            f"Shared core path used: {item.get('shared_core_path_used', False)}",
            f"Attached story family: {item.get('attached_story_family') or 'none'}",
            f"Family attach reason: {item.get('family_attach_reason') or 'none'}",
            f"Family first seen: {item.get('family_first_seen') or 'none'}",
            f"Family last seen: {item.get('family_last_seen') or 'none'}",
            f"Family run count: {item.get('family_run_count', 0)}",
            f"Family age hours: {item.get('family_age_hours', 0.0)}",
            f"Lifecycle boost: {item.get('family_lifecycle_boost', 0.0)}",
            f"Geographic signal detected: {item.get('geographic_signal_detected') or 'none'}",
            f"Local relevance boost: {item.get('local_relevance_boost', 0.0)}",
            f"Local domain signal hits: {', '.join(item.get('local_domain_signal_hits') or []) or 'none'}",
            f"Local county tag: {item.get('local_county_tag') or 'none'}",
            f"Entered via: {'lifecycle_support' if item.get('family_lifecycle_boost', 0.0) > 0 else 'standard_selection'}",
            f"Freshness: {item['freshness_score']}",
            f"Score: {item['final_score']}",
            "",
        ])

    justice_boosted_stories = [
        item for item in primary_top5
        if any(hint in JUSTICE_HINTS for hint in (item.get("cluster_event_family_hints") or []))
        and (
            item.get("recovered_domestic_candidate")
            or (item.get("persistence_boost_applied") or 0.0) > 0
            or any(hint in JUSTICE_HINTS for hint in (item.get("cluster_event_family_hints") or []))
        )
    ]
    family_summaries = _story_family_summary(scored_clusters)
    lines.extend(["STORY FAMILIES DETECTED", ""])
    if family_summaries:
        for family in family_summaries:
            lines.extend([
                f"family_id: {family['family_id']}",
                f"stories: {family['stories']}",
                f"sources: {', '.join(family['sources']) or 'none'}",
                f"event_hints: {', '.join(family['event_hints']) or 'none'}",
                f"first_seen: {family.get('first_seen') or 'none'}",
                f"last_seen: {family.get('last_seen') or 'none'}",
                f"run_count: {family.get('run_count', 0)}",
                f"age_hours: {family.get('age_hours', 0.0)}",
                "",
            ])
    else:
        lines.extend(["none", ""])

    lines.extend(["JUSTICE BOOSTED STORIES", ""])
    if justice_boosted_stories:
        for item in justice_boosted_stories:
            lines.extend([
                f"- {item['headline']}",
                f"  reason: {_justice_boost_reason(item)}",
                f"  purity: {item.get('domestic_purity_score', 0.0)}",
                f"  recovery_score: {item.get('recovery_score', 0.0)}",
                f"  entered_via: {_justice_entered_via(item)}",
                "",
            ])
    else:
        lines.extend(["none", ""])

    selected_national_ids = {item["cluster_id"] for item in primary_top5}
    near_miss_candidates = [
        cluster for cluster in national_candidates
        if cluster.cluster.cluster_id not in selected_national_ids
        and getattr(cluster, "domestic_purity_score", 0.0) > 0.4
        and len(getattr(cluster, "romania_impact_evidence_hits", []) or []) >= 1
        and getattr(cluster, "recovered_domestic_candidate", False) is False
    ]
    near_miss_candidates.sort(key=lambda cluster: (getattr(cluster, "recovery_score", 0.0), getattr(cluster, "domestic_purity_score", 0.0), cluster.score_total), reverse=True)
    lines.extend(["NEAR_MISS_DOMESTIC_CANDIDATES", ""])
    for cluster in near_miss_candidates[:5]:
        lines.extend([
            f"Headline: {cluster.cluster.representative_title}",
            f"Domestic purity: {getattr(cluster, 'domestic_purity_score', 0.0)}",
            f"Romania impact hits: {', '.join(getattr(cluster, 'romania_impact_evidence_hits', []) or []) or 'none'}",
            f"Event family hints: {', '.join(getattr(cluster, 'cluster_event_family_hints', []) or []) or 'none'}",
            f"Rejection reason: {getattr(cluster, 'domestic_vs_external_rank_reason', None) or 'none'}",
            f"Recovery score: {getattr(cluster, 'recovery_score', 0.0)}",
            f"Recovery rejection: {getattr(cluster, 'recovery_rejection_reason', None) or 'none'}",
            f"Failed threshold: {getattr(cluster, 'failed_threshold_name', None) or 'none'}",
            f"Required value: {getattr(cluster, 'threshold_required_value', None) or 'none'}",
            f"Current value: {getattr(cluster, 'candidate_current_value', None) or 'none'}",
            "",
        ])

    hard_news_count = sum(1 for item in primary_top5 if item.get("national_preference_bucket") == "domestic_hard_news")
    recovered_count = sum(1 for item in primary_top5 if item.get("recovered_domestic_candidate"))
    near_miss_count = len(near_miss_candidates)
    if hard_news_count + recovered_count >= 3:
        balance_label = "GOOD"
    elif hard_news_count + recovered_count == 2:
        balance_label = "THIN"
    else:
        balance_label = "WEAK"
    lines.extend([f"Domestic coverage today: {hard_news_count} hard-news / {recovered_count} recovered / {near_miss_count} near-miss -> balance: {balance_label}", ""])

    if "international" in top5_by_profile:
        lines.extend(["TOP 5 INTERNATIONAL", ""])
        for item in top5_by_profile["international"]:
            lines.extend([
                f"{item['rank']}.",
                f"Headline: {item['headline']}",
                f"Normalized headline: {item['normalized_headline']}",
                f"Sources: {', '.join(item['source_list'])}",
                f"Unique sources: {item['unique_source_count']}",
                f"Event family: {', '.join(item['event_family']) or 'none'}",
                f"Regional bucket: {', '.join(item['regional_bucket']) or 'none'}",
                f"Domestic purity: {item.get('domestic_purity_score', 0.0)}",
                f"Romania impact hits: {', '.join(item.get('romania_impact_evidence_hits') or []) or 'none'}",
                f"Romanian source count: {item.get('romanian_source_count', 0)}",
                f"Romanian multi-source bonus: {item.get('romanian_multi_source_bonus_applied', 0.0)}",
                f"External penalty: {item.get('external_penalty_applied', 0.0)}",
                f"Title-only domestic boost: {item.get('title_only_domestic_boost', 0.0)}",
                f"Rank reason: {item.get('domestic_vs_external_rank_reason') or 'none'}",
                f"Recovery score: {item.get('recovery_score', 0.0)}",
                f"Recovered domestic: {item.get('recovered_domestic_candidate', False)}",
                f"Persistence boost: {item.get('persistence_boost_applied', 0.0)}",
                f"Balance adjustment: {item.get('top5_balance_adjustment_reason') or 'none'}",
                f"Editorial profile used: {item.get('editorial_profile_used') or 'none'}",
                f"Shared core path used: {item.get('shared_core_path_used', False)}",
                f"Attached story family: {item.get('attached_story_family') or 'none'}",
                f"Family attach reason: {item.get('family_attach_reason') or 'none'}",
                f"Geographic signal detected: {item.get('geographic_signal_detected') or 'none'}",
                f"Local relevance boost: {item.get('local_relevance_boost', 0.0)}",
                f"Local domain signal hits: {', '.join(item.get('local_domain_signal_hits') or []) or 'none'}",
                f"Local county tag: {item.get('local_county_tag') or 'none'}",
                f"Freshness: {item['freshness_score']}",
                f"Score: {item['final_score']}",
                "",
            ])

    TEXT_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {TEXT_OUTPUT_PATH}")
    print(f"Wrote {JSON_OUTPUT_PATH}")
    if national_candidates:
        print(f"Wrote {ROMANIAN_SOURCE_COVERAGE_JSON_PATH}")
        print(f"Wrote {ROMANIAN_SOURCE_COVERAGE_TEXT_PATH}")
        print(f"Wrote {ROMANIAN_CANDIDATE_POOL_AUDIT_JSON_PATH}")
    print(json.dumps({
        "profiles_run": profile_names,
        "selected_counts": {name: len(items) for name, items in top5_by_profile.items()},
        "national_candidate_clusters": len(national_candidates),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
