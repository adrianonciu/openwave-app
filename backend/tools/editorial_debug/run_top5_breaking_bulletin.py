from __future__ import annotations

from pathlib import Path
import json
import sys
from collections import Counter

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

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


EXCLUDED_NATIONAL_CATEGORIES = {"sport", "entertainment", "lifestyle", "culture", "tv"}
PLACEHOLDER_HEADLINES = {"actualitate", "stiri", "stiri", "live", "breaking", "updates", "context"}


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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    personalization = _build_general_personalization()
    pipeline_service = EditorialPipelineService()

    articles, _, _ = _build_articles(personalization)
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
            f"Freshness: {item['freshness_score']}",
            f"Score: {item['final_score']}",
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
            f"Freshness: {item['freshness_score']}",
            f"Score: {item['final_score']}",
            "",
        ])

    TEXT_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {TEXT_OUTPUT_PATH}")
    print(f"Wrote {JSON_OUTPUT_PATH}")
    print(json.dumps({
        "national": len(national_top5),
        "global": len(global_top5),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
