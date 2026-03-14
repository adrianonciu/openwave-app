from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import json
import re
import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.models.article_fetch import ArticleFetchResult, FetchArticleInput, FetchedArticle
from app.models.source_watcher import DetectedContentItem, LatestContentItem

USER_AGENT = "OpenWaveArticleFetcher/1.0"
REQUEST_TIMEOUT_SECONDS = 20
HTML_CACHE_TTL_SECONDS = 900
MIN_CONTENT_LENGTH = 500
JSON_LD_ARTICLE_TYPES = {"article", "newsarticle", "blogposting", "report"}
INLINE_BREAK_TAGS = {"br"}
CONTENT_BLOCK_TAGS = {"p", "div", "section", "li", "blockquote"}
ARTICLE_TEXT_TAGS = {"p", "h2", "h3", "li", "blockquote"}
IGNORE_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "path",
    "button",
    "form",
    "nav",
    "footer",
    "aside",
    "header",
}
JUNK_HINTS = {
    "nav",
    "footer",
    "header",
    "menu",
    "share",
    "social",
    "related",
    "recommend",
    "promo",
    "newsletter",
    "subscribe",
    "signin",
    "login",
    "comment",
    "advert",
    "ad-",
    "outbrain",
    "taboola",
    "cookie",
    "breadcrumb",
    "author-bio",
}
MULTISPACE_PATTERN = re.compile(r"[ \t]+")
MULTINEWLINE_PATTERN = re.compile(r"\n{3,}")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
CHARSET_PATTERN = re.compile(r"charset=['\"]?([A-Za-z0-9._-]+)", re.IGNORECASE)
PARAGRAPH_PATTERN = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)


@dataclass
class _ArticleMetadata:
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    source: str | None = None
    article_body: str | None = None


@dataclass
class _FetchTarget:
    url: str
    title: str | None = None
    source: str | None = None
    published_at: datetime | None = None


class _ArticleHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.json_ld_blocks: list[str] = []
        self._capture_title = False
        self._capture_script = False
        self._script_parts: list[str] = []
        self._frames: list[dict[str, Any]] = []
        self._article_depth = 0
        self.article_blocks: list[str] = []
        self.heuristic_blocks: list[dict[str, Any]] = []
        self._block_index = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        attr_text = f"{attributes.get('id', '')} {attributes.get('class', '')}".lower()
        parent_ignored = any(frame["ignore"] for frame in self._frames)
        ignore = parent_ignored or tag in IGNORE_TAGS or self._looks_like_junk(attr_text)
        in_article = self._article_depth > 0 or (tag == "article" and not ignore)

        self._frames.append(
            {
                "tag": tag,
                "text_parts": [],
                "ignore": ignore,
                "in_article": in_article,
                "attr_text": attr_text,
            }
        )

        if tag == "meta":
            key = attributes.get("property") or attributes.get("name")
            content = attributes.get("content", "").strip()
            if key and content:
                self.meta[key.lower()] = content

        if tag == "title":
            self._capture_title = True

        if tag == "script" and "ld+json" in attributes.get("type", "").lower():
            self._capture_script = True
            self._script_parts = []

        if tag == "article" and not ignore:
            self._article_depth += 1

        if tag in INLINE_BREAK_TAGS:
            self.handle_data("\n")

    def handle_endtag(self, tag: str) -> None:
        if not self._frames:
            return

        frame = self._frames.pop()
        text = self._normalize_inline_text("".join(frame["text_parts"]))

        if tag == "title":
            self._capture_title = False
        elif tag == "script" and self._capture_script:
            script_content = "".join(self._script_parts).strip()
            if script_content:
                self.json_ld_blocks.append(script_content)
            self._capture_script = False
            self._script_parts = []

        if not frame["ignore"] and text:
            if frame["in_article"] and frame["tag"] in ARTICLE_TEXT_TAGS:
                self.article_blocks.append(text)
            if frame["tag"] in CONTENT_BLOCK_TAGS:
                self.heuristic_blocks.append(
                    {
                        "text": text,
                        "tag": frame["tag"],
                        "context": frame["attr_text"],
                        "in_article": frame["in_article"],
                        "index": self._block_index,
                    }
                )
                self._block_index += 1

        if tag == "article" and not frame["ignore"] and self._article_depth > 0:
            self._article_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self.title += data
        if self._capture_script:
            self._script_parts.append(data)

        if not self._frames:
            return

        cleaned = unescape(data)
        if not cleaned.strip():
            return

        for frame in self._frames:
            if not frame["ignore"]:
                frame["text_parts"].append(cleaned)

    @staticmethod
    def _normalize_inline_text(value: str) -> str:
        value = value.replace("\r", " ")
        value = MULTISPACE_PATTERN.sub(" ", value)
        return value.strip()

    @staticmethod
    def _looks_like_junk(attr_text: str) -> bool:
        return any(hint in attr_text for hint in JUNK_HINTS)


