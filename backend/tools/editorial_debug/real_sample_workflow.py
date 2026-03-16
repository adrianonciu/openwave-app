from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.article_fetch import FetchedArticle
from app.models.user_personalization import EditorialPreferenceProfile, GeographyPreferenceMix, ListenerProfile, UserPersonalization
from app.services.editorial_pipeline_service import EditorialPipelineService
from app.services.romanian_geo_resolver import resolve_listener_geography

REAL_SAMPLES_ROOT = REPO_ROOT / "tests" / "real_samples"
DEFAULT_SAMPLE_COUNTY = "Constanta"
DEFAULT_SAMPLE_USER = "Nicu"


def build_personalization(user: str, county: str) -> UserPersonalization:
    return UserPersonalization(
        listener_profile=ListenerProfile(first_name=user, country="Romania", region=county),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=35, national=40, international=25),
        ),
    )


def normalize_slug(value: str) -> str:
    return "_".join(str(value or "").strip().lower().split())


def build_sample_folder_name(user: str, county: str, sample_date: datetime | None = None) -> str:
    date_value = (sample_date or datetime.now()).date().isoformat()
    return f"{date_value}_{normalize_slug(user)}_{normalize_slug(county)}"


def latest_alias_dir(county: str, root: Path | None = None) -> Path:
    samples_root = root or REAL_SAMPLES_ROOT
    return samples_root / f"latest_{normalize_slug(county)}"


def default_sample_output_dir(user: str, county: str, root: Path | None = None) -> Path:
    samples_root = root or REAL_SAMPLES_ROOT
    return samples_root / build_sample_folder_name(user=user, county=county)


def resolve_real_sample_dir(explicit_dir: str | Path | None = None, root: Path | None = None) -> Path | None:
    samples_root = root or REAL_SAMPLES_ROOT
    if explicit_dir:
        candidate = Path(explicit_dir)
        return candidate if candidate.exists() else None
    latest_dirs = sorted(samples_root.glob("latest_*"), key=lambda item: item.stat().st_mtime, reverse=True) if samples_root.exists() else []
    for candidate in latest_dirs:
        if candidate.is_dir():
            return candidate
    dated_dirs = sorted([item for item in samples_root.iterdir() if item.is_dir()], key=lambda item: item.stat().st_mtime, reverse=True) if samples_root.exists() else []
    return dated_dirs[0] if dated_dirs else None


def load_real_sample(sample_dir: str | Path) -> dict[str, Any]:
    sample_path = Path(sample_dir)
    articles_payload = json.loads((sample_path / "articles.json").read_text(encoding="utf-8"))
    metadata = json.loads((sample_path / "metadata.json").read_text(encoding="utf-8"))
    preview_payload = json.loads((sample_path / "preview.json").read_text(encoding="utf-8"))
    articles = [FetchedArticle(**item) for item in articles_payload.get("articles", [])]
    personalization = UserPersonalization(**metadata.get("personalization", {}))
    return {
        "sample_dir": sample_path,
        "articles": articles,
        "metadata": metadata,
        "preview_payload": preview_payload,
        "personalization": personalization,
    }


