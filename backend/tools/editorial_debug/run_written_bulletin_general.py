from __future__ import annotations

from collections import Counter
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
from app.services.editorial_contract_validation_service import EditorialContractValidationService
from app.services.editorial_pipeline_service import EditorialPipelineService
from app.services.source_watcher_service import SourceWatcherService

OUTPUT_DIR = BACKEND_ROOT / "debug_output"
JSON_OUTPUT_PATH = OUTPUT_DIR / "written_bulletin_debug.json"
TEXT_OUTPUT_PATH = OUTPUT_DIR / "written_bulletin_general.txt"
SELECTION_JSON_OUTPUT_PATH = OUTPUT_DIR / "story_selection_debug.json"
SELECTION_TEXT_OUTPUT_PATH = OUTPUT_DIR / "story_selection_debug.txt"
MAX_INPUT_ARTICLES = 20
MAX_RSS_FALLBACK_ARTICLES = 6
ENGLISH_MARKERS = {
    "the", "and", "with", "from", "under", "against", "whose", "during", "officials",
    "says", "say", "family", "suspect", "wait", "world", "news", "teacher", "died",
    "dropped", "charges", "fire", "drone", "airstrike", "school", "deliberate",
}
ROMANIAN_MARKERS = {
    "si", "sau", "este", "sunt", "pentru", "care", "din", "catre", "dupa", "potrivit",
    "spune", "transmite", "arata", "masura", "buletin", "stiri", "momentului", "atentie",
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


def _detect_language_issue(text: str) -> dict[str, object]:
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", text.lower())
    english_hits = sorted({token for token in tokens if token in ENGLISH_MARKERS})
    romanian_hits = sorted({token for token in tokens if token in ROMANIAN_MARKERS})
    mixed = len(english_hits) >= 2
    return {
        "mixed_language_detected": mixed,
        "english_markers": english_hits,
        "romanian_markers": romanian_hits,
    }


def _serialize_score_breakdown(scored_cluster) -> dict[str, object]:
    breakdown = scored_cluster.score_breakdown
    return {
        "recency": breakdown.recency.model_dump(mode="json"),
        "source_count": breakdown.source_count.model_dump(mode="json"),
        "source_quality": breakdown.source_quality.model_dump(mode="json"),
        "entity_importance": breakdown.entity_importance.model_dump(mode="json"),
        "topic_weight": breakdown.topic_weight.model_dump(mode="json"),
        "title_strength": breakdown.title_strength.model_dump(mode="json"),
        "editorial_fit": breakdown.editorial_fit.model_dump(mode="json"),
    }


def _cluster_scope(scored_cluster) -> str:
    scopes = [member.source_scope or ("local" if member.is_local_source else "unknown") for member in scored_cluster.cluster.member_articles]
    return Counter(scopes).most_common(1)[0][0] if scopes else "unknown"


def _cluster_category(scored_cluster) -> str:
    categories = [member.source_category or "general" for member in scored_cluster.cluster.member_articles]
    return Counter(categories).most_common(1)[0][0] if categories else "general"


def _cluster_editorial_priority(scored_cluster) -> int:
    priorities = [member.editorial_priority for member in scored_cluster.cluster.member_articles]
    return min(priorities) if priorities else 5


def _unique_source_count(scored_cluster) -> int:
    return len({member.source for member in scored_cluster.cluster.member_articles})


def _serialize_selection_candidate(scored_cluster, decision_by_cluster_id: dict[str, object]) -> dict[str, object]:
    decision = decision_by_cluster_id.get(scored_cluster.cluster.cluster_id)
    breakdown = scored_cluster.score_breakdown
    return {
        "cluster_id": scored_cluster.cluster.cluster_id,
        "top_headline": scored_cluster.cluster.representative_title,
        "cluster_size": len(scored_cluster.cluster.member_articles),
        "unique_source_count": _unique_source_count(scored_cluster),
        "source_scope": _cluster_scope(scored_cluster),
        "source_category": _cluster_category(scored_cluster),
        "editorial_priority": _cluster_editorial_priority(scored_cluster),
        "freshness_score": breakdown.recency.contribution,
        "editorial_fit": breakdown.editorial_fit.contribution,
        "final_score": scored_cluster.score_total,
        "decision": None if decision is None else decision.model_dump(mode="json"),
    }


def _write_story_selection_debug(scored_clusters, selection_result) -> None:
    decision_by_cluster_id = {decision.cluster_id: decision for decision in selection_result.decisions}
    candidates = [_serialize_selection_candidate(cluster, decision_by_cluster_id) for cluster in scored_clusters]
    selected_candidates = [candidate for candidate in candidates if candidate["decision"] and candidate["decision"]["status"] == "selected"]
    anchor_candidate = next((candidate for candidate in selected_candidates if candidate["unique_source_count"] >= 3), None)
    anchor_story = selected_candidates[0] if selected_candidates else None
    anchor_rule_satisfied = bool(anchor_story and anchor_story["unique_source_count"] >= 3)
    eligible_anchor_exists = any(candidate["unique_source_count"] >= 3 for candidate in candidates)

    payload = {
        "candidate_cluster_count": len(candidates),
        "selected_story_count": len(selected_candidates),
        "anchor_rule": {
            "required_unique_source_count": 3,
            "story_1_cluster_id": None if anchor_story is None else anchor_story["cluster_id"],
            "story_1_unique_source_count": None if anchor_story is None else anchor_story["unique_source_count"],
            "satisfied": anchor_rule_satisfied,
            "eligible_anchor_exists": eligible_anchor_exists,
            "note": None if anchor_rule_satisfied or eligible_anchor_exists else "No cluster reached the anchor-strength threshold of 3 unique sources.",
        },
        "top_candidate_clusters": candidates[:10],
        "selected_stories": selected_candidates,
        "all_candidates": candidates,
    }
    SELECTION_JSON_OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "STORY SELECTION DEBUG",
        "",
        f"Candidate clusters: {len(candidates)}",
        f"Selected stories: {len(selected_candidates)}",
        f"Anchor rule satisfied: {anchor_rule_satisfied}",
    ]
    if anchor_story is not None:
        lines.append(f"Anchor story: {anchor_story['cluster_id']} | sources={anchor_story['unique_source_count']} | score={anchor_story['final_score']}")
    elif not eligible_anchor_exists:
        lines.append("Anchor story: no eligible cluster reached 3 unique sources")
    lines.extend([
        "",
        "Top Candidate Clusters",
    ])
    for index, candidate in enumerate(candidates[:10], start=1):
        decision = candidate["decision"]
        lines.append(
            f"{index}. {candidate['cluster_id']} | score={candidate['final_score']} | sources={candidate['unique_source_count']} | "
            f"priority={candidate['editorial_priority']} | scope={candidate['source_scope']} | category={candidate['source_category']} | "
            f"decision={decision['status'] if decision else 'none'} | headline={candidate['top_headline']}"
        )
    SELECTION_TEXT_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_articles(personalization: UserPersonalization) -> tuple[list[FetchedArticle], list[dict[str, object]], dict[str, dict[str, object]], object]:
    watcher_service = SourceWatcherService()
    fetch_service = ArticleFetchService()
    article_service = ArticleService()

    base_source_configs, local_resolution = watcher_service.resolve_monitored_source_configs(personalization)
    source_by_domain: dict[str, dict[str, object]] = {}
    discovery_results: list[dict[str, object]] = []
    latest_items: list[tuple[object, object]] = []

    for source_config in base_source_configs:
        source_meta = {
            "source_id": source_config.source_id,
            "source_name": source_config.source_name,
            "source_type": source_config.source_type,
            "scope": source_config.scope,
            "category": source_config.category,
            "editorial_priority": source_config.editorial_priority,
            "region": source_config.region,
        }
        source_by_domain[_normalize_domain(source_config.source_url)] = source_meta
        try:
            latest = watcher_service.get_latest_content(source_config)
            latest_items.append((source_config, latest))
            discovery_results.append({**source_meta, "status": "success", "latest_item": latest.model_dump(mode="json")})
        except Exception as exc:  # pragma: no cover - diagnostic path
            discovery_results.append({**source_meta, "status": "error", "error": str(exc)})

    latest_items.sort(key=lambda item: item[1].published_at, reverse=True)

    provenance_by_url: dict[str, dict[str, object]] = {}
    articles: list[FetchedArticle] = []
    seen_urls: set[str] = set()

    for source_config, latest in latest_items:
        if len(articles) >= MAX_INPUT_ARTICLES:
            break
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
        mapped_meta = source_by_domain.get(_normalize_domain(rss_article.url), {})
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

    return articles, discovery_results, provenance_by_url, local_resolution


