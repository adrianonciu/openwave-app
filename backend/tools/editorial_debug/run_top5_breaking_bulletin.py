from __future__ import annotations

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
    _build_general_personalization,
    _cluster_signals,
    _dominant_scope,
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
        "external_penalty_applied": getattr(scored_cluster, "external_penalty_applied", 0.0),
        "title_only_domestic_boost": getattr(scored_cluster, "title_only_domestic_boost", 0.0),
        "cluster_event_family_hints": getattr(scored_cluster, "cluster_event_family_hints", []),
        "domestic_vs_external_rank_reason": getattr(scored_cluster, "domestic_vs_external_rank_reason", None),
        "recovery_score": getattr(scored_cluster, "recovery_score", 0.0),
        "recovered_domestic_candidate": getattr(scored_cluster, "recovered_domestic_candidate", False),
        "persistence_boost_applied": getattr(scored_cluster, "persistence_boost_applied", 0.0),
        "top5_balance_adjustment_reason": getattr(scored_cluster, "top5_balance_adjustment_reason", None),
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
            "classifier_decision_reason": getattr(debug_article, "classifier_decision_reason", None) if debug_article is not None else None,
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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    personalization = _build_general_personalization()
    pipeline_service = EditorialPipelineService()

    articles, _, source_coverage = _build_articles(personalization)
    article_by_url = {article.url: article for article in articles}
    story_clusters = pipeline_service.clustering_service.cluster_articles(articles)
    scored_clusters = pipeline_service.scoring_service.score_clusters(story_clusters)

    national_candidates = [cluster for cluster in scored_clusters if _dominant_scope(cluster) == "national"]
    global_candidates = [cluster for cluster in scored_clusters if _dominant_scope(cluster) == "international"]

    national_selection = pipeline_service.selection_service.select_stories(
        national_candidates,
        max_stories=5,
        editorial_preferences=personalization.editorial_preferences,
        personalization=personalization,
    )
    global_selection = pipeline_service.selection_service.select_stories(
        global_candidates,
        max_stories=5,
        editorial_preferences=personalization.editorial_preferences,
        personalization=personalization,
    )

    national_top5 = _pick_top5(national_selection.selected_clusters, national_candidates, article_by_url, pipeline_service.clustering_service, "national")
    global_top5 = _pick_top5(global_selection.selected_clusters, global_candidates, article_by_url, pipeline_service.clustering_service, "international")

    _write_romanian_source_coverage(source_coverage, national_candidates, pipeline_service.clustering_service)
    _write_romanian_candidate_pool_audit(national_candidates, article_by_url, pipeline_service.clustering_service)

    payload = {
        "top5_national": national_top5,
        "top5_global": global_top5,
    }
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = ["TOP 5 NATIONAL", ""]
    for item in national_top5:
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
            f"External penalty: {item.get('external_penalty_applied', 0.0)}",
            f"Title-only domestic boost: {item.get('title_only_domestic_boost', 0.0)}",
            f"Rank reason: {item.get('domestic_vs_external_rank_reason') or 'none'}",
            f"Recovery score: {item.get('recovery_score', 0.0)}",
            f"Recovered domestic: {item.get('recovered_domestic_candidate', False)}",
            f"Persistence boost: {item.get('persistence_boost_applied', 0.0)}",
            f"Balance adjustment: {item.get('top5_balance_adjustment_reason') or 'none'}",
            f"Freshness: {item['freshness_score']}",
            f"Score: {item['final_score']}",
            "",
        ])

    selected_national_ids = {item["cluster_id"] for item in national_top5}
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
            "",
        ])

    lines.extend(["TOP 5 INTERNATIONAL", ""])
    for item in global_top5:
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
            f"External penalty: {item.get('external_penalty_applied', 0.0)}",
            f"Title-only domestic boost: {item.get('title_only_domestic_boost', 0.0)}",
            f"Rank reason: {item.get('domestic_vs_external_rank_reason') or 'none'}",
            f"Recovery score: {item.get('recovery_score', 0.0)}",
            f"Recovered domestic: {item.get('recovered_domestic_candidate', False)}",
            f"Persistence boost: {item.get('persistence_boost_applied', 0.0)}",
            f"Balance adjustment: {item.get('top5_balance_adjustment_reason') or 'none'}",
            f"Freshness: {item['freshness_score']}",
            f"Score: {item['final_score']}",
            "",
        ])

    TEXT_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {TEXT_OUTPUT_PATH}")
    print(f"Wrote {JSON_OUTPUT_PATH}")
    print(f"Wrote {ROMANIAN_SOURCE_COVERAGE_JSON_PATH}")
    print(f"Wrote {ROMANIAN_SOURCE_COVERAGE_TEXT_PATH}")
    print(f"Wrote {ROMANIAN_CANDIDATE_POOL_AUDIT_JSON_PATH}")
    print(json.dumps({
        "national": len(national_top5),
        "global": len(global_top5),
        "national_candidate_clusters": len(national_candidates),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
