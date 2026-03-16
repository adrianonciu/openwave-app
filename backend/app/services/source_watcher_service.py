from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError

from app.models.local_source_registry import LocalSourceEntry
from app.models.source_watcher import (
    DetectedContentItem,
    LatestContentItem,
    LocalSourceResolutionResult,
    SourceCheckResult,
    SourceCheckSummary,
    SourceConfig,
    SourceWatcherState,
)
from app.services.local_source_registry_service import LocalSourceRegistryService
from app.services.romanian_geo_resolver import resolve_listener_geography
from app.models.user_personalization import UserPersonalization

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
REQUEST_TIMEOUT_SECONDS = 15
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "source_watchers.json"
STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "source_watcher_state.json"
RFC3339_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
CHARSET_PATTERN = re.compile(r"charset=['\"]?([A-Za-z0-9._-]+)", re.IGNORECASE)
MAX_LOCAL_SOURCES_PER_REGION = 3
MALFORMED_RSS_NAMESPACE_TAG_PATTERN = re.compile(r"</?media:[^>]+>")


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.canonical_url: str | None = None
        self.json_ld_blocks: list[str] = []
        self._capture_title = False
        self._capture_script = False
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            key = attributes.get("property") or attributes.get("name")
            content = attributes.get("content", "").strip()
            if key and content:
                self.meta[key.lower()] = content
        elif tag == "link" and attributes.get("rel", "").lower() == "canonical":
            href = attributes.get("href", "").strip()
            if href:
                self.canonical_url = href
        elif tag == "title":
            self._capture_title = True
        elif tag == "script" and "ld+json" in attributes.get("type", "").lower():
            self._capture_script = True
            self._script_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._capture_title = False
        elif tag == "script" and self._capture_script:
            script_content = "".join(self._script_parts).strip()
            if script_content:
                self.json_ld_blocks.append(script_content)
            self._capture_script = False
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self.title += data
        if self._capture_script:
            self._script_parts.append(data)


class _ListingParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.container_stack: list[dict[str, Any]] = []
        self.candidates: list[dict[str, str]] = []
        self._capture_anchor_depth: int | None = None
        self._capture_anchor_parts: list[str] = []
        self._capture_time_depth: int | None = None
        self._capture_time_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}

        if tag in {"article", "li"}:
            self.container_stack.append({"href": "", "title": "", "published_at": ""})

        if tag == "a" and self.container_stack:
            href = attributes.get("href", "").strip()
            if href and not self.container_stack[-1]["href"]:
                self.container_stack[-1]["href"] = urljoin(self.base_url, href)
                self._capture_anchor_depth = len(self.container_stack)
                self._capture_anchor_parts = []

        if tag == "time" and self.container_stack:
            datetime_value = attributes.get("datetime", "").strip()
            if datetime_value and not self.container_stack[-1]["published_at"]:
                self.container_stack[-1]["published_at"] = datetime_value
            self._capture_time_depth = len(self.container_stack)
            self._capture_time_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_anchor_depth is not None and self.container_stack:
            if len(self.container_stack) == self._capture_anchor_depth:
                title = " ".join("".join(self._capture_anchor_parts).split())
                if title and not self.container_stack[-1]["title"]:
                    self.container_stack[-1]["title"] = title
                self._capture_anchor_depth = None
                self._capture_anchor_parts = []

        if tag == "time" and self._capture_time_depth is not None and self.container_stack:
            if len(self.container_stack) == self._capture_time_depth:
                if not self.container_stack[-1]["published_at"]:
                    published_text = " ".join("".join(self._capture_time_parts).split())
                    self.container_stack[-1]["published_at"] = published_text
                self._capture_time_depth = None
                self._capture_time_parts = []

        if tag in {"article", "li"} and self.container_stack:
            candidate = self.container_stack.pop()
            if candidate["href"] and candidate["title"]:
                self.candidates.append(candidate)

    def handle_data(self, data: str) -> None:
        if self._capture_anchor_depth is not None and self.container_stack:
            self._capture_anchor_parts.append(data)
        if self._capture_time_depth is not None and self.container_stack:
            self._capture_time_parts.append(data)