def build_preview_payload_from_articles(
    articles: list[FetchedArticle],
    personalization: UserPersonalization,
    mode_label: str,
    geo_tagging_preview_path: Path,
    news_clustering_preview_path: Path | None = None,
    registry_audit_path: Path | None = None,
    registry_audit: dict[str, Any] | None = None,
    ingestion_debug: dict[str, Any] | None = None,
    sample_origin: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    pipeline_service = EditorialPipelineService()
    geo_service = pipeline_service.live_source_ingestion_service.geo_tagging_service
    needs_geo = any(article.geo_scope is None for article in articles)
    geo_articles = articles
    geo_debug = geo_service.build_debug_summary(articles)
    if needs_geo:
        geo_articles, geo_debug = geo_service.tag_articles(articles)

    resolved_geo = resolve_listener_geography(
        city=personalization.listener_profile.city,
        region=personalization.listener_profile.region,
    )
    target_county = str(resolved_geo.resolved_county or personalization.listener_profile.region or DEFAULT_SAMPLE_COUNTY)

    if not geo_articles:
        geo_preview_payload = {
            "stories": [],
            "validation_summary": geo_debug,
        }
        clustering_preview = pipeline_service.clustering_service.build_debug_preview([])
        payload = {
            "mode": mode_label,
            "debug_source": sample_origin or mode_label,
            "listener_name": personalization.listener_profile.first_name or DEFAULT_SAMPLE_USER,
            "listener_county": resolved_geo.resolved_county or target_county,
            "resolved_user_county": resolved_geo.resolved_county or target_county,
            "resolved_user_region": resolved_geo.resolved_macro_region,
            "county_first_local_selection": True,
            "article_count": 0,
            "story_count": 0,
            "local_story_count_from_county": 0,
            "local_story_count_from_regional_fallback": 0,
            "local_story_count_from_constanta_county": 0,
            "geo_tagging_preview_path": str(geo_tagging_preview_path),
            "news_clustering_preview_path": str(news_clustering_preview_path) if news_clustering_preview_path else None,
            "geo_tagged_county": geo_debug.get("geo_tagged_county", 0),
            "cluster_count": clustering_preview.get("cluster_count", 0),
            "average_cluster_size": clustering_preview.get("average_cluster_size", 0.0),
            "largest_cluster_size": clustering_preview.get("largest_cluster_size", 0),
            "duplicate_articles_collapsed": clustering_preview.get("duplicate_articles_collapsed", 0),
            "clusters_with_multiple_sources": clustering_preview.get("clusters_with_multiple_sources", 0),
            "geo_tagged_regional": geo_debug.get("geo_tagged_regional", 0),
            "geo_tagged_national": geo_debug.get("geo_tagged_national", 0),
            "geo_tagged_international": geo_debug.get("geo_tagged_international", 0),
            "stories_with_multiple_county_hits": geo_debug.get("stories_with_multiple_county_hits", 0),
            "stories": [],
            "media_source_credits": [],
            "written_source_credits_emitted": False,
            "registry_audit_path": str(registry_audit_path) if registry_audit_path else None,
            "registry_audit_source_count": (registry_audit or {}).get("source_count"),
            "ingestion_debug": ingestion_debug or {},
        }
        return payload, geo_preview_payload, clustering_preview

    story_clusters = pipeline_service.clustering_service.cluster_articles(geo_articles)
    clustering_preview = pipeline_service.clustering_service.build_debug_preview(story_clusters)
    scored_clusters = pipeline_service.scoring_service.score_clusters(story_clusters)
    pipeline_service.story_family_service.attach_story_families(scored_clusters)
    selection_result = pipeline_service.selection_service.select_stories(
        scored_clusters,
        max_stories=15,
        editorial_preferences=personalization.editorial_preferences,
        personalization=personalization,
    )
    profile_name = (
        selection_result.selected_clusters[0].editorial_profile_used
        if selection_result.selected_clusters and selection_result.selected_clusters[0].editorial_profile_used
        else "generalist"
    )
    shaping_result = pipeline_service.bulletin_shaping_service.shape_selected_clusters(
        selection_result.selected_clusters,
        profile_name=profile_name,
    )
    final_briefing = pipeline_service.run_editorial_pipeline(
        articles=geo_articles,
        personalization=personalization,
        max_stories=15,
    )

    cluster_by_id = {cluster.cluster.cluster_id: cluster for cluster in shaping_result.ordered_clusters}
    story_rows: list[dict[str, Any]] = []
    for position, item in enumerate(final_briefing.story_items, start=1):
        cluster = cluster_by_id.get(item.story.cluster_id)
        members = sorted(list(cluster.cluster.member_articles), key=lambda member: member.published_at, reverse=True) if cluster is not None else []
        primary_member = members[0] if members else None
        original_urls = sorted({member.url for member in members})[:5]
        source_labels = item.story.source_labels
        story_rows.append({
            "position": position,
            "headline": item.story.headline,
            "summary_text": item.story.summary_text,
            "source_name": primary_member.source if primary_member is not None else (source_labels[0] if source_labels else None),
            "original_url": primary_member.url if primary_member is not None else (original_urls[0] if original_urls else None),
            "source_labels": source_labels,
            "original_urls": original_urls,
            "scope": next((member.source_scope for member in members if member.source_scope), "unknown"),
            "local_origin_type": _cluster_local_origin_type(cluster, target_county) if cluster is not None else "unknown",
        })

    geo_preview_payload = geo_service.build_preview_payload(geo_articles)
    geo_summary = geo_preview_payload["validation_summary"]
    payload = {
        "mode": mode_label,
        "debug_source": sample_origin or mode_label,
        "listener_name": personalization.listener_profile.first_name or DEFAULT_SAMPLE_USER,
        "listener_county": final_briefing.local_source_region_used or target_county,
        "resolved_user_county": final_briefing.local_source_region_used or target_county,
        "resolved_user_region": resolve_listener_geography(city=None, region=target_county).resolved_macro_region,
        "county_first_local_selection": True,
        "article_count": len(geo_articles),
        "story_count": len(story_rows),
        "local_story_count_from_county": sum(1 for row in story_rows if row["local_origin_type"] == "county"),
        "local_story_count_from_regional_fallback": sum(1 for row in story_rows if row["local_origin_type"] == "fallback_region"),
        "local_story_count_from_constanta_county": sum(1 for row in story_rows if row["local_origin_type"] == "county"),
        "geo_tagging_preview_path": str(geo_tagging_preview_path),
        "news_clustering_preview_path": str(news_clustering_preview_path) if news_clustering_preview_path else None,
        "geo_tagged_county": geo_summary["geo_tagged_county"],
        "cluster_count": clustering_preview["cluster_count"],
        "average_cluster_size": clustering_preview["average_cluster_size"],
        "largest_cluster_size": clustering_preview["largest_cluster_size"],
        "duplicate_articles_collapsed": clustering_preview["duplicate_articles_collapsed"],
        "clusters_with_multiple_sources": clustering_preview["clusters_with_multiple_sources"],
        "geo_tagged_regional": geo_summary["geo_tagged_regional"],
        "geo_tagged_national": geo_summary["geo_tagged_national"],
        "geo_tagged_international": geo_summary["geo_tagged_international"],
        "stories_with_multiple_county_hits": geo_summary["stories_with_multiple_county_hits"],
        "stories": story_rows,
        "media_source_credits": final_briefing.media_source_credits,
        "written_source_credits_emitted": bool(final_briefing.media_source_credits),
        "registry_audit_path": str(registry_audit_path) if registry_audit_path else None,
        "registry_audit_source_count": (registry_audit or {}).get("source_count"),
        "ingestion_debug": ingestion_debug or {},
    }
    return payload, geo_preview_payload, clustering_preview


def save_real_sample_bundle(
    output_dir: str | Path,
    preview_payload: dict[str, Any],
    preview_text: str,
    bulletin_text: str,
    articles: list[FetchedArticle],
    personalization: UserPersonalization,
    geo_preview_payload: dict[str, Any],
    registry_audit: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    sample_dir = Path(output_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)
    registry_payload = registry_audit or {}
    metadata_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": preview_payload.get("mode"),
        "user": personalization.listener_profile.first_name,
        "county": personalization.listener_profile.region,
        "personalization": personalization.model_dump(mode="json"),
        **(metadata or {}),
    }
    (sample_dir / "preview.json").write_text(json.dumps(preview_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (sample_dir / "preview.txt").write_text(preview_text, encoding="utf-8")
    (sample_dir / "bulletin.txt").write_text(bulletin_text, encoding="utf-8")
    (sample_dir / "articles.json").write_text(
        json.dumps({"articles": [article.model_dump(mode="json") for article in articles]}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (sample_dir / "metadata.json").write_text(json.dumps(metadata_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (sample_dir / "geo_tagging_preview.json").write_text(json.dumps(geo_preview_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if registry_payload:
        (sample_dir / "source_registry_audit.json").write_text(json.dumps(registry_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    county = personalization.listener_profile.region or DEFAULT_SAMPLE_COUNTY
    alias_dir = latest_alias_dir(county=county)
    if alias_dir.exists():
        shutil.rmtree(alias_dir)
    shutil.copytree(sample_dir, alias_dir)
    return sample_dir


def _cluster_local_origin_type(cluster, target_county: str) -> str:
    county_key = (target_county or "").strip().lower()
    local_members = [member for member in cluster.cluster.member_articles if member.is_local_source]
    local_regions = {str(member.source_region or "").strip().lower() for member in local_members if member.source_region}
    detected_counties = {str(member.county_detected or "").strip().lower() for member in local_members if member.county_detected}
    scopes = {member.source_scope for member in cluster.cluster.member_articles}
    if "international" in scopes and len(local_members) <= 1:
        return "international"
    if county_key and (county_key in local_regions or county_key in detected_counties):
        return "county"
    if local_regions or detected_counties:
        return "fallback_region"
    if "international" in scopes:
        return "international"
    return "national"
