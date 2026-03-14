from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path
from urllib.parse import urlparse
import json
import re
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.article_fetch import FetchedArticle
from app.models.user_personalization import (
    DomainPreferenceMix,
    EditorialPreferenceProfile,
    GeographyPreferenceMix,
    ListenerProfile,
    UserPersonalization,
)
from app.services.article_fetch_service import ArticleFetchService
from app.services.article_service import ArticleService
from app.services.editorial_pipeline_service import EditorialPipelineService
from app.services.source_watcher_service import SourceWatcherService

OUTPUT_DIR = BACKEND_ROOT / "debug_output"
NATIONAL_JSON_OUTPUT_PATH = OUTPUT_DIR / "top5_national_selection.json"
NATIONAL_TEXT_OUTPUT_PATH = OUTPUT_DIR / "top5_national_selection.txt"
GLOBAL_JSON_OUTPUT_PATH = OUTPUT_DIR / "top5_global_selection.json"
GLOBAL_TEXT_OUTPUT_PATH = OUTPUT_DIR / "top5_global_selection.txt"
STORY_SELECTION_DEBUG_JSON_PATH = OUTPUT_DIR / "story_selection_debug.json"
STORY_SELECTION_DEBUG_TEXT_PATH = OUTPUT_DIR / "story_selection_debug.txt"
INTERNATIONAL_MERGE_DEBUG_JSON_PATH = OUTPUT_DIR / "international_merge_debug.json"
INTERNATIONAL_MERGE_DEBUG_TEXT_PATH = OUTPUT_DIR / "international_merge_debug.txt"
CANDIDATE_POOL_AUDIT_JSON_PATH = OUTPUT_DIR / "candidate_pool_audit.json"
CANDIDATE_POOL_AUDIT_TEXT_PATH = OUTPUT_DIR / "candidate_pool_audit.txt"
INTERNATIONAL_SOURCE_COVERAGE_JSON_PATH = OUTPUT_DIR / "international_source_coverage.json"
INTERNATIONAL_SOURCE_COVERAGE_TEXT_PATH = OUTPUT_DIR / "international_source_coverage.txt"
MAX_INPUT_ARTICLES = 20
MAX_RSS_FALLBACK_ARTICLES = 6
MAX_SOURCE_FETCH_ATTEMPTS = 32
TOKEN_PATTERN = re.compile(r"[0-9A-Za-z\u00C0-\u024F][0-9A-Za-z\u00C0-\u024F\-']*")
NOISY_PREFIX_PATTERN = re.compile(r"^(?:live(?:-text)?|video|foto|breaking|update)\s*[:\-]+\s*", re.IGNORECASE)
SEPARATOR_PATTERN = re.compile(r"\s*(?:\||::| - |  |  )\s*")
LIKELY_EVENT_TERMS = {
    "iran", "golful", "emiratele", "ormuz", "porturi", "marines", "mijlociu", "orientul", "hamas",
    "nato", "eu", "brussels", "sanctions", "atac", "ambasada", "ukraine", "ucraina", "moldova",
}
LOCATION_TERMS = {
    "iran", "emiratele", "golful", "ormuz", "bagdad", "brussels", "romania", "ukraine", "ucraina", "moldova",
    "balkans", "balcani", "black sea", "marea neagra", "germany", "belarus",
}


def _normalize_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _build_general_personalization() -> UserPersonalization:
    return UserPersonalization(
        listener_profile=ListenerProfile(
            first_name=None,
            country=None,
            region=None,
            city=None,
        ),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=0, national=50, international=50),
            domains=DomainPreferenceMix(
                politics=28,
                economy=20,
                sport=4,
                entertainment=4,
                education=14,
                health=14,
                tech=16,
            ),
        ),
    )


