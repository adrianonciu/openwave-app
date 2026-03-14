from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
import json
import re
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
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
from app.services.briefing_assembly_service import BriefingAssemblyService
from app.services.bulletin_sizing_service import BulletinSizingService
from app.services.editorial_pipeline_service import EditorialPipelineService
from app.services.news_clustering_service import NewsClusteringService
from app.services.source_watcher_service import SourceWatcherService
from app.services.story_scoring_service import StoryScoringService
from app.services.story_selection_service import StorySelectionService
from app.services.story_summary_generator_service import StorySummaryGeneratorService

OUTPUT_DIR = BACKEND_ROOT / 'debug_output'
JSON_OUTPUT_PATH = OUTPUT_DIR / 'written_bulletin_debug.json'
TEXT_OUTPUT_PATH = OUTPUT_DIR / 'written_bulletin_adrian.txt'
MAX_INPUT_ARTICLES = 14
MAX_RSS_FALLBACK_ARTICLES = 4
ENGLISH_MARKERS = {
    'the', 'and', 'with', 'from', 'under', 'against', 'whose', 'during', 'officials',
    'says', 'say', 'family', 'suspect', 'wait', 'world', 'news', 'teacher', 'died',
    'dropped', 'charges', 'fire', 'drone', 'airstrike', 'school', 'deliberate'
}
ROMANIAN_MARKERS = {
    'si', 'sau', 'este', 'sunt', 'pentru', 'care', 'din', 'catre', 'dupa', 'potrivit',
    'spune', 'transmite', 'arata', 'masura', 'buletin', 'stiri', 'momentului', 'atentie'
}


def _normalize_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower().strip()
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


def _build_personalization() -> UserPersonalization:
    return UserPersonalization(
        listener_profile=ListenerProfile(
            first_name='Adrian',
            country='Romania',
            region='Iasi',
            city='Iasi',
        ),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=10, national=50, international=40),
            domains=DomainPreferenceMix(
                politics=50,
                economy=15,
                sport=35,
                entertainment=0,
                education=0,
                health=0,
                tech=0,
            ),
        ),
    )


def _detect_language_issue(text: str) -> dict[str, object]:
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", text.lower())
    english_hits = sorted({token for token in tokens if token in ENGLISH_MARKERS})
    romanian_hits = sorted({token for token in tokens if token in ROMANIAN_MARKERS})
    mixed = len(english_hits) >= 2
    return {
        'mixed_language_detected': mixed,
        'english_markers': english_hits,
        'romanian_markers': romanian_hits,
    }


def _serialize_score_breakdown(scored_cluster) -> dict[str, object]:
    breakdown = scored_cluster.score_breakdown
    return {
        'recency': breakdown.recency.model_dump(mode='json'),
        'source_count': breakdown.source_count.model_dump(mode='json'),
        'source_quality': breakdown.source_quality.model_dump(mode='json'),
        'entity_importance': breakdown.entity_importance.model_dump(mode='json'),
        'topic_weight': breakdown.topic_weight.model_dump(mode='json'),
        'title_strength': breakdown.title_strength.model_dump(mode='json'),
    }


