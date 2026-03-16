from __future__ import annotations

from datetime import UTC, datetime
from difflib import SequenceMatcher
import json
from pathlib import Path
from typing import Any

from app.models.article_fetch import FetchedArticle
from app.models.live_source_ingestion import LiveStoryCandidate, SourceRegistryEntry
from app.models.user_personalization import UserPersonalization
from app.services.article_fetch_and_clean_service import ArticleFetchAndCleanService
from app.services.geo_tagging_service import GeoTaggingService
from app.services.source_registry_service import SourceRegistryService
from app.services.source_watcher_service import SourceWatcherService

FEED_CACHE_PATH = Path(__file__).resolve().parents[2] / 'data' / 'live_source_feed_cache.json'
FEED_CACHE_TTL_SECONDS = 1800
DEFAULT_ITEMS_PER_SOURCE = 3
DEFAULT_MAX_FULL_FETCH = 80
DEFAULT_MAX_RSS_FALLBACK = 35
FUZZY_DEDUPE_THRESHOLD = 0.85


class LiveSourceIngestionService:
    def __init__(self) -> None:
        self.source_watcher_service = SourceWatcherService()
        self.source_registry_service = SourceRegistryService()
        self.article_fetch_and_clean_service = ArticleFetchAndCleanService()
        self.geo_tagging_service = GeoTaggingService()

    def load_registry(self) -> list[SourceRegistryEntry]:
        return self.source_registry_service.load_registry()

    def write_registry(self) -> list[SourceRegistryEntry]:
        return self.source_registry_service.write_registry_file()

    def fetch_story_candidates(
        self,
        personalization: UserPersonalization | None = None,
        items_per_source: int = DEFAULT_ITEMS_PER_SOURCE,
    ) -> tuple[list[LiveStoryCandidate], dict[str, Any]]:
        self.write_registry()
        monitored_sources, local_resolution = self.source_watcher_service.resolve_monitored_source_configs(personalization)
        active_source_ids = {config.source_id for config in monitored_sources}
        fallback_sources = self.source_registry_service.build_live_fallback_source_configs(exclude_source_ids=active_source_ids)
        monitored_sources = list(monitored_sources) + fallback_sources
        active_source_ids = {config.source_id for config in monitored_sources}
        active_source_keys = {self._source_live_key(config.region, config.source_name) for config in monitored_sources}
        audit = self.source_registry_service.build_registry_audit(
            active_source_ids=active_source_ids,
            active_source_keys=active_source_keys,
        )

        candidates: list[LiveStoryCandidate] = []
        source_results: list[dict[str, Any]] = []
        for source_config in monitored_sources:
            try:
                recent_items = self._recent_items_with_cache(source_config, limit=items_per_source)
                source_results.append({
                    'source_id': source_config.source_id,
                    'source_name': source_config.source_name,
                    'status': 'success',
                    'item_count': len(recent_items),
                })
            except Exception as exc:
                source_results.append({
                    'source_id': source_config.source_id,
                    'source_name': source_config.source_name,
                    'status': 'error',
                    'error': str(exc),
                })
                continue

            access_method = self._access_method_for_config(source_config)
            status = 'usable' if source_config.enabled else 'fallback_only'
            for item in recent_items:
                summary_text = (getattr(item, 'summary', None) or getattr(item, 'title', '')).strip()
                candidates.append(
                    LiveStoryCandidate(
                        source_id=source_config.source_id,
                        source_name=source_config.source_name,
                        source_scope='local' if source_config.scope == 'local' or source_config.source_type == 'local_county' else (source_config.scope or 'national'),
                        county=source_config.region if source_config.source_type == 'local_county' else None,
                        region=source_config.region,
                        title=item.title,
                        summary=summary_text,
                        original_url=item.url,
                        published_at=item.published_at,
                        author=None,
                        language=source_config.language,
                        fetch_timestamp=datetime.now(UTC),
                        access_method=access_method,
                        priority=source_config.editorial_priority,
                        status=status,
                    )
                )

        deduped = self._dedupe_candidates(candidates)
        debug = {
            'generated_at': datetime.now(UTC).isoformat(),
            'mode': 'live',
            'candidate_count_before_dedupe': len(candidates),
            'candidate_count_after_dedupe': len(deduped),
            'source_results': source_results,
            'resolved_user_county': local_resolution.region_used,
            'local_source_registry_used': local_resolution.local_source_registry_used,
            'local_sources_selected': [config.source_name for config in local_resolution.resolved_sources],
            'fallback_sources_selected': [config.source_name for config in fallback_sources],
            'registry_audit': audit,
        }
        return deduped, debug

    def fetch_articles(
        self,
        personalization: UserPersonalization | None = None,
        items_per_source: int = DEFAULT_ITEMS_PER_SOURCE,
        max_full_fetch: int = DEFAULT_MAX_FULL_FETCH,
        max_rss_fallback: int = DEFAULT_MAX_RSS_FALLBACK,
    ) -> tuple[list[FetchedArticle], dict[str, Any]]:
        candidates, debug = self.fetch_story_candidates(personalization=personalization, items_per_source=items_per_source)
        ranked_candidates = sorted(
            candidates,
            key=lambda item: (item.published_at, -item.priority),
            reverse=True,
        )

        articles: list[FetchedArticle] = []
        full_fetch_count = 0
        rss_fallback_count = 0
        failures: list[dict[str, str]] = []
        for candidate in ranked_candidates:
            if len(articles) >= max_full_fetch + max_rss_fallback:
                break
            fetch_result = self.article_fetch_and_clean_service.fetch_candidate_article(candidate)
            if fetch_result.status == 'success' and fetch_result.article is not None and full_fetch_count < max_full_fetch:
                article = fetch_result.article.model_copy(
                    update={
                        'editorial_priority': candidate.priority,
                        'source_scope': candidate.source_scope,
                        'source_region': candidate.county if candidate.source_scope == 'local' else candidate.region,
                        'is_local_source': candidate.source_scope == 'local',
                        'source_selection_reason': f"live_ingestion:{candidate.access_method}",
                    }
                )
                articles.append(article)
                full_fetch_count += 1
                continue

            if candidate.summary.strip() and rss_fallback_count < max_rss_fallback:
                articles.append(
                    FetchedArticle(
                        url=candidate.original_url,
                        title=candidate.title,
                        author=candidate.author,
                        published_at=candidate.published_at,
                        source=candidate.source_name,
                        content_text=candidate.summary,
                        ingestion_kind='rss_fallback',
                        editorial_priority=candidate.priority,
                        source_scope=candidate.source_scope,
                        source_region=candidate.county if candidate.source_scope == 'local' else candidate.region,
                        is_local_source=candidate.source_scope == 'local',
                        source_selection_reason=f"live_ingestion_fallback:{candidate.access_method}",
                    )
                )
                rss_fallback_count += 1
                continue

            failures.append({'source_name': candidate.source_name, 'url': candidate.original_url, 'status': fetch_result.status})

        tagged_articles, geo_debug = self.geo_tagging_service.tag_articles(articles)
        debug.update(
            {
                'article_count': len(tagged_articles),
                'full_fetch_count': full_fetch_count,
                'rss_fallback_count': rss_fallback_count,
                'failed_candidates': failures,
                'candidates_used': [candidate.model_dump(mode='json') for candidate in ranked_candidates[: max_full_fetch + max_rss_fallback]],
                'geo_tagging_summary': geo_debug,
            }
        )
        return tagged_articles, debug

    def write_registry_audit(self, output_path: Path, personalization: UserPersonalization | None = None) -> dict[str, Any]:
        monitored_sources, _resolution = self.source_watcher_service.resolve_monitored_source_configs(personalization)
        active_source_ids = {config.source_id for config in monitored_sources}
        fallback_sources = self.source_registry_service.build_live_fallback_source_configs(exclude_source_ids=active_source_ids)
        monitored_sources = list(monitored_sources) + fallback_sources
        active_source_ids = {config.source_id for config in monitored_sources}
        active_source_keys = {self._source_live_key(config.region, config.source_name) for config in monitored_sources}
        audit = self.source_registry_service.build_registry_audit(
            active_source_ids=active_source_ids,
            active_source_keys=active_source_keys,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        return audit

    def _recent_items_with_cache(self, source_config, limit: int):
        cache = self._read_feed_cache()
        record = cache.get(source_config.source_id)
        if record:
            cached_at = datetime.fromisoformat(record['cached_at'])
            if (datetime.now(UTC) - cached_at).total_seconds() <= FEED_CACHE_TTL_SECONDS and record.get('limit') == limit:
                return [self._cached_item_to_latest(item) for item in record.get('items', [])]

        recent_items = self.source_watcher_service.get_recent_content_items(source_config, limit=limit)
        cache[source_config.source_id] = {
            'cached_at': datetime.now(UTC).isoformat(),
            'limit': limit,
            'items': [item.model_dump(mode='json') for item in recent_items],
        }
        FEED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FEED_CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        return recent_items

    def _dedupe_candidates(self, candidates: list[LiveStoryCandidate]) -> list[LiveStoryCandidate]:
        exact_by_url: dict[str, LiveStoryCandidate] = {}
        for candidate in sorted(candidates, key=lambda item: (item.published_at, -item.priority), reverse=True):
            existing = exact_by_url.get(candidate.original_url)
            if existing is None or self._prefer_candidate(candidate, existing):
                exact_by_url[candidate.original_url] = candidate

        deduped: list[LiveStoryCandidate] = []
        for candidate in sorted(exact_by_url.values(), key=lambda item: (item.published_at, -item.priority), reverse=True):
            duplicate_index = next((index for index, existing in enumerate(deduped) if self._title_similarity(candidate.title, existing.title) > FUZZY_DEDUPE_THRESHOLD), None)
            if duplicate_index is None:
                deduped.append(candidate)
                continue
            if self._prefer_candidate(candidate, deduped[duplicate_index]):
                deduped[duplicate_index] = candidate
        return deduped

    def _prefer_candidate(self, candidate: LiveStoryCandidate, existing: LiveStoryCandidate) -> bool:
        if candidate.published_at != existing.published_at:
            return candidate.published_at > existing.published_at
        return candidate.priority < existing.priority

    def _title_similarity(self, left: str, right: str) -> float:
        return SequenceMatcher(None, self._normalize_title(left), self._normalize_title(right)).ratio()

    def _normalize_title(self, value: str) -> str:
        return ' '.join(value.lower().strip().split())

    def _access_method_for_config(self, source_config) -> str:
        if source_config.rss_url:
            return 'atom' if 'atom' in source_config.rss_url.lower() else 'rss'
        if source_config.source_url:
            return 'listing_page'
        return 'unknown'

    def _read_feed_cache(self) -> dict[str, Any]:
        if not FEED_CACHE_PATH.exists():
            return {}
        try:
            return json.loads(FEED_CACHE_PATH.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return {}

    def _source_live_key(self, region: str | None, source_name: str) -> str:
        normalized_region = self._slugify(region or '')
        normalized_source = self._slugify(source_name)
        return f"{normalized_region}:{normalized_source}" if normalized_region else normalized_source

    def _slugify(self, value: str) -> str:
        return '-'.join(value.lower().strip().split()).replace('.', '-')

    def _cached_item_to_latest(self, payload: dict[str, Any]):
        from app.models.source_watcher import LatestContentItem

        return LatestContentItem(**payload)