def _format_story(index: int, item) -> list[str]:
    lines = [
        f"Story {index}",
        item.story.headline,
        item.story.source_attribution,
        item.story.lead,
        item.story.body,
    ]
    if item.story.quotes:
        lines.append("Quotes:")
        lines.extend(f"- {quote}" for quote in item.story.quotes)
    return lines


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    personalization = _build_general_personalization()
    pipeline_service = EditorialPipelineService()
    validation_service = EditorialContractValidationService()

    articles, discovery_results, provenance_by_url, local_resolution = _build_articles(personalization)
    story_clusters = pipeline_service.clustering_service.cluster_articles(articles)
    scored_clusters = pipeline_service.scoring_service.score_clusters(story_clusters)
    selection_result = pipeline_service.selection_service.select_stories(
        scored_clusters,
        max_stories=8,
        editorial_preferences=personalization.editorial_preferences,
        personalization=personalization,
    )
    _write_story_selection_debug(scored_clusters, selection_result)
    final_briefing = pipeline_service.run_editorial_pipeline(
        articles=articles,
        personalization=personalization,
        max_stories=8,
    )
    validated_briefing, validation_result = validation_service.validate_bulletin(final_briefing)

    if not validation_result.passed:
        raise SystemExit(
            f"Editorial validation failed for neutral bulletin. Report: {validation_result.report_path}"
        )

    mixed_language_story_ids: list[str] = []
    selected_story_debug: list[dict[str, object]] = []
    for item in validated_briefing.story_items:
        language_issue = _detect_language_issue(item.story.summary_text)
        if language_issue["mixed_language_detected"]:
            mixed_language_story_ids.append(item.story.story_id)
        selected_story_debug.append(
            {
                "position": item.position,
                "cluster_id": item.story.cluster_id,
                "story_id": item.story.story_id,
                "story_type": item.story.story_type,
                "headline": item.story.headline,
                "lead": item.story.lead,
                "body": item.story.body,
                "source_attribution": item.story.source_attribution,
                "quotes": item.story.quotes,
                "editorial_notes": item.story.editorial_notes,
                "representative_title": item.story.representative_title,
                "summary_text": item.story.summary_text,
                "source_labels": item.story.source_labels,
                "score_total": item.story.score_total,
                "lead_type": item.story.lead_type,
                "topic_label": item.story.topic_label,
                "story_continuity_type": item.story.story_continuity_type,
                "policy_compliance": item.story.policy_compliance.model_dump(mode="json"),
                "generation_explanation": item.story.generation_explanation,
                "language_issue": language_issue,
                "member_provenance": dict(Counter(
                    provenance_by_url.get(member.url, {}).get("ingestion_kind", "unknown")
                    for member in next(
                        cluster.cluster.member_articles
                        for cluster in scored_clusters
                        if cluster.cluster.cluster_id == item.story.cluster_id
                    )
                )),
            }
        )

    candidate_scope_counts = dict(Counter((article.source_scope or "unknown") for article in articles))
    candidate_provenance_counts = dict(Counter(article.ingestion_kind for article in articles))

    debug_payload = {
        "user_profile": {
            "user": "debug_general",
            "personalization": personalization.model_dump(mode="json"),
        },
        "local_anchor_resolved": {
            "anchor": personalization.local_editorial_anchor(),
            "scope": personalization.local_editorial_anchor_scope(),
            "local_source_region_used": local_resolution.region_used,
            "local_source_count": local_resolution.source_count,
            "local_sources_enabled": local_resolution.local_sources_enabled,
            "local_source_registry_used": local_resolution.local_source_registry_used,
            "explanation": local_resolution.explanation,
        },
        "article_ingestion": {
            "total_candidate_articles": len(articles),
            "full_fetch_success_count": sum(1 for article in articles if article.ingestion_kind == "full_fetch"),
            "rss_fallback_count": sum(1 for article in articles if article.ingestion_kind == "rss_fallback"),
            "candidates_by_scope": candidate_scope_counts,
            "candidates_by_provenance": candidate_provenance_counts,
            "source_discovery_results": discovery_results,
        },
        "story_clustering": {
            "cluster_count": len(scored_clusters),
            "clusters": [
                {
                    "cluster_id": scored.cluster.cluster_id,
                    "representative_title": scored.cluster.representative_title,
                    "score_total": scored.score_total,
                    "score_breakdown": _serialize_score_breakdown(scored),
                    "member_articles": [member.model_dump(mode="json") for member in scored.cluster.member_articles],
                }
                for scored in scored_clusters
            ],
        },
        "final_written_bulletin": {
            "briefing_id": validated_briefing.briefing_id,
            "intro_text": validated_briefing.intro_text,
            "selected_stories": selected_story_debug,
            "outro_text": validated_briefing.outro_text,
            "sizing_explanation": validated_briefing.sizing_explanation,
        },
        "editorial_validation": {
            "passed": validation_result.passed,
            "report_path": validation_result.report_path,
            "summary": validation_result.summary,
            "blocking_violation_count": validation_result.blocking_violation_count,
            "warning_count": validation_result.warning_count,
            "auto_fix_count": validation_result.auto_fix_count,
            "warnings": [
                violation.model_dump(mode="json")
                for violation in ([*validation_result.violations] + [
                    violation
                    for story_result in validation_result.story_results
                    for violation in story_result.violations
                ])
                if violation.severity == "warning"
            ],
            "auto_fixes": [
                fix.model_dump(mode="json")
                for fix in ([*validation_result.auto_fixes] + [
                    fix
                    for story_result in validation_result.story_results
                    for fix in story_result.auto_fixes
                ])
            ],
        },
        "editorial_diagnostics": {
            "mixed_language_story_ids": mixed_language_story_ids,
        },
    }
    JSON_OUTPUT_PATH.write_text(json.dumps(debug_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "INTRO",
        "",
        validated_briefing.intro_text,
        "",
    ]
    for index, item in enumerate(validated_briefing.story_items, start=1):
        lines.extend(_format_story(index, item))
        lines.append("")
    lines.extend([
        "OUTRO",
        "",
        validated_briefing.outro_text,
        "",
        "Validation",
        f"- Story count: {len(validated_briefing.story_items)}",
        f"- Validation passed: {validation_result.passed}",
        f"- Auto-fixes applied: {validation_result.auto_fix_count}",
        f"- Warnings: {validation_result.warning_count}",
    ])
    TEXT_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {JSON_OUTPUT_PATH}")
    print(f"Wrote {TEXT_OUTPUT_PATH}")
    print(f"Wrote {SELECTION_JSON_OUTPUT_PATH}")
    print(f"Wrote {SELECTION_TEXT_OUTPUT_PATH}")
    print(validation_result.summary)


if __name__ == "__main__":
    main()
