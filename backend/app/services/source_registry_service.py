from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

from app.models.live_source_ingestion import SourceRegistryEntry
from app.models.local_source_registry import LocalSourceEntry
from app.models.source_watcher import SourceConfig
from app.services.local_source_registry_service import LocalSourceRegistryService
from app.services.romanian_geo_resolver import resolve_listener_geography
from app.services.source_watcher_service import SourceWatcherService

REGISTRY_PATH = Path(__file__).resolve().parents[1] / 'config' / 'source_registry.json'
_SOURCE_WATCHERS_PATH = Path(__file__).resolve().parents[1] / 'config' / 'source_watchers.json'
_LOCAL_REGISTRY_PATH = Path(__file__).resolve().parents[1] / 'config' / 'romanian_local_sources_by_county.json'
_PAYWALL_HINT_PATTERN = re.compile(r'paywall|paywalled|metered|403|404|inactive|fallback', re.IGNORECASE)
_ACCESS_BLOCKER_HINT_PATTERN = re.compile(r'paywall|paywalled|metered|403|404', re.IGNORECASE)
_FALLBACK_EXCLUDED_CATEGORIES = {'sport', 'entertainment', 'lifestyle', 'tv'}


class SourceRegistryService:
    def __init__(self) -> None:
        self.source_watcher_service = SourceWatcherService()
        self.local_source_registry_service = LocalSourceRegistryService()

    def load_registry(self) -> list[SourceRegistryEntry]:
        if not REGISTRY_PATH.exists():
            self.write_registry_file()
        payload = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        return [SourceRegistryEntry(**item) for item in payload.get('sources', [])]

    def write_registry_file(self) -> list[SourceRegistryEntry]:
        entries = self.build_registry_entries()
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'generated_at': datetime.now(UTC).isoformat(),
            'sources': [entry.model_dump(mode='json') for entry in entries],
            'source_files': {
                'source_watchers': str(_SOURCE_WATCHERS_PATH),
                'county_local_registry': str(_LOCAL_REGISTRY_PATH),
            },
        }
        REGISTRY_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        return entries

    def build_registry_entries(self) -> list[SourceRegistryEntry]:
        entries: list[SourceRegistryEntry] = []
        entries.extend(self._watcher_entries())
        entries.extend(self._county_entries())
        return sorted(entries, key=lambda item: (item.scope, item.county or '', item.priority, item.source_name.lower()))

    def build_live_fallback_source_configs(
        self,
        exclude_source_ids: set[str] | None = None,
        limit: int = 20,
    ) -> list[SourceConfig]:
        excluded_ids = exclude_source_ids or set()
        raw_watchers = json.loads(_SOURCE_WATCHERS_PATH.read_text(encoding='utf-8'))
        fallback_configs: list[SourceConfig] = []
        for item in raw_watchers.get('sources', []):
            config = SourceConfig(**item)
            if config.source_id in excluded_ids:
                continue
            if config.enabled:
                continue
            if (config.scope or '') not in {'national', 'international'}:
                continue
            if (config.category or '').lower() in _FALLBACK_EXCLUDED_CATEGORIES:
                continue
            if not config.rss_url and not config.source_url:
                continue
            if config.notes and _ACCESS_BLOCKER_HINT_PATTERN.search(config.notes):
                continue
            fallback_configs.append(config)
        fallback_configs.sort(key=lambda item: (item.editorial_priority, item.priority_rank or 999, item.source_name.lower()))
        return fallback_configs[:limit]

    def build_registry_audit(self, active_source_ids: set[str] | None = None, active_source_keys: set[str] | None = None) -> dict[str, Any]:
        active_ids = active_source_ids or set()
        active_keys = active_source_keys or set()
        entries = self.load_registry()
        return {
            'generated_at': datetime.now(UTC).isoformat(),
            'source_count': len(entries),
            'sources': [
                {
                    'source_id': entry.source_id,
                    'source_name': entry.source_name,
                    'scope': entry.scope,
                    'county': entry.county,
                    'region': entry.region,
                    'language': entry.language,
                    'priority': entry.priority,
                    'access_method': entry.access_method,
                    'feed_url': entry.feed_url,
                    'listing_url': entry.listing_url,
                    'status': entry.status,
                    'active_in_live_mode': (entry.source_id in active_ids or self._entry_live_key(entry) in active_keys) if (active_ids or active_keys) else entry.active_in_live_mode,
                }
                for entry in entries
            ],
        }

    def _watcher_entries(self) -> list[SourceRegistryEntry]:
        entries: list[SourceRegistryEntry] = []
        raw_watchers = json.loads(_SOURCE_WATCHERS_PATH.read_text(encoding='utf-8'))
        for item in raw_watchers.get('sources', []):
            entries.append(self._entry_from_source_config(SourceConfig(**item)))
        return entries

    def _county_entries(self) -> list[SourceRegistryEntry]:
        entries: list[SourceRegistryEntry] = []
        for county_group in self.local_source_registry_service.load_registry():
            county_name = county_group.county_name
            resolved_geo = resolve_listener_geography(city=None, region=county_name)
            for entry in county_group.source_entries:
                entries.append(self._entry_from_local_source(county_name, resolved_geo.resolved_macro_region, entry))
        return entries

    def _entry_from_source_config(self, config: SourceConfig) -> SourceRegistryEntry:
        scope = 'county' if config.source_type == 'local_county' else (config.scope or 'national')
        access_method = self._detect_access_method(config.rss_url, config.parser_type, config.source_url)
        status = self._detect_status(config.enabled, config.notes, access_method, config.source_url)
        county = config.region if scope == 'county' else None
        region = None
        if county:
            region = resolve_listener_geography(city=None, region=county).resolved_macro_region
        return SourceRegistryEntry(
            source_id=config.source_id,
            source_name=config.source_name,
            scope=scope if scope in {'county', 'regional', 'national', 'international'} else 'national',
            county=county,
            region=region,
            language=config.language,
            priority=config.editorial_priority,
            access_method=access_method,
            feed_url=config.rss_url,
            listing_url=config.source_url,
            status=status,
            active_in_live_mode=bool(config.enabled and status != 'unavailable'),
            parser_type=config.parser_type,
            notes=config.notes,
        )

    def _entry_from_local_source(self, county_name: str, macro_region: str | None, entry: LocalSourceEntry) -> SourceRegistryEntry:
        access_method = self._detect_access_method(entry.rss_url, entry.parser_type, entry.source_url)
        status = self._detect_status(entry.enabled, entry.notes, access_method, entry.source_url)
        return SourceRegistryEntry(
            source_id=f"county-{self._slugify(county_name)}-{self._slugify(entry.source_name)}",
            source_name=entry.source_name,
            scope='county',
            county=county_name,
            region=macro_region,
            language=entry.language,
            priority=entry.editorial_priority,
            access_method=access_method,
            feed_url=entry.rss_url,
            listing_url=entry.source_url,
            status=status,
            active_in_live_mode=bool(entry.enabled and status != 'unavailable'),
            parser_type=entry.parser_type,
            notes=entry.notes,
        )

    def _detect_access_method(self, feed_url: str | None, parser_type: str | None, listing_url: str | None) -> str:
        if feed_url:
            lowered = feed_url.lower()
            if 'atom' in lowered:
                return 'atom'
            return 'rss'
        if listing_url and (parser_type in {'auto', 'html_listing', 'meta_page', 'rss', None}):
            return 'listing_page'
        return 'unknown'

    def _detect_status(self, enabled: bool, notes: str | None, access_method: str, listing_url: str | None) -> str:
        if access_method == 'unknown' and not listing_url:
            return 'unavailable'
        if not enabled:
            return 'fallback_only'
        if notes and _PAYWALL_HINT_PATTERN.search(notes):
            return 'fallback_only'
        return 'usable'

    def _entry_live_key(self, entry: SourceRegistryEntry) -> str:
        county = self._slugify(entry.county or "")
        return f"{county}:{self._slugify(entry.source_name)}" if county else self._slugify(entry.source_name)

    def _slugify(self, value: str) -> str:
        lowered = value.strip().lower()
        lowered = re.sub(r'[^a-z0-9]+', '-', lowered)
        return lowered.strip('-')