class ArticleFetchService:
    def __init__(self) -> None:
        self._html_cache: dict[str, tuple[float, str]] = {}

    def fetch_article(self, target: FetchArticleInput) -> ArticleFetchResult:
        normalized_target = self._normalize_target(target)

        try:
            html, cached = self._fetch_html(normalized_target.url)
        except TimeoutError as exc:
            return ArticleFetchResult(status="timeout", error_message=str(exc))
        except (HTTPError, URLError) as exc:
            return ArticleFetchResult(status="network_error", error_message=str(exc))
        except Exception as exc:
            return ArticleFetchResult(status="error", error_message=str(exc))

        try:
            parser = _ArticleHtmlParser()
            parser.feed(html)
            parser.close()
        except Exception as exc:
            return ArticleFetchResult(status="invalid_html", error_message=str(exc), cached=cached)

        json_ld_metadata = self._extract_json_ld_metadata(parser.json_ld_blocks)
        metadata = self._merge_metadata(normalized_target, parser, json_ld_metadata)
        extraction_method, content_text = self._extract_content_text(parser, json_ld_metadata, html)

        if len(content_text) < MIN_CONTENT_LENGTH:
            return ArticleFetchResult(
                status="content_extraction_failed",
                error_message=(
                    f"Extracted content too small ({len(content_text)} characters); "
                    "minimum is 500."
                ),
                cached=cached,
            )

        article = FetchedArticle(
            url=normalized_target.url,
            title=metadata.title or normalized_target.title or normalized_target.url,
            author=metadata.author,
            published_at=metadata.published_at or normalized_target.published_at,
            source=metadata.source or normalized_target.source or self._source_from_url(normalized_target.url),
            content_text=content_text,
            ingestion_kind="full_fetch",
        )
        return ArticleFetchResult(
            status="success",
            article=article,
            extraction_method=extraction_method,
            cached=cached,
        )

    def _normalize_target(self, target: FetchArticleInput) -> _FetchTarget:
        if isinstance(target, str):
            return _FetchTarget(url=target)

        if isinstance(target, LatestContentItem):
            return _FetchTarget(
                url=target.url,
                title=target.title,
                source=target.source_name,
                published_at=target.published_at,
            )

        if isinstance(target, DetectedContentItem):
            return _FetchTarget(
                url=target.url,
                title=target.title,
                source=target.source_name,
                published_at=target.published_at,
            )

        raise TypeError("Unsupported fetch target.")

    def _fetch_html(self, url: str) -> tuple[str, bool]:
        now = time.time()
        cached_entry = self._html_cache.get(url)
        if cached_entry is not None:
            cached_at, cached_html = cached_entry
            if now - cached_at < HTML_CACHE_TTL_SECONDS:
                return cached_html, True

        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw_body = response.read()
                charset = response.headers.get_content_charset()
                html = self._decode_html_bytes(raw_body, charset)
        except (TimeoutError, socket.timeout) as exc:
            raise TimeoutError(f"Timed out while downloading article '{url}'.") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise TimeoutError(f"Timed out while downloading article '{url}'.") from exc
            raise

        self._html_cache[url] = (now, html)
        return html, False

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

    def _extract_json_ld_metadata(self, json_ld_blocks: list[str]) -> _ArticleMetadata:
        best = _ArticleMetadata()
        best_score = -1

        for block in json_ld_blocks:
            try:
                payload = json.loads(block)
            except json.JSONDecodeError:
                continue

            for item in self._flatten_json_ld(payload):
                article_type = item.get("@type")
                if isinstance(article_type, list):
                    types = {value.lower() for value in article_type if isinstance(value, str)}
                elif isinstance(article_type, str):
                    types = {article_type.lower()}
                else:
                    types = set()

                if not types.intersection(JSON_LD_ARTICLE_TYPES):
                    continue

                article_body = self._normalize_json_ld_body(item.get("articleBody"))
                score = len(article_body)
                if score <= best_score:
                    continue

                best = _ArticleMetadata(
                    title=self._clean_line(str(item.get("headline") or item.get("name") or "")) or None,
                    author=self._extract_author(item.get("author")),
                    published_at=self._parse_datetime(
                        str(item.get("datePublished") or item.get("dateCreated") or "")
                    ),
                    source=self._extract_publisher_name(item.get("publisher")),
                    article_body=article_body or None,
                )
                best_score = score

        return best

    def _merge_metadata(
        self,
        target: _FetchTarget,
        parser: _ArticleHtmlParser,
        json_ld_metadata: _ArticleMetadata,
    ) -> _ArticleMetadata:
        return _ArticleMetadata(
            title=(
                json_ld_metadata.title
                or self._first_non_empty(
                    parser.meta.get("og:title"),
                    parser.meta.get("twitter:title"),
                    parser.title,
                    target.title,
                )
            ),
            author=(
                json_ld_metadata.author
                or self._first_non_empty(
                    parser.meta.get("author"),
                    parser.meta.get("article:author"),
                )
            ),
            published_at=(
                json_ld_metadata.published_at
                or self._parse_datetime(
                    self._first_non_empty(
                        parser.meta.get("article:published_time"),
                        parser.meta.get("og:published_time"),
                        parser.meta.get("parsely-pub-date"),
                        parser.meta.get("pubdate"),
                        parser.meta.get("date"),
                    )
                )
                or target.published_at
            ),
            source=(
                json_ld_metadata.source
                or self._first_non_empty(parser.meta.get("og:site_name"), target.source)
                or self._source_from_url(target.url)
            ),
            article_body=json_ld_metadata.article_body,
        )

    def _extract_content_text(
        self,
        parser: _ArticleHtmlParser,
        json_ld_metadata: _ArticleMetadata,
        html: str,
    ) -> tuple[str | None, str]:
        if json_ld_metadata.article_body:
            cleaned = self._clean_content_text(json_ld_metadata.article_body)
            if len(cleaned) >= MIN_CONTENT_LENGTH:
                return "json_ld", cleaned

        article_text = self._clean_content_text("\n\n".join(self._dedupe_lines(parser.article_blocks)))
        if len(article_text) >= MIN_CONTENT_LENGTH:
            return "article_tag", article_text

        heuristic_text = self._clean_content_text(self._build_heuristic_text(parser.heuristic_blocks))
        if len(heuristic_text) >= MIN_CONTENT_LENGTH:
            return "heuristic", heuristic_text

        paragraph_fallback = self._clean_content_text(self._extract_paragraph_fallback_text(html))
        if len(paragraph_fallback) >= MIN_CONTENT_LENGTH:
            return "paragraph_fallback", paragraph_fallback

        fallback = max((json_ld_metadata.article_body or ""), article_text, heuristic_text, paragraph_fallback, key=len)
        return None, fallback

    def _build_heuristic_text(self, blocks: list[dict[str, Any]]) -> str:
        selected: list[tuple[int, str]] = []
        seen: set[str] = set()

        for block in blocks:
            text = self._clean_line(block["text"])
            if not text:
                continue
            if len(text) < 80:
                continue
            if self._looks_like_noise(text, block["context"]):
                continue

            normalized_key = text.lower()
            if normalized_key in seen:
                continue

            seen.add(normalized_key)
            score = len(text)
            if block["in_article"]:
                score += 250
            if block["tag"] == "p":
                score += 120
            if text.count(".") >= 2:
                score += 80
            if len(text.split()) >= 20:
                score += 40

            if score >= 160:
                selected.append((block["index"], text))

        selected.sort(key=lambda item: item[0])
        return "\n\n".join(text for _, text in selected)

    def _extract_paragraph_fallback_text(self, html: str) -> str:
        paragraphs: list[str] = []
        for match in PARAGRAPH_PATTERN.findall(html):
            text = re.sub(r"<[^>]+>", " ", match)
            text = self._clean_line(text)
            if not text:
                continue
            lowered = text.lower()
            if any(marker in lowered for marker in [
                "adresa ta de email",
                "campurile obligatorii",
                "lasa un raspuns",
                "publicată.",
                "comentariu",
            ]):
                break
            if len(text) < 60:
                continue
            if self._looks_like_noise(text, "paragraph_fallback"):
                continue
            paragraphs.append(text)
            if sum(len(item) for item in paragraphs) >= 4000:
                break
        return "\n\n".join(paragraphs)

    def _clean_content_text(self, raw_text: str) -> str:
        if not raw_text:
            return ""

        text = unescape(raw_text)
        text = text.replace("\r", "\n")
        text = re.sub(r"<[^>]+>", " ", text)
        text = MULTISPACE_PATTERN.sub(" ", text)
        text = text.replace(" \n", "\n").replace("\n ", "\n")

        lines: list[str] = []
        seen: set[str] = set()
        for raw_line in text.split("\n"):
            line = self._clean_line(raw_line)
            if not line:
                continue
            if len(line) < 25 and line.count(" ") < 4:
                continue
            line_key = line.lower()
            if line_key in seen:
                continue
            seen.add(line_key)
            lines.append(line)

        cleaned = "\n\n".join(lines)
        cleaned = MULTINEWLINE_PATTERN.sub("\n\n", cleaned)
        return cleaned.strip()

    def _clean_line(self, value: str) -> str:
        value = unescape(value)
        value = value.replace("\u00a0", " ")
        value = MULTISPACE_PATTERN.sub(" ", value)
        return value.strip(" \t\n")

    def _looks_like_noise(self, text: str, context: str) -> bool:
        lowered = f"{context} {text[:120]}".lower()
        return any(hint in lowered for hint in JUNK_HINTS)

    def _normalize_json_ld_body(self, article_body: Any) -> str:
        if isinstance(article_body, str):
            return article_body.strip()
        if isinstance(article_body, list):
            parts = [str(item).strip() for item in article_body if str(item).strip()]
            return "\n\n".join(parts)
        return ""

    def _extract_author(self, author_value: Any) -> str | None:
        if isinstance(author_value, str):
            return self._clean_line(author_value) or None
        if isinstance(author_value, list):
            parts = [self._extract_author(item) for item in author_value]
            merged = ", ".join(part for part in parts if part)
            return merged or None
        if isinstance(author_value, dict):
            return self._clean_line(str(author_value.get("name") or "")) or None
        return None

    def _extract_publisher_name(self, publisher_value: Any) -> str | None:
        if isinstance(publisher_value, str):
            return self._clean_line(publisher_value) or None
        if isinstance(publisher_value, dict):
            return self._clean_line(str(publisher_value.get("name") or "")) or None
        return None

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

    def _dedupe_lines(self, items: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = self._clean_line(item)
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(normalized)
        return result

    def _parse_datetime(self, raw_value: str | None) -> datetime | None:
        if not raw_value:
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

        match = DATE_PATTERN.search(value)
        if match:
            try:
                return datetime.fromisoformat(match.group(0)).replace(tzinfo=UTC)
            except ValueError:
                return None

        return None

    def _source_from_url(self, url: str) -> str:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown-source"

    def _first_non_empty(self, *values: str | None) -> str | None:
        for value in values:
            cleaned = self._clean_line(value or "")
            if cleaned:
                return cleaned
        return None