class _LooseAnchorParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.candidates: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attributes = {key.lower(): value or "" for key, value in attrs}
        href = attributes.get("href", "").strip()
        if href:
            self._current_href = urljoin(self.base_url, href)
            self._current_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._current_href:
            return
        title = " ".join("".join(self._current_parts).split())
        if title:
            self.candidates.append({"href": self._current_href, "title": title})
        self._current_href = None
        self._current_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_parts.append(data)


class SourceWatcherService:
    def __init__(self) -> None:
        self.local_source_registry_service = LocalSourceRegistryService()

    def load_source_configs(self) -> list[SourceConfig]:
        raw_data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return [
            SourceConfig(**item)
            for item in raw_data.get("sources", [])
            if item.get("enabled", True)
        ]

    def load_source_configs_with_local_sources(
        self,
        personalization: UserPersonalization | None = None,
    ) -> list[SourceConfig]:
        source_configs = list(self.load_source_configs())
        resolution = self.resolve_local_sources_for_personalization(personalization)
        if resolution.local_sources_enabled:
            source_configs.extend(resolution.resolved_sources)
        return source_configs

    def resolve_monitored_source_configs(
        self,
        personalization: UserPersonalization | None = None,
    ) -> tuple[list[SourceConfig], LocalSourceResolutionResult]:
        resolution = self.resolve_local_sources_for_personalization(personalization)
        source_configs = list(self.load_source_configs())
        if resolution.local_sources_enabled:
            source_configs.extend(resolution.resolved_sources)
        return source_configs, resolution

    def resolve_local_sources_for_personalization(
        self,
        personalization: UserPersonalization | None,
    ) -> LocalSourceResolutionResult:
        if personalization is None:
            return LocalSourceResolutionResult(
                explanation="County local sources were not activated because no personalization payload was provided.",
            )
        if personalization.editorial_preferences.geography.local <= 0:
            return LocalSourceResolutionResult(
                explanation="County local sources were not activated because local preference is 0.",
            )
        resolved_geography = resolve_listener_geography(
            city=personalization.listener_profile.city,
            region=personalization.listener_profile.region,
        )
        region = resolved_geography.resolved_county
        if not region:
            return LocalSourceResolutionResult(
                explanation="County local sources were not activated because the listener city or region could not be resolved to a supported county.",
            )

        resolved_sources = self.get_local_source_configs_for_region(region)
        if not resolved_sources:
            return LocalSourceResolutionResult(
                region_used=region,
                resolved_sources=[],
                source_count=0,
                local_source_registry_used=False,
                local_sources_enabled=False,
                explanation=f"County local sources were not activated because the registry has no entries for region '{region}'.",
            )

        resolution_note = (
            f"resolved from city '{resolved_geography.input_city}' to county '{region}'"
            if resolved_geography.input_city and not (personalization.listener_profile.region or "").strip()
            else f"resolved directly for county '{region}'"
        )
        return LocalSourceResolutionResult(
            region_used=region,
            resolved_sources=resolved_sources,
            source_count=len(resolved_sources),
            local_source_registry_used=True,
            local_sources_enabled=True,
            explanation=f"County local sources were activated for {resolution_note} with {len(resolved_sources)} watcher-usable source config(s).",
        )

    def get_latest_content(self, source_config: SourceConfig) -> LatestContentItem:
        recent_items = self.get_recent_content_items(source_config, limit=1)
        if recent_items:
            return recent_items[0]
        raise ValueError(
            f"Unable to detect latest content for source '{source_config.source_id}': no parser returned a dated content item."
        )

    def get_recent_content_items(self, source_config: SourceConfig, limit: int = 3) -> list[LatestContentItem]:
        errors: list[str] = []

        if source_config.rss_url:
            try:
                recent_from_rss = self._get_recent_from_rss(source_config, limit=limit)
                if recent_from_rss:
                    return recent_from_rss
            except Exception as exc:
                errors.append(f"rss: {exc}")

        if source_config.parser_type in {"auto", "html_listing"}:
            try:
                latest_from_listing = self._get_latest_from_listing(source_config)
                if latest_from_listing is not None:
                    return [latest_from_listing]
            except Exception as exc:
                errors.append(f"listing: {exc}")

        if source_config.parser_type in {"auto", "meta_page"}:
            try:
                latest_from_page = self._get_latest_from_page(source_config)
                if latest_from_page is not None:
                    return [latest_from_page]
            except Exception as exc:
                errors.append(f"page: {exc}")

        detail = "; ".join(errors) if errors else "no parser returned a dated content item"
        raise ValueError(
            f"Unable to detect latest content for source '{source_config.source_id}': {detail}."
        )

    def check_source_for_new_content(self, source_config: SourceConfig) -> SourceCheckResult:
        states = self._load_states()
        existing_state = states.get(source_config.source_id) or SourceWatcherState(
            last_seen_url=source_config.last_seen_url,
            last_seen_title=source_config.last_seen_title,
            last_seen_published_at=source_config.last_seen_published_at,
        )
        now = datetime.now(UTC)

        if self._should_skip_check(existing_state, source_config, now):
            return SourceCheckResult(
                source_id=source_config.source_id,
                source_type=source_config.source_type,
                status="no_change",
                item=self._state_item_or_none(existing_state, source_config),
            )

        try:
            latest_item = self.get_latest_content(source_config)
        except Exception as exc:
            self._save_state(
                source_id=source_config.source_id,
                state=existing_state.model_copy(update={"last_checked_at": now}),
                states=states,
            )
            return SourceCheckResult(
                source_id=source_config.source_id,
                source_type=source_config.source_type,
                status="error",
                error_message=str(exc),
            )

        if self._is_bootstrap_run(existing_state):
            self._save_state(
                source_id=source_config.source_id,
                state=self._build_state(latest_item, now),
                states=states,
            )
            return SourceCheckResult(
                source_id=source_config.source_id,
                source_type=source_config.source_type,
                status="no_change",
                item=self._to_detected_item(latest_item),
            )

        is_new_content = self._is_new_content(latest_item, existing_state)
        state_item = latest_item if is_new_content else _state_to_item(existing_state, latest_item)
        self._save_state(
            source_id=source_config.source_id,
            state=self._build_state(state_item, now),
            states=states,
        )

        return SourceCheckResult(
            source_id=source_config.source_id,
            source_type=source_config.source_type,
            status="new_content_detected" if is_new_content else "no_change",
            item=self._to_detected_item(latest_item),
        )

    def check_all_sources(
        self,
        personalization: UserPersonalization | None = None,
    ) -> SourceCheckSummary:
        monitored_sources, _resolution = self.resolve_monitored_source_configs(personalization)
        results = [
            self.check_source_for_new_content(source_config)
            for source_config in monitored_sources
        ]
        return SourceCheckSummary(checked_at=datetime.now(UTC), results=results)

    def get_local_sources_for_region(self, region: str) -> list[LocalSourceEntry]:
        return self.local_source_registry_service.get_local_sources_for_region(region)

    def get_local_source_configs_for_region(self, region: str) -> list[SourceConfig]:
        source_entries = self.get_local_sources_for_region(region)[:MAX_LOCAL_SOURCES_PER_REGION]
        source_configs: list[SourceConfig] = []
        normalized_region = self._normalize_source_id_fragment(region) or "region"
        for entry in source_entries:
            source_configs.append(
                SourceConfig(
                    source_id=f"local-{normalized_region}-{self._normalize_source_id_fragment(entry.source_name)}",
                    source_name=entry.source_name,
                    source_type="local_county",
                    source_url=entry.source_url,
                    category=entry.category,
                    scope=entry.scope,
                    country=entry.country,
                    language=entry.language,
                    enabled=entry.enabled,
                    editorial_priority=entry.editorial_priority,
                    notes=entry.notes,
                    region=region,
                    priority_rank=entry.priority_rank,
                    rss_url=entry.rss_url,
                    parser_type=entry.parser_type,
                    check_interval_minutes=30,
                )
            )
        return sorted(source_configs, key=lambda item: item.priority_rank or 999)

    def _get_latest_from_rss(self, source_config: SourceConfig) -> LatestContentItem | None:
        recent_items = self._get_recent_from_rss(source_config, limit=1)
        return recent_items[0] if recent_items else None

    def _get_recent_from_rss(self, source_config: SourceConfig, limit: int = 3) -> list[LatestContentItem]:
        if not source_config.rss_url:
            return []

        root = self._parse_rss_root(source_config.rss_url)
        candidates: list[LatestContentItem] = []
        pending_page_resolution: list[tuple[str, str]] = []

        for item in root.findall("./channel/item"):
            candidate = self._build_item_from_xml_entry(
                source_config=source_config,
                entry=item,
                title_paths=("title",),
                link_paths=("link",),
                published_paths=(
                    "pubDate",
                    "published",
                    "updated",
                    "{http://purl.org/dc/elements/1.1/}date",
                ),
            )
            if candidate is not None:
                candidates.append(candidate)
                continue
            title = self._first_text(item, "title")
            url = self._first_text(item, "link")
            if title and url:
                pending_page_resolution.append((title.strip(), url.strip()))

        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            candidate = self._build_item_from_xml_entry(
                source_config=source_config,
                entry=entry,
                title_paths=("{http://www.w3.org/2005/Atom}title",),
                link_paths=("{http://www.w3.org/2005/Atom}link",),
                published_paths=(
                    "{http://www.w3.org/2005/Atom}published",
                    "{http://www.w3.org/2005/Atom}updated",
                ),
                atom_link=True,
            )
            if candidate is not None:
                candidates.append(candidate)

        if not candidates:
            for title, url in pending_page_resolution[: max(5, limit * 2)]:
                candidate = self._get_latest_from_article_page(
                    source_config=source_config,
                    article_url=url,
                    fallback_title=title,
                )
                if candidate is not None:
                    candidates.append(candidate)

        deduped: list[LatestContentItem] = []
        seen_urls: set[str] = set()
        for candidate in sorted(candidates, key=lambda item: item.published_at, reverse=True):
            if candidate.url in seen_urls:
                continue
            seen_urls.add(candidate.url)
            deduped.append(candidate)
            if len(deduped) >= max(1, limit):
                break

        return deduped

    def _parse_rss_root(self, rss_url: str) -> ET.Element:
        raw_feed = self._fetch_bytes(rss_url).lstrip()
        try:
            return ET.fromstring(raw_feed)
        except ParseError as exc:
            if 'unbound prefix' not in str(exc):
                raise
            sanitized_feed = MALFORMED_RSS_NAMESPACE_TAG_PATTERN.sub('', raw_feed.decode('utf-8', errors='replace'))
            return ET.fromstring(sanitized_feed.encode('utf-8'))

    def _get_latest_from_listing(self, source_config: SourceConfig) -> LatestContentItem | None:
        html = self._fetch_text(source_config.source_url)
        json_ld_candidates = self._extract_json_ld_candidates(html, source_config)
        if json_ld_candidates:
            return max(json_ld_candidates, key=lambda item: item.published_at)

        parser = _ListingParser(source_config.source_url)
        parser.feed(html)

        candidates: list[LatestContentItem] = []
        undated_candidates: list[dict[str, str]] = []
        for candidate in parser.candidates:
            published_at = self._parse_datetime(candidate["published_at"])
            if published_at is None:
                undated_candidates.append(candidate)
                continue
            candidates.append(
                LatestContentItem(
                    url=candidate["href"],
                    title=candidate["title"],
                    published_at=published_at,
                    source_name=source_config.source_name,
                    source_type=source_config.source_type,
                )
            )

        if not candidates:
            for candidate in undated_candidates[:5]:
                resolved_candidate = self._get_latest_from_article_page(
                    source_config=source_config,
                    article_url=candidate["href"],
                    fallback_title=candidate["title"],
                )
                if resolved_candidate is not None:
                    candidates.append(resolved_candidate)

        if not candidates and source_config.source_name in {"Mediafax", "Ziarul Financiar"}:
            seen_urls = {candidate["href"] for candidate in parser.candidates}
            loose_parser = _LooseAnchorParser(source_config.source_url)
            loose_parser.feed(html)
            for candidate in loose_parser.candidates:
                href = candidate.get("href", "").strip()
                title = candidate.get("title", "").strip()
                if not href or not title or href in seen_urls:
                    continue
                if source_config.source_url.rstrip("/") not in href:
                    continue
                if len(title) < 24:
                    continue
                if any(marker in href.lower() for marker in ("/tag/", "/categorie/", "/category/", "/video", "/foto", "/opinii", "/opinie")):
                    continue
                resolved_candidate = self._get_latest_from_article_page(
                    source_config=source_config,
                    article_url=href,
                    fallback_title=title,
                )
                if resolved_candidate is not None:
                    candidates.append(resolved_candidate)
                if len(candidates) >= 5:
                    break

        if not candidates:
            return None

        return max(candidates, key=lambda item: item.published_at)

    def _get_latest_from_page(self, source_config: SourceConfig) -> LatestContentItem | None:
        return self._get_latest_from_article_page(
            source_config=source_config,
            article_url=source_config.source_url,
            fallback_title=None,
        )

    def _get_latest_from_article_page(
        self,
        source_config: SourceConfig,
        article_url: str,
        fallback_title: str | None,
    ) -> LatestContentItem | None:
        html = self._fetch_text(article_url)
        json_ld_candidates = self._extract_json_ld_candidates(
            html,
            source_config,
            base_url=article_url,
        )
        if json_ld_candidates:
            return max(json_ld_candidates, key=lambda item: item.published_at)

        parser = _PageParser()
        parser.feed(html)

        published_at = self._parse_datetime(
            parser.meta.get("article:published_time")
            or parser.meta.get("og:published_time")
            or parser.meta.get("parsely-pub-date")
            or parser.meta.get("pubdate")
            or parser.meta.get("date")
        )
        title = (
            parser.meta.get("og:title")
            or parser.meta.get("twitter:title")
            or parser.title.strip()
            or fallback_title
        )
        canonical_url = parser.canonical_url or article_url

        if not published_at or not title or not canonical_url:
            return None

        return LatestContentItem(
            url=urljoin(article_url, canonical_url),
            title=title,
            published_at=published_at,
            source_name=source_config.source_name,
            source_type=source_config.source_type,
        )

    def _build_item_from_xml_entry(
        self,
        source_config: SourceConfig,
        entry: ET.Element,
        title_paths: tuple[str, ...],
        link_paths: tuple[str, ...],
        published_paths: tuple[str, ...],
        atom_link: bool = False,
    ) -> LatestContentItem | None:
        title = self._first_text(entry, *title_paths)
        published_at = self._parse_datetime(self._first_text(entry, *published_paths))
        if atom_link:
            url = ""
            for link_path in link_paths:
                link_element = entry.find(link_path)
                href = link_element.attrib.get("href", "").strip() if link_element is not None else ""
                if href:
                    url = href
                    break
        else:
            url = self._first_text(entry, *link_paths)

        if not title or not url or published_at is None:
            return None

        return LatestContentItem(
            url=url.strip(),
            title=title.strip(),
            published_at=published_at,
            source_name=source_config.source_name,
            source_type=source_config.source_type,
        )

    def _extract_json_ld_candidates(
        self,
        html: str,
        source_config: SourceConfig,
        base_url: str | None = None,
    ) -> list[LatestContentItem]:
        parser = _PageParser()
        parser.feed(html)

        candidates: list[LatestContentItem] = []
        for block in parser.json_ld_blocks:
            try:
                payload = json.loads(block)
            except json.JSONDecodeError:
                continue

            for item in self._flatten_json_ld(payload):
                candidate = self._json_ld_to_item(item, source_config, base_url=base_url)
                if candidate is not None:
                    candidates.append(candidate)

        return candidates

    def _json_ld_to_item(
        self,
        item: dict[str, Any],
        source_config: SourceConfig,
        base_url: str | None = None,
    ) -> LatestContentItem | None:
        item_type = item.get("@type")
        if isinstance(item_type, list):
            item_types = {value.lower() for value in item_type if isinstance(value, str)}
        elif isinstance(item_type, str):
            item_types = {item_type.lower()}
        else:
            item_types = set()

        if not item_types.intersection({"article", "newsarticle", "blogposting"}):
            return None

        published_at = self._parse_datetime(
            str(item.get("datePublished") or item.get("dateCreated") or "")
        )
        title = str(item.get("headline") or item.get("name") or "").strip()
        url = self._extract_json_ld_url(item, base_url or source_config.source_url)

        if not published_at or not title or not url:
            return None

        return LatestContentItem(
            url=url,
            title=title,
            published_at=published_at,
            source_name=source_config.source_name,
            source_type=source_config.source_type,
        )

    def _extract_json_ld_url(self, item: dict[str, Any], base_url: str) -> str:
        for key in ("url", "mainEntityOfPage"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return urljoin(base_url, value.strip())
            if isinstance(value, dict):
                nested_url = value.get("@id") or value.get("url")
                if isinstance(nested_url, str) and nested_url.strip():
                    return urljoin(base_url, nested_url.strip())
        return ""

    def _flatten_json_ld(self, payload: Any) -> list[dict[str, Any]]:
        flattened: list[dict[str, Any]] = []

        if isinstance(payload, list):
            for item in payload:
                flattened.extend(self._flatten_json_ld(item))
            return flattened

        if not isinstance(payload, dict):
            return flattened

        flattened.append(payload)

        for key in ("@graph", "itemListElement"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and "item" in item:
                        flattened.extend(self._flatten_json_ld(item["item"]))
                    else:
                        flattened.extend(self._flatten_json_ld(item))

        return flattened

    def _is_bootstrap_run(self, state: SourceWatcherState) -> bool:
        return (
            state.last_seen_url is None
            and state.last_seen_title is None
            and state.last_seen_published_at is None
        )

    def _should_skip_check(
        self,
        state: SourceWatcherState,
        source_config: SourceConfig,
        now: datetime,
    ) -> bool:
        if state.last_checked_at is None:
            return False

        next_allowed_check = state.last_checked_at + timedelta(
            minutes=source_config.check_interval_minutes
        )
        return now < next_allowed_check

    def _state_item_or_none(
        self,
        state: SourceWatcherState,
        source_config: SourceConfig,
    ) -> DetectedContentItem | None:
        if (
            state.last_seen_url is None
            or state.last_seen_title is None
            or state.last_seen_published_at is None
        ):
            return None

        return DetectedContentItem(
            url=state.last_seen_url,
            title=state.last_seen_title,
            published_at=state.last_seen_published_at,
            source_name=source_config.source_name,
        )

    def _to_detected_item(self, item: LatestContentItem) -> DetectedContentItem:
        return DetectedContentItem(
            url=item.url,
            title=item.title,
            published_at=item.published_at,
            source_name=item.source_name,
        )

    def _is_new_content(
        self,
        current: LatestContentItem,
        existing_state: SourceWatcherState,
    ) -> bool:
        if existing_state.last_seen_url and current.url != existing_state.last_seen_url:
            return True

        if (
            existing_state.last_seen_title
            and current.title != existing_state.last_seen_title
            and (
                existing_state.last_seen_published_at is None
                or current.published_at >= existing_state.last_seen_published_at
            )
        ):
            return True

        if (
            existing_state.last_seen_published_at is not None
            and current.published_at > existing_state.last_seen_published_at
        ):
            return True

        return False

    def _build_state(self, item: LatestContentItem, checked_at: datetime) -> SourceWatcherState:
        return SourceWatcherState(
            last_seen_url=item.url,
            last_seen_title=item.title,
            last_seen_published_at=item.published_at,
            last_checked_at=checked_at,
        )

    def _load_states(self) -> dict[str, SourceWatcherState]:
        if not STATE_PATH.exists():
            return {}

        raw_data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return {
            source_id: SourceWatcherState(**state)
            for source_id, state in raw_data.get("sources", {}).items()
        }

    def _save_state(
        self,
        source_id: str,
        state: SourceWatcherState,
        states: dict[str, SourceWatcherState],
    ) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        updated_states = dict(states)
        updated_states[source_id] = state

        payload = {
            "sources": {
                current_source_id: current_state.model_dump(mode="json")
                for current_source_id, current_state in updated_states.items()
            }
        }
        STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _fetch_bytes(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read()

    def _fetch_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw_body = response.read()
            charset = response.headers.get_content_charset()
            return self._decode_html_bytes(raw_body, charset)

    def _decode_html_bytes(self, raw_body: bytes, header_charset: str | None) -> str:
        attempted: list[str] = []
        candidate_charsets: list[str] = []
        if header_charset:
            candidate_charsets.append(header_charset)

        meta_snippet = raw_body[:2048].decode("ascii", errors="ignore")
        meta_match = CHARSET_PATTERN.search(meta_snippet)
        if meta_match:
            candidate_charsets.append(meta_match.group(1))

        candidate_charsets.extend(["utf-8", "windows-1250", "iso-8859-2", "cp1252", "latin-1"])
        for charset in candidate_charsets:
            normalized = charset.strip().lower()
            if not normalized or normalized in attempted:
                continue
            attempted.append(normalized)
            try:
                return raw_body.decode(normalized)
            except (LookupError, UnicodeDecodeError):
                continue

        return raw_body.decode("utf-8", errors="replace")

    def _first_text(self, parent: ET.Element, *paths: str) -> str:
        for path in paths:
            element = parent.find(path)
            if element is not None and element.text:
                return element.text.strip()
        return ""

    def _normalize_source_id_fragment(self, value: str) -> str:
        lowered = value.strip().lower()
        lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
        return lowered.strip("-")

    def _parse_datetime(self, raw_value: str | None) -> datetime | None:
        if raw_value is None:
            return None
        value = raw_value.strip()
        if not value:
            return None

        for candidate in (value, value.replace("Z", "+00:00")):
            try:
                parsed = datetime.fromisoformat(candidate)
                return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                continue

        try:
            parsed_rfc = parsedate_to_datetime(value)
            return parsed_rfc.astimezone(UTC) if parsed_rfc.tzinfo else parsed_rfc.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            pass

        match = RFC3339_DATE_PATTERN.search(value)
        if match:
            try:
                return datetime.fromisoformat(match.group(0)).replace(tzinfo=UTC)
            except ValueError:
                return None

        return None


def _state_to_item(
    state: SourceWatcherState,
    fallback_item: LatestContentItem,
) -> LatestContentItem:
    return LatestContentItem(
        url=state.last_seen_url or fallback_item.url,
        title=state.last_seen_title or fallback_item.title,
        published_at=state.last_seen_published_at or fallback_item.published_at,
        source_name=fallback_item.source_name,
        source_type=fallback_item.source_type,
    )
