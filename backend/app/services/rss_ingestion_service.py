"""RSS ingestion service using Python standard libraries only."""

from __future__ import annotations

from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

RSS_SOURCES = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.dw.com/xml/rss-en-world",
]


def _read_feed(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "OpenWaveRSS/1.0"})
    with urlopen(request, timeout=10) as response:
        return response.read()


def _first_text(parent: ET.Element, *paths: str) -> str:
    for path in paths:
        element = parent.find(path)
        if element is not None and element.text:
            return element.text.strip()
    return ""


def _normalize_date(raw_date: str) -> str:
    if not raw_date:
        return ""

    try:
        parsed = parsedate_to_datetime(raw_date)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return raw_date


def _source_name(root: ET.Element, feed_url: str) -> str:
    channel_title = _first_text(root, "channel/title")
    if channel_title:
        return channel_title

    host = urlparse(feed_url).netloc
    return host.replace("www.", "")


def ingest_rss() -> list[dict[str, Any]]:
    """Fetch and parse configured RSS feeds into article dictionaries."""
    articles: list[dict[str, Any]] = []

    for feed_url in RSS_SOURCES:
        feed_bytes = _read_feed(feed_url)
        root = ET.fromstring(feed_bytes)
        source_name = _source_name(root, feed_url)

        for item in root.findall("./channel/item"):
            title = _first_text(item, "title")
            link = _first_text(item, "link")
            published_raw = _first_text(item, "pubDate", "published", "{http://purl.org/dc/elements/1.1/}date")

            if not title or not link:
                continue

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "published_date": _normalize_date(published_raw),
                    "source_name": source_name,
                }
            )

    return articles