def _build_articles(personalization: UserPersonalization) -> tuple[list[FetchedArticle], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    watcher_service = SourceWatcherService()
    fetch_service = ArticleFetchService()
    article_service = ArticleService()

    base_source_configs, _ = watcher_service.resolve_monitored_source_configs(personalization)
    source_by_domain: dict[str, dict[str, object]] = {}
    latest_items: list[tuple[object, object]] = []
    source_coverage: dict[str, dict[str, object]] = {}

    for source_config in base_source_configs:
        source_by_domain[_normalize_domain(source_config.source_url)] = {
            "source_id": source_config.source_id,
            "source_name": source_config.source_name,
            "source_type": source_config.source_type,
            "scope": source_config.scope,
            "category": source_config.category,
            "editorial_priority": source_config.editorial_priority,
            "region": source_config.region,
        }
        source_coverage[source_config.source_id] = {
            "source_id": source_config.source_id,
            "source_name": source_config.source_name,
            "source_scope": source_config.scope,
            "source_category": source_config.category,
            "editorial_priority": source_config.editorial_priority,
            "articles_discovered": 0,
            "articles_fetched_successfully": 0,
            "candidate_articles_produced": 0,
            "clusters_contributed_to": 0,
            "multi_source_clusters_contributed_to": 0,
        }
        try:
            latest = watcher_service.get_latest_content(source_config)
            latest_items.append((source_config, latest))
            source_coverage[source_config.source_id]["articles_discovered"] += 1
        except Exception:
            continue

    latest_items.sort(key=lambda item: item[1].published_at, reverse=True)

    provenance_by_url: dict[str, dict[str, object]] = {}
    articles: list[FetchedArticle] = []
    seen_urls: set[str] = set()

    source_attempts = 0
    for source_config, latest in latest_items:
        if len(articles) >= MAX_INPUT_ARTICLES or source_attempts >= MAX_SOURCE_FETCH_ATTEMPTS:
            break
        source_attempts += 1
        if latest.url in seen_urls:
            continue
        seen_urls.add(latest.url)
        fetch_result = fetch_service.fetch_article(latest)
        if fetch_result.status == "success" and fetch_result.article is not None:
            article = fetch_result.article.model_copy(
                update={
                    "ingestion_kind": "full_fetch",
                    "editorial_priority": source_config.editorial_priority,
                    "source_scope": source_config.scope,
                    "source_category": source_config.category,
                    "is_local_source": source_config.scope == "local",
                }
            )
            articles.append(article)
            source_coverage[source_config.source_id]["articles_fetched_successfully"] += 1
            source_coverage[source_config.source_id]["candidate_articles_produced"] += 1
            provenance_by_url[article.url] = {
                "ingestion_kind": "full_fetch",
                "source_id": source_config.source_id,
                "scope": source_config.scope,
                "category": source_config.category,
                "editorial_priority": source_config.editorial_priority,
                "source_type": source_config.source_type,
                "is_local_source": source_config.scope == "local",
            }

    rss_articles_added = 0
    for rss_article in article_service.get_articles():
        if len(articles) >= MAX_INPUT_ARTICLES or rss_articles_added >= MAX_RSS_FALLBACK_ARTICLES:
            break
        if rss_article.url in seen_urls or not rss_article.summary.strip():
            continue
        seen_urls.add(rss_article.url)
        mapped_meta = source_by_domain.get(_normalize_domain(rss_article.url))
        if not mapped_meta:
            continue
        article = FetchedArticle(
            url=rss_article.url,
            title=rss_article.title,
            published_at=rss_article.published_at,
            source=rss_article.source,
            content_text=rss_article.summary,
            ingestion_kind="rss_fallback",
            editorial_priority=mapped_meta.get("editorial_priority", 3),
            source_scope=mapped_meta.get("scope"),
            source_category=mapped_meta.get("category"),
            is_local_source=mapped_meta.get("scope") == "local",
        )
        articles.append(article)
        source_id = mapped_meta.get("source_id")
        if source_id in source_coverage:
            source_coverage[source_id]["candidate_articles_produced"] += 1
        provenance_by_url[article.url] = {
            "ingestion_kind": "rss_fallback",
            "source_id": mapped_meta.get("source_id"),
            "scope": mapped_meta.get("scope"),
            "category": mapped_meta.get("category"),
            "editorial_priority": mapped_meta.get("editorial_priority", 3),
            "source_type": mapped_meta.get("source_type"),
            "is_local_source": mapped_meta.get("scope") == "local",
        }
        rss_articles_added += 1

    return articles, provenance_by_url, source_coverage


def _dominant_scope(scored_cluster) -> str:
    scopes = [member.source_scope or ("local" if member.is_local_source else "unknown") for member in scored_cluster.cluster.member_articles]
    return Counter(scopes).most_common(1)[0][0] if scopes else "unknown"


def _dominant_category(scored_cluster) -> str:
    categories = [member.source_category or "general" for member in scored_cluster.cluster.member_articles]
    return Counter(categories).most_common(1)[0][0] if categories else "general"


def _normalize_headline(title: str) -> str:
    cleaned = NOISY_PREFIX_PATTERN.sub("", title or "")
    cleaned = SEPARATOR_PATTERN.split(cleaned, maxsplit=1)[0]
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:;,")
    tokens = TOKEN_PATTERN.findall(cleaned)
    if len(tokens) > 12:
        cleaned = " ".join(tokens[:12])
    return cleaned


def _serialize_candidate(scored_cluster, selection_status: str = "selected") -> dict[str, object]:
    breakdown = scored_cluster.score_breakdown
    source_list = sorted({member.source for member in scored_cluster.cluster.member_articles})
    priorities = sorted({member.editorial_priority for member in scored_cluster.cluster.member_articles})
    return {
        "selection_status": selection_status,
        "cluster_id": scored_cluster.cluster.cluster_id,
        "top_headline": scored_cluster.cluster.representative_title,
        "normalized_headline": _normalize_headline(scored_cluster.cluster.representative_title),
        "cluster_size": len(scored_cluster.cluster.member_articles),
        "unique_source_count": len(source_list),
        "source_list": source_list,
        "source_scope": _dominant_scope(scored_cluster),
        "source_category": _dominant_category(scored_cluster),
        "editorial_priority_summary": {
            "best": min(priorities) if priorities else 5,
            "all": priorities,
        },
        "freshness_score": breakdown.recency.contribution,
        "europe_romania_impact_score": breakdown.europe_romania_impact.contribution,
        "europe_romania_impact_explanation": breakdown.europe_romania_impact.explanation,
        "editorial_fit_score": breakdown.editorial_fit.contribution,
        "final_score": scored_cluster.score_total,
    }


def _cluster_signals(scored_cluster, article_by_url: dict[str, FetchedArticle], clustering_service) -> dict[str, object]:
    representative_article = _representative_article(scored_cluster, article_by_url)
    if representative_article is None:
        return {
            "event_families": [],
            "regional_buckets": [],
            "normalized_headline": _normalize_headline(scored_cluster.cluster.representative_title),
            "normalized_source": None,
        }
    normalized_article = clustering_service._normalize_article(representative_article)
    signals = clustering_service._build_signals(normalized_article)
    return {
        "event_families": sorted(signals.event_families),
        "regional_buckets": sorted(signals.regional_buckets),
        "normalized_headline": signals.normalized_title or _normalize_headline(scored_cluster.cluster.representative_title),
        "normalized_source": signals.normalized_source,
    }


def _write_scope_outputs(label: str, selected_clusters: list, candidate_clusters: list, json_path: Path, txt_path: Path) -> dict[str, object]:
    selected_payload = [_serialize_candidate(cluster, selection_status="selected") for cluster in selected_clusters[:5]]
    if len(selected_payload) < 5:
        selected_ids = {item["cluster_id"] for item in selected_payload}
        fallback_clusters = [cluster for cluster in candidate_clusters if cluster.cluster.cluster_id not in selected_ids]
        for cluster in fallback_clusters[: 5 - len(selected_payload)]:
            selected_payload.append(_serialize_candidate(cluster, selection_status="debug_rank_fallback"))
    candidate_payload = [_serialize_candidate(cluster, selection_status="candidate") for cluster in candidate_clusters]
    payload = {
        "scope": label,
        "candidate_cluster_count": len(candidate_clusters),
        "selected_count": len(selected_clusters[:5]),
        "debug_fallback_count": sum(1 for item in selected_payload if item["selection_status"] == "debug_rank_fallback"),
        "selected_with_unique_source_count_gte_2": sum(1 for item in selected_payload if item["unique_source_count"] >= 2),
        "selected_with_unique_source_count_gte_3": sum(1 for item in selected_payload if item["unique_source_count"] >= 3),
        "top5": selected_payload,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [f"TOP 5 {label.upper()} SELECTION", "", f"Candidate clusters: {len(candidate_clusters)}", ""]
    for index, item in enumerate(selected_payload, start=1):
        lines.extend([
            f"{index}. {item['normalized_headline'] or item['top_headline']}",
            f"   selection_status: {item['selection_status']}",
            f"   cluster_id: {item['cluster_id']}",
            f"   top_headline: {item['top_headline']}",
            f"   normalized_headline: {item['normalized_headline']}",
            f"   unique_source_count: {item['unique_source_count']}",
            f"   source_list: {', '.join(item['source_list'])}",
            f"   source_scope: {item['source_scope']}",
            f"   source_category: {item['source_category']}",
            f"   editorial_priority: best={item['editorial_priority_summary']['best']} all={item['editorial_priority_summary']['all']}",
            f"   freshness_score: {item['freshness_score']}",
            f"   europe_romania_impact_score: {item['europe_romania_impact_score']}",
            f"   editorial_fit_score: {item['editorial_fit_score']}",
            f"   final_score: {item['final_score']}",
            "",
        ])
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return payload


def _representative_article(cluster, article_by_url: dict[str, FetchedArticle]) -> FetchedArticle | None:
    for member in cluster.cluster.member_articles:
        article = article_by_url.get(member.url)
        if article is not None:
            return article
    return None


def _write_international_merge_debug(global_candidates: list, article_by_url: dict[str, FetchedArticle], clustering_service) -> None:
    top_candidates = global_candidates[:10]
    representative_articles = []
    for candidate in top_candidates:
        article = _representative_article(candidate, article_by_url)
        if article is not None:
            representative_articles.append((candidate, article))

    pair_payload = []
    for (left_cluster, left_article), (right_cluster, right_article) in combinations(representative_articles, 2):
        left_signal = clustering_service._build_signals(clustering_service._normalize_article(left_article))
        right_signal = clustering_service._build_signals(clustering_service._normalize_article(right_article))
        shared_entities = sorted(left_signal.entities & right_signal.entities)
        shared_event_keywords = sorted(left_signal.event_terms & right_signal.event_terms)
        shared_locations = sorted({term for term in shared_event_keywords if term in LOCATION_TERMS})
        likely_pair = bool(
            shared_entities
            or (set(shared_event_keywords) & LIKELY_EVENT_TERMS)
            or left_signal.normalized_source != right_signal.normalized_source and (
                "iran" in (left_signal.event_terms | right_signal.event_terms)
                and ({"golful", "emiratele", "ormuz", "porturi", "mijlociu", "marines", "hamas"} & (left_signal.event_terms | right_signal.event_terms))
            )
        )
        if not likely_pair:
            continue

        decision = clustering_service.explain_pair(left_article, right_article)
        pair_payload.append({
            "candidate_a_cluster_id": left_cluster.cluster.cluster_id,
            "candidate_b_cluster_id": right_cluster.cluster.cluster_id,
            "candidate_a_headline": left_cluster.cluster.representative_title,
            "candidate_b_headline": right_cluster.cluster.representative_title,
            "normalized_headline_a": left_signal.normalized_title,
            "normalized_headline_b": right_signal.normalized_title,
            "normalized_source_a": left_signal.normalized_source,
            "normalized_source_b": right_signal.normalized_source,
            "event_families_a": sorted(left_signal.event_families),
            "event_families_b": sorted(right_signal.event_families),
            "regional_buckets_a": sorted(left_signal.regional_buckets),
            "regional_buckets_b": sorted(right_signal.regional_buckets),
            "shared_entities": shared_entities,
            "shared_locations": shared_locations,
            "shared_event_keywords": shared_event_keywords,
            "hours_apart": round(decision.hours_apart, 2),
            "merge_decision": decision.status == "merged",
            "decision_status": decision.status,
            "decision_reason": decision.reason,
            "title_similarity": decision.title_similarity,
            "keyword_overlap": decision.keyword_overlap,
            "body_overlap": decision.body_overlap,
        })

    payload = {
        "candidate_count_considered": len(representative_articles),
        "pair_count_reported": len(pair_payload),
        "pairs": pair_payload,
    }
    INTERNATIONAL_MERGE_DEBUG_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "INTERNATIONAL MERGE DEBUG",
        "",
        f"candidate_count_considered: {payload['candidate_count_considered']}",
        f"pair_count_reported: {payload['pair_count_reported']}",
        "",
    ]
    for index, item in enumerate(pair_payload, start=1):
        lines.extend([
            f"{index}. {item['candidate_a_headline']}  <->  {item['candidate_b_headline']}",
            f"   normalized_headline_a: {item['normalized_headline_a']}",
            f"   normalized_headline_b: {item['normalized_headline_b']}",
            f"   normalized_source_a: {item['normalized_source_a']}",
            f"   normalized_source_b: {item['normalized_source_b']}",
            f"   event_families_a: {', '.join(item['event_families_a']) or 'none'}",
            f"   event_families_b: {', '.join(item['event_families_b']) or 'none'}",
            f"   regional_buckets_a: {', '.join(item['regional_buckets_a']) or 'none'}",
            f"   regional_buckets_b: {', '.join(item['regional_buckets_b']) or 'none'}",
            f"   shared_entities: {', '.join(item['shared_entities']) or 'none'}",
            f"   shared_locations: {', '.join(item['shared_locations']) or 'none'}",
            f"   shared_event_keywords: {', '.join(item['shared_event_keywords']) or 'none'}",
            f"   hours_apart: {item['hours_apart']}",
            f"   merge_decision: {item['merge_decision']}",
            f"   decision_reason: {item['decision_reason']}",
            f"   title_similarity: {item['title_similarity']}",
            f"   keyword_overlap: {item['keyword_overlap']}",
            f"   body_overlap: {item['body_overlap']}",
            "",
        ])
    INTERNATIONAL_MERGE_DEBUG_TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_story_selection_debug(scored_clusters: list, selected_cluster_ids: set[str]) -> None:
    candidate_payload = []
    for cluster in scored_clusters:
        serialized = _serialize_candidate(
            cluster,
            selection_status="selected" if cluster.cluster.cluster_id in selected_cluster_ids else "candidate",
        )
        candidate_payload.append(serialized)

    payload = {
        "candidate_cluster_count": len(candidate_payload),
        "clusters_with_unique_source_count_gte_2": sum(1 for item in candidate_payload if item["unique_source_count"] >= 2),
        "clusters_with_unique_source_count_gte_3": sum(1 for item in candidate_payload if item["unique_source_count"] >= 3),
        "top_candidate_clusters": candidate_payload[:10],
        "selected_stories": [item for item in candidate_payload if item["selection_status"] == "selected"],
    }
    STORY_SELECTION_DEBUG_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "STORY SELECTION DEBUG",
        "",
        f"candidate_cluster_count: {payload['candidate_cluster_count']}",
        f"clusters_with_unique_source_count_gte_2: {payload['clusters_with_unique_source_count_gte_2']}",
        f"clusters_with_unique_source_count_gte_3: {payload['clusters_with_unique_source_count_gte_3']}",
        "",
    ]
    for index, item in enumerate(payload["top_candidate_clusters"], start=1):
        lines.extend([
            f"{index}. {item['normalized_headline'] or item['top_headline']}",
            f"   selection_status: {item['selection_status']}",
            f"   cluster_id: {item['cluster_id']}",
            f"   unique_source_count: {item['unique_source_count']}",
            f"   source_list: {', '.join(item['source_list'])}",
            f"   source_scope: {item['source_scope']}",
            f"   source_category: {item['source_category']}",
            f"   editorial_priority: {item['editorial_priority_summary']['best']}",
            f"   freshness_score: {item['freshness_score']}",
            f"   europe_romania_impact_score: {item['europe_romania_impact_score']}",
            f"   editorial_fit_score: {item['editorial_fit_score']}",
            f"   final_score: {item['final_score']}",
            "",
        ])
    STORY_SELECTION_DEBUG_TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_international_source_coverage(
    source_coverage: dict[str, dict[str, object]],
    scored_clusters: list,
    clustering_service,
) -> None:
    coverage_by_normalized_source = {
        clustering_service._normalize_source_identity(coverage["source_name"]): coverage
        for coverage in source_coverage.values()
    }

    for cluster in scored_clusters:
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

    international_sources = [
        coverage
        for coverage in source_coverage.values()
        if coverage["source_scope"] == "international"
    ]
    international_sources.sort(
        key=lambda item: (
            -item["candidate_articles_produced"],
            -item["articles_fetched_successfully"],
            -item["clusters_contributed_to"],
            item["source_name"].lower(),
        )
    )

    payload = {
        "international_source_count": len(international_sources),
        "sources": international_sources,
    }
    INTERNATIONAL_SOURCE_COVERAGE_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "INTERNATIONAL SOURCE COVERAGE",
        "",
        f"international_source_count: {payload['international_source_count']}",
        "",
    ]
    for index, item in enumerate(international_sources, start=1):
        lines.extend([
            f"{index}. {item['source_name']}",
            f"   source_category: {item['source_category']}",
            f"   editorial_priority: {item['editorial_priority']}",
            f"   articles_discovered: {item['articles_discovered']}",
            f"   articles_fetched_successfully: {item['articles_fetched_successfully']}",
            f"   candidate_articles_produced: {item['candidate_articles_produced']}",
            f"   clusters_contributed_to: {item['clusters_contributed_to']}",
            f"   multi_source_clusters_contributed_to: {item['multi_source_clusters_contributed_to']}",
            "",
        ])
    INTERNATIONAL_SOURCE_COVERAGE_TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_candidate_pool_audit(scored_clusters: list, article_by_url: dict[str, FetchedArticle], clustering_service) -> None:
    top_candidates = scored_clusters[:10]
    top_payload = []
    event_family_distribution: Counter[str] = Counter()
    regional_bucket_distribution: Counter[str] = Counter()
    scope_distribution: Counter[str] = Counter()

    for cluster in scored_clusters:
        serialized = _serialize_candidate(cluster, selection_status="candidate")
        signals = _cluster_signals(cluster, article_by_url, clustering_service)
        scope_distribution[serialized["source_scope"]] += 1

        families = signals["event_families"] or ["none"]
        for family in families:
            event_family_distribution[family] += 1

        buckets = signals["regional_buckets"] or ["none"]
        for bucket in buckets:
            regional_bucket_distribution[bucket] += 1

        if len(top_payload) < 10:
            top_payload.append({
                **serialized,
                "normalized_headline": signals["normalized_headline"],
                "normalized_source": signals["normalized_source"],
                "event_family": signals["event_families"],
                "regional_bucket": signals["regional_buckets"],
            })

    payload = {
        "candidate_pool_size": {
            "total_clusters": len(scored_clusters),
            "international_clusters": scope_distribution.get("international", 0),
            "national_clusters": scope_distribution.get("national", 0),
        },
        "multi_source_cluster_stats": {
            "clusters_unique_sources_gte_2": sum(
                1 for cluster in scored_clusters if len({member.source for member in cluster.cluster.member_articles}) >= 2
            ),
            "clusters_unique_sources_gte_3": sum(
                1 for cluster in scored_clusters if len({member.source for member in cluster.cluster.member_articles}) >= 3
            ),
            "clusters_unique_sources_gte_4": sum(
                1 for cluster in scored_clusters if len({member.source for member in cluster.cluster.member_articles}) >= 4
            ),
        },
        "event_family_distribution": dict(sorted(event_family_distribution.items())),
        "regional_bucket_distribution": dict(sorted(regional_bucket_distribution.items())),
        "top_candidate_clusters": top_payload,
    }
    CANDIDATE_POOL_AUDIT_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "CANDIDATE POOL AUDIT",
        "",
        f"total_clusters: {payload['candidate_pool_size']['total_clusters']}",
        f"international_clusters: {payload['candidate_pool_size']['international_clusters']}",
        f"national_clusters: {payload['candidate_pool_size']['national_clusters']}",
        "",
        "MULTI-SOURCE CLUSTER STATS",
        f"clusters_unique_sources_gte_2: {payload['multi_source_cluster_stats']['clusters_unique_sources_gte_2']}",
        f"clusters_unique_sources_gte_3: {payload['multi_source_cluster_stats']['clusters_unique_sources_gte_3']}",
        f"clusters_unique_sources_gte_4: {payload['multi_source_cluster_stats']['clusters_unique_sources_gte_4']}",
        "",
        "EVENT FAMILY DISTRIBUTION",
    ]
    for family, count in payload["event_family_distribution"].items():
        lines.append(f"{family}: {count}")
    lines.extend(["", "REGIONAL BUCKET DISTRIBUTION"])
    for bucket, count in payload["regional_bucket_distribution"].items():
        lines.append(f"{bucket}: {count}")
    lines.extend(["", "TOP 10 CANDIDATE CLUSTERS", ""])

    for index, item in enumerate(top_payload, start=1):
        lines.extend([
            f"{index}. {item['normalized_headline'] or item['top_headline']}",
            f"   cluster_id: {item['cluster_id']}",
            f"   top_headline: {item['top_headline']}",
            f"   normalized_headline: {item['normalized_headline']}",
            f"   normalized_source: {item['normalized_source'] or 'unknown'}",
            f"   source_list: {', '.join(item['source_list'])}",
            f"   unique_source_count: {item['unique_source_count']}",
            f"   event_family: {', '.join(item['event_family']) or 'none'}",
            f"   regional_bucket: {', '.join(item['regional_bucket']) or 'none'}",
            f"   category: {item['source_category']}",
            f"   freshness_score: {item['freshness_score']}",
            f"   editorial_fit_score: {item['editorial_fit_score']}",
            f"   final_score: {item['final_score']}",
            "",
        ])
    CANDIDATE_POOL_AUDIT_TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")


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

    national_payload = _write_scope_outputs(
        "national",
        national_selection.selected_clusters,
        national_candidates,
        NATIONAL_JSON_OUTPUT_PATH,
        NATIONAL_TEXT_OUTPUT_PATH,
    )
    global_payload = _write_scope_outputs(
        "global",
        global_selection.selected_clusters,
        global_candidates,
        GLOBAL_JSON_OUTPUT_PATH,
        GLOBAL_TEXT_OUTPUT_PATH,
    )

    selected_cluster_ids = {cluster.cluster.cluster_id for cluster in national_selection.selected_clusters + global_selection.selected_clusters}
    _write_story_selection_debug(scored_clusters, selected_cluster_ids)
    _write_international_merge_debug(global_candidates, article_by_url, pipeline_service.clustering_service)
    _write_candidate_pool_audit(scored_clusters, article_by_url, pipeline_service.clustering_service)
    _write_international_source_coverage(source_coverage, scored_clusters, pipeline_service.clustering_service)

    print(f"Wrote {NATIONAL_JSON_OUTPUT_PATH}")
    print(f"Wrote {NATIONAL_TEXT_OUTPUT_PATH}")
    print(f"Wrote {GLOBAL_JSON_OUTPUT_PATH}")
    print(f"Wrote {GLOBAL_TEXT_OUTPUT_PATH}")
    print(f"Wrote {STORY_SELECTION_DEBUG_JSON_PATH}")
    print(f"Wrote {STORY_SELECTION_DEBUG_TEXT_PATH}")
    print(f"Wrote {INTERNATIONAL_MERGE_DEBUG_JSON_PATH}")
    print(f"Wrote {INTERNATIONAL_MERGE_DEBUG_TEXT_PATH}")
    print(f"Wrote {CANDIDATE_POOL_AUDIT_JSON_PATH}")
    print(f"Wrote {CANDIDATE_POOL_AUDIT_TEXT_PATH}")
    print(f"Wrote {INTERNATIONAL_SOURCE_COVERAGE_JSON_PATH}")
    print(f"Wrote {INTERNATIONAL_SOURCE_COVERAGE_TEXT_PATH}")
    print(json.dumps({
        "national_candidate_clusters": national_payload["candidate_cluster_count"],
        "global_candidate_clusters": global_payload["candidate_cluster_count"],
        "national_selected": national_payload["selected_count"],
        "global_selected": global_payload["selected_count"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