def _format_story_block(index: int, item) -> list[str]:
    lines = [
        f'Story {index}',
        f'Story Type: {item.story.story_type}',
        f'Headline: {item.story.headline}',
        f'Lead: {item.story.lead}',
        f'Source Attribution: {item.story.source_attribution}',
        f'Body: {item.story.body}',
        f'Quotes: {" | ".join(item.story.quotes) if item.story.quotes else "None"}',
        f'Editorial Notes: {", ".join(item.story.editorial_notes) if item.story.editorial_notes else "None"}',
        f'Source: {", ".join(item.story.source_labels) or "Unknown"}',
        f'Summary: {item.story.summary_text}',
        f'Pacing: {item.pacing_label}',
        f'Continuity: {item.story.story_continuity_type}',
    ]
    if item.perspective_segments:
        lines.append('Perspectives:')
        for perspective in item.perspective_segments:
            lines.append(f'- {perspective.title}: {perspective.narration_text}')
    return lines


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    personalization = _build_personalization()
    watcher_service = SourceWatcherService()
    fetch_service = ArticleFetchService()
    article_service = ArticleService()
    clustering_service = NewsClusteringService()
    scoring_service = StoryScoringService()
    selection_service = StorySelectionService()
    summary_service = StorySummaryGeneratorService()
    assembly_service = BriefingAssemblyService()
    sizing_service = BulletinSizingService()
    pipeline_service = EditorialPipelineService()

    base_source_configs, local_resolution = watcher_service.resolve_monitored_source_configs(personalization)
    source_by_domain: dict[str, dict[str, object]] = {}
    local_source_names = set()
    discovery_results = []
    latest_items = []

    for source_config in base_source_configs:
        source_meta = {
            'source_id': source_config.source_id,
            'source_name': source_config.source_name,
            'source_type': source_config.source_type,
            'scope': source_config.scope,
            'category': source_config.category,
            'editorial_priority': source_config.editorial_priority,
            'region': source_config.region,
        }
        source_by_domain[_normalize_domain(source_config.source_url)] = source_meta
        if source_config.scope == 'local':
            local_source_names.add(source_config.source_name)
        try:
            latest = watcher_service.get_latest_content(source_config)
            latest_items.append((source_config, latest))
            discovery_results.append({
                **source_meta,
                'status': 'success',
                'latest_item': latest.model_dump(mode='json'),
            })
        except Exception as exc:
            discovery_results.append({
                **source_meta,
                'status': 'error',
                'error': str(exc),
            })

    latest_items.sort(key=lambda item: item[1].published_at, reverse=True)

    provenance_by_url: dict[str, dict[str, object]] = {}
    articles: list[FetchedArticle] = []
    article_ingestion_results = []
    seen_urls: set[str] = set()

    for source_config, latest in latest_items:
        if latest.url in seen_urls:
            continue
        seen_urls.add(latest.url)
        fetch_result = fetch_service.fetch_article(latest)
        if fetch_result.status == 'success' and fetch_result.article is not None:
            article = fetch_result.article.model_copy(
                update={
                    'ingestion_kind': 'full_fetch',
                    'editorial_priority': source_config.editorial_priority,
                    'source_scope': source_config.scope,
                    'source_category': source_config.category,
                    'is_local_source': source_config.scope == 'local',
                }
            )
            articles.append(article)
            provenance_by_url[article.url] = {
                'ingestion_kind': 'full_fetch',
                'source_id': source_config.source_id,
                'scope': source_config.scope,
                'category': source_config.category,
                'editorial_priority': source_config.editorial_priority,
                'source_type': source_config.source_type,
                'is_local_source': source_config.scope == 'local',
            }
            article_ingestion_results.append({
                'url': article.url,
                'title': article.title,
                'source': article.source,
                'status': fetch_result.status,
                'ingestion_kind': 'full_fetch',
                'extraction_method': fetch_result.extraction_method,
                'scope': source_config.scope,
                'category': source_config.category,
                'editorial_priority': source_config.editorial_priority,
                'is_local_source': source_config.scope == 'local',
            })
        else:
            article_ingestion_results.append({
                'url': latest.url,
                'title': latest.title,
                'source': latest.source_name,
                'status': fetch_result.status,
                'ingestion_kind': 'failed_full_fetch',
                'error': fetch_result.error_message,
                'scope': source_config.scope,
                'category': source_config.category,
                'editorial_priority': source_config.editorial_priority,
                'is_local_source': source_config.scope == 'local',
            })

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
            ingestion_kind='rss_fallback',
            editorial_priority=mapped_meta.get('editorial_priority', 3),
            source_scope=mapped_meta.get('scope'),
            source_category=mapped_meta.get('category'),
            is_local_source=mapped_meta.get('scope') == 'local',
        )
        articles.append(article)
        provenance_by_url[article.url] = {
            'ingestion_kind': 'rss_fallback',
            'source_id': mapped_meta.get('source_id'),
            'scope': mapped_meta.get('scope'),
            'category': mapped_meta.get('category'),
            'editorial_priority': mapped_meta.get('editorial_priority', 3),
            'source_type': mapped_meta.get('source_type'),
            'is_local_source': mapped_meta.get('scope') == 'local',
        }
        article_ingestion_results.append({
            'url': article.url,
            'title': article.title,
            'source': article.source,
            'status': 'success',
            'ingestion_kind': 'rss_fallback',
            'extraction_method': None,
            'scope': mapped_meta.get('scope'),
            'category': mapped_meta.get('category'),
            'editorial_priority': mapped_meta.get('editorial_priority', 3),
            'is_local_source': mapped_meta.get('scope') == 'local',
        })
        rss_articles_added += 1

    previous_clusters = pipeline_service._load_previous_bulletin_clusters(None)
    story_clusters = clustering_service.cluster_articles(articles)
    scored_clusters = scoring_service.score_clusters(story_clusters)
    selection_result = selection_service.select_stories(
        scored_clusters,
        personalization=personalization,
    )

    summary_service.reset_variation_state()
    generated_summaries = [
        summary_service.generate_story_summary(cluster, previous_bulletin_clusters=previous_clusters)
        for cluster in selection_result.selected_clusters
    ]
    briefing_draft = assembly_service.assemble_briefing(
        generated_summaries,
        personalization=personalization,
    )
    sized_briefing = sizing_service.size_briefing(briefing_draft)

    decision_by_cluster = {decision.cluster_id: decision for decision in selection_result.decisions}
    summary_by_cluster = {summary.cluster_id: summary for summary in generated_summaries}

    cluster_debug = []
    for scored in scored_clusters:
        member_urls = [member.url for member in scored.cluster.member_articles]
        provenance_counts = Counter(
            provenance_by_url.get(url, {}).get('ingestion_kind', 'unknown')
            for url in member_urls
        )
        cluster_debug.append({
            'cluster_id': scored.cluster.cluster_id,
            'representative_title': scored.cluster.representative_title,
            'member_articles': [member.model_dump(mode='json') for member in scored.cluster.member_articles],
            'member_provenance': dict(provenance_counts),
            'contains_local_source': any(provenance_by_url.get(url, {}).get('is_local_source', False) for url in member_urls),
            'source_scopes': sorted({member.source_scope or 'unknown' for member in scored.cluster.member_articles}),
            'source_categories': sorted({member.source_category or 'general' for member in scored.cluster.member_articles}),
            'editorial_priorities': sorted({member.editorial_priority for member in scored.cluster.member_articles}),
            'score_total': scored.score_total,
            'score_breakdown': _serialize_score_breakdown(scored),
            'quality_guardrail_explanation': scored.score_breakdown.editorial_fit.explanation,
            'downranked_for_quality': 'low-value' in scored.score_breakdown.editorial_fit.explanation or 'English-heavy' in scored.score_breakdown.editorial_fit.explanation or 'soft-news' in scored.score_breakdown.editorial_fit.explanation,
            'scoring_explanation': scored.scoring_explanation,
        })

    selected_story_debug = []
    mixed_language_story_ids = []
    for item in sized_briefing.story_items:
        decision = decision_by_cluster.get(item.story.cluster_id)
        summary = summary_by_cluster[item.story.cluster_id]
        member_urls = [member.url for member in next(cluster.cluster.member_articles for cluster in scored_clusters if cluster.cluster.cluster_id == item.story.cluster_id)]
        provenance_counts = Counter(
            provenance_by_url.get(url, {}).get('ingestion_kind', 'unknown')
            for url in member_urls
        )
        language_issue = _detect_language_issue(summary.summary_text)
        if language_issue['mixed_language_detected']:
            mixed_language_story_ids.append(item.story.cluster_id)
        selected_story_debug.append({
            'position': item.position,
            'cluster_id': item.story.cluster_id,
            'story_id': summary.story_id,
            'story_type': summary.story_type,
            'headline': summary.headline,
            'lead': summary.lead,
            'body': summary.body,
            'source_attribution': summary.source_attribution,
            'quotes': summary.quotes,
            'editorial_notes': summary.editorial_notes,
            'representative_title': summary.representative_title,
            'summary_text': summary.summary_text,
            'source_labels': summary.source_labels,
            'source_scopes': sorted({member.source_scope or 'unknown' for member in next(cluster.cluster.member_articles for cluster in scored_clusters if cluster.cluster.cluster_id == item.story.cluster_id)}),
            'source_categories': sorted({member.source_category or 'general' for member in next(cluster.cluster.member_articles for cluster in scored_clusters if cluster.cluster.cluster_id == item.story.cluster_id)}),
            'editorial_priorities': sorted({member.editorial_priority for member in next(cluster.cluster.member_articles for cluster in scored_clusters if cluster.cluster.cluster_id == item.story.cluster_id)}),
            'score_total': summary.score_total,
            'lead_type': summary.lead_type,
            'topic_label': summary.topic_label,
            'story_continuity_type': summary.story_continuity_type,
            'policy_compliance': summary.policy_compliance.model_dump(mode='json'),
            'generation_explanation': summary.generation_explanation,
            'decision': decision.model_dump(mode='json') if decision else None,
            'member_provenance': dict(provenance_counts),
            'quality_guardrail_explanation': next(cluster.score_breakdown.editorial_fit.explanation for cluster in scored_clusters if cluster.cluster.cluster_id == item.story.cluster_id),
            'downranked_for_quality': 'low-value' in next(cluster.score_breakdown.editorial_fit.explanation for cluster in scored_clusters if cluster.cluster.cluster_id == item.story.cluster_id) or 'English-heavy' in next(cluster.score_breakdown.editorial_fit.explanation for cluster in scored_clusters if cluster.cluster.cluster_id == item.story.cluster_id) or 'soft-news' in next(cluster.score_breakdown.editorial_fit.explanation for cluster in scored_clusters if cluster.cluster.cluster_id == item.story.cluster_id),
            'perspective_count': len(item.perspective_segments),
            'language_issue': language_issue,
        })

    local_candidate_articles = [
        article for article in article_ingestion_results if article.get('is_local_source') and article.get('status') == 'success'
    ]
    candidate_scope_counts = dict(Counter((article.get('scope') or 'unknown') for article in article_ingestion_results if article.get('status') == 'success'))
    candidate_provenance_counts = dict(Counter(article.get('ingestion_kind') or 'unknown' for article in article_ingestion_results if article.get('status') == 'success'))
    local_source_status = {
        result['source_name']: {
            'status': result['status'],
            'latest_item': result.get('latest_item'),
            'error': result.get('error'),
        }
        for result in discovery_results
        if result.get('scope') == 'local'
    }
    local_selected_stories = [
        story for story in selected_story_debug if story['decision'] and story['decision'].get('regional_relevance') == 'region_match'
    ]
    perspective_triggered = any(item.perspective_segments for item in sized_briefing.story_items)
    rss_fallback_candidates = sum(1 for article in article_ingestion_results if article.get('ingestion_kind') == 'rss_fallback')
    rss_fallback_selected = sum(1 for story in selected_story_debug if story['member_provenance'].get('rss_fallback', 0) > 0)

    debug_payload = {
        'user_profile': personalization.model_dump(mode='json'),
        'local_anchor_resolved': {
            'anchor': personalization.local_editorial_anchor(),
            'scope': personalization.local_editorial_anchor_scope(),
            'local_source_region_used': local_resolution.region_used,
            'local_source_count': local_resolution.source_count,
            'local_sources_enabled': local_resolution.local_sources_enabled,
            'local_source_registry_used': local_resolution.local_source_registry_used,
            'explanation': local_resolution.explanation,
        },
        'source_discovery': {
            'total_sources_checked': len(base_source_configs),
            'results': discovery_results,
        },
        'article_ingestion': {
            'total_candidate_articles': len(articles),
            'full_fetch_success_count': sum(1 for article in article_ingestion_results if article.get('ingestion_kind') == 'full_fetch'),
            'rss_fallback_count': rss_articles_added,
            'candidates_by_scope': candidate_scope_counts,
            'candidates_by_provenance': candidate_provenance_counts,
            'results': article_ingestion_results,
        },
        'story_clustering': {
            'cluster_count': len(story_clusters),
            'clusters': cluster_debug,
        },
        'story_selection': {
            'selection_stats': selection_result.selection_stats.model_dump(mode='json'),
            'selection_explanation': selection_result.selection_explanation,
            'stories_considered': [
                {
                    **decision.model_dump(mode='json'),
                    'source_categories': sorted({member.source_category or 'general' for member in next(cluster.cluster.member_articles for cluster in scored_clusters if cluster.cluster.cluster_id == decision.cluster_id)}),
                    'source_scopes': sorted({member.source_scope or 'unknown' for member in next(cluster.cluster.member_articles for cluster in scored_clusters if cluster.cluster.cluster_id == decision.cluster_id)}),
                    'editorial_priorities': sorted({member.editorial_priority for member in next(cluster.cluster.member_articles for cluster in scored_clusters if cluster.cluster.cluster_id == decision.cluster_id)}),
                    'provenance': next(dict(Counter(member.ingestion_kind for member in cluster.cluster.member_articles)) for cluster in scored_clusters if cluster.cluster.cluster_id == decision.cluster_id),
                    'quality_guardrail_explanation': next(cluster.score_breakdown.editorial_fit.explanation for cluster in scored_clusters if cluster.cluster.cluster_id == decision.cluster_id),
                    'downranked_for_quality': 'low-value' in next(cluster.score_breakdown.editorial_fit.explanation for cluster in scored_clusters if cluster.cluster.cluster_id == decision.cluster_id) or 'English-heavy' in next(cluster.score_breakdown.editorial_fit.explanation for cluster in scored_clusters if cluster.cluster.cluster_id == decision.cluster_id) or 'soft-news' in next(cluster.score_breakdown.editorial_fit.explanation for cluster in scored_clusters if cluster.cluster.cluster_id == decision.cluster_id),
                }
                for decision in selection_result.decisions
            ],
        },
        'final_written_bulletin': {
            'briefing_id': sized_briefing.briefing_id,
            'intro_text': sized_briefing.intro_text,
            'selected_stories': selected_story_debug,
            'outro_text': sized_briefing.outro_text,
            'sizing_explanation': sized_briefing.sizing_explanation,
            'sizing_actions': [action.model_dump(mode='json') for action in sized_briefing.sizing_actions],
        },
        'editorial_diagnostics': {
            'local_story_count': len(local_selected_stories),
            'iasi_local_candidate_count': len(local_candidate_articles),
            'iasi_local_sources_produced_candidates': len(local_candidate_articles) > 0,
            'local_parser_status_by_source': local_source_status,
            'perspective_pairs_triggered': perspective_triggered,
            'mixed_language_story_ids': mixed_language_story_ids,
            'rss_fallback_usage_rate': round(rss_fallback_candidates / max(len(articles), 1), 2),
            'rss_fallback_selected_story_count': rss_fallback_selected,
            'questions': {
                'correct_main_stories_selected': 'Inspect selected_stories and selection decisions manually.',
                'personalization_influenced_selection': len(local_selected_stories) > 0,
                'iasi_sources_contributed': len(local_candidate_articles) > 0,
                'summaries_clean_romanian': not mixed_language_story_ids,
                'rss_fallback_dominating_selection': rss_fallback_selected >= max(1, len(selected_story_debug) // 2),
            },
        },
    }

    JSON_OUTPUT_PATH.write_text(
        json.dumps(debug_payload, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )

    lines = [
        '--------------------------------',
        'OPENWAVE WRITTEN BULLETIN',
        'User: Adrian',
        'Location: Iasi',
        '--------------------------------',
        '',
        'Intro',
        sized_briefing.intro_text,
        '',
    ]
    for index, item in enumerate(sized_briefing.story_items, start=1):
        lines.extend(_format_story_block(index, item))
        lines.append('')
    lines.extend([
        'Outro',
        sized_briefing.outro_text,
        '',
        'Editorial diagnostics',
        f'- Candidate articles: {len(articles)}',
        f'- Candidates by scope: {candidate_scope_counts}',
        f'- Candidates by provenance: {candidate_provenance_counts}',
        f'- Clusters created: {len(story_clusters)}',
        f'- Selected stories: {len(sized_briefing.story_items)}',
        f'- Local stories selected: {len(local_selected_stories)}',
        f'- Iasi local candidate count: {len(local_candidate_articles)}',
        f'- Iasi sources produced candidates: {len(local_candidate_articles) > 0}',
        f'- Local parser status by source: {local_source_status}',
        f'- Perspective pairs triggered: {perspective_triggered}',
        f'- Mixed Romanian/English detected: {bool(mixed_language_story_ids)}',
        f'- Mixed-language story ids: {", ".join(mixed_language_story_ids) or "none"}',
        f'- RSS fallback usage rate: {round(rss_fallback_candidates / max(len(articles), 1), 2)}',
        f'- RSS fallback selected stories: {rss_fallback_selected}',
        f'- Sizing explanation: {sized_briefing.sizing_explanation}',
    ])
    TEXT_OUTPUT_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(f'Wrote {JSON_OUTPUT_PATH}')
    print(f'Wrote {TEXT_OUTPUT_PATH}')


if __name__ == '__main__':
    main()
