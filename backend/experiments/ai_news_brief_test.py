from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import os
import re
from typing import Iterable
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - runtime dependency check
    raise SystemExit(
        "Missing dependency 'openai'. Install it before running this script."
    ) from exc

RRSS_SOURCES = [
("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
("DW World", "https://rss.dw.com/xml/rss-en-world"),
("NYTimes World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
("Guardian World", "https://www.theguardian.com/world/rss"),
("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
]

MAX_ARTICLES = 20
MAX_PER_SOURCE = 5
SELECT_COUNT = 5
TITLE_DUPLICATE_THRESHOLD = 0.60
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class Article:
    title: str
    description: str
    link: str
    published_at: datetime
    source: str


def _fetch_feed(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "OpenWave-AI-Test/1.0"})
    with urlopen(request, timeout=15) as response:
        return response.read()


def _first_text(parent: ET.Element, *paths: str) -> str:
    for path in paths:
        element = parent.find(path)
        if element is not None and element.text:
            return element.text.strip()
    return ""


def _parse_datetime(raw_value: str) -> datetime:
    if not raw_value:
        return datetime.now(timezone.utc)

    try:
        parsed = parsedate_to_datetime(raw_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass

    cleaned = raw_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _parse_rss_items(root: ET.Element, source_name: str) -> Iterable[Article]:
    for item in root.findall("./channel/item"):
        title = _first_text(item, "title")
        description = _first_text(
            item,
            "description",
            "{http://purl.org/rss/1.0/modules/content/}encoded",
        )
        link = _first_text(item, "link")
        published_raw = _first_text(
            item,
            "pubDate",
            "published",
            "{http://purl.org/dc/elements/1.1/}date",
        )

        if not title or not link:
            continue

        yield Article(
            title=title,
            description=_clean_text(description),
            link=link,
            published_at=_parse_datetime(published_raw),
            source=source_name,
        )


def _parse_atom_items(root: ET.Element, source_name: str) -> Iterable[Article]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("./atom:entry", ns)
    for entry in entries:
        title = _first_text(entry, "{http://www.w3.org/2005/Atom}title")
        description = _first_text(
            entry,
            "{http://www.w3.org/2005/Atom}summary",
            "{http://www.w3.org/2005/Atom}content",
        )
        link = ""
        for link_element in entry.findall("{http://www.w3.org/2005/Atom}link"):
            href = link_element.attrib.get("href", "").strip()
            rel = link_element.attrib.get("rel", "alternate")
            if href and rel in {"alternate", ""}:
                link = href
                break
        if not link and entry.find("{http://www.w3.org/2005/Atom}link") is not None:
            link = entry.find("{http://www.w3.org/2005/Atom}link").attrib.get("href", "")

        published_raw = _first_text(
            entry,
            "{http://www.w3.org/2005/Atom}updated",
            "{http://www.w3.org/2005/Atom}published",
        )

        if not title or not link:
            continue

        yield Article(
            title=title,
            description=_clean_text(description),
            link=link,
            published_at=_parse_datetime(published_raw),
            source=source_name,
        )


def _extract_articles(source_name: str, feed_xml: bytes) -> list[Article]:
    root = ET.fromstring(feed_xml)

    if root.tag.endswith("rss") or root.find("channel") is not None:
        return list(_parse_rss_items(root, source_name))

    if root.tag.endswith("feed"):
        return list(_parse_atom_items(root, source_name))

    return []


def _clean_text(text: str) -> str:
    if not text:
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", text)
    compact = re.sub(r"\s+", " ", no_tags)
    return compact.strip()


def fetch_latest_articles() -> list[Article]:
    collected: list[Article] = []

    for source_name, url in RSS_SOURCES:
        try:
            feed_xml = _fetch_feed(url)
            collected.extend(_extract_articles(source_name, feed_xml))
        except Exception as exc:  # pragma: no cover - network/runtime path
            print(f"[WARN] Failed to read {source_name} ({url}): {exc}")

    collected.sort(key=lambda article: article.published_at, reverse=True)
    return collected[:MAX_ARTICLES]


def _normalize_title_words(title: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", title.lower())
    words = [word for word in cleaned.split() if word]
    return set(words)


def _title_similarity(words_a: set[str], words_b: set[str]) -> float:
    if not words_a or not words_b:
        return 0.0
    shared = words_a & words_b
    return len(shared) / max(1, min(len(words_a), len(words_b)))


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    deduped: list[Article] = []
    deduped_words: list[set[str]] = []

    # Articles are expected newest-first; first seen is kept.
    for article in articles:
        article_words = _normalize_title_words(article.title)
        is_duplicate = any(
            _title_similarity(article_words, seen_words) > TITLE_DUPLICATE_THRESHOLD
            for seen_words in deduped_words
        )
        if is_duplicate:
            continue

        deduped.append(article)
        deduped_words.append(article_words)

    return deduped


def limit_articles_per_source(articles: list[Article], max_per_source: int) -> list[Article]:
    source_counts: dict[str, int] = {}
    limited: list[Article] = []

    for article in articles:
        count = source_counts.get(article.source, 0)
        if count >= max_per_source:
            continue

        limited.append(article)
        source_counts[article.source] = count + 1

    return limited


def _build_selection_input(articles: list[Article]) -> str:
    lines = []
    for idx, article in enumerate(articles, start=1):
        lines.append(
            f"ID: {idx}\n"
            f"Source: {article.source}\n"
            f"Published: {article.published_at.isoformat()}\n"
            f"Title: {article.title}\n"
            f"Description: {article.description or '(no description)'}\n"
        )
    return "\n".join(lines)


def _extract_ids(response_text: str, max_id: int) -> list[int]:
    matches = re.findall(r"\b(\d{1,2})\b", response_text)
    ordered: list[int] = []
    for raw in matches:
        value = int(raw)
        if 1 <= value <= max_id and value not in ordered:
            ordered.append(value)
        if len(ordered) == SELECT_COUNT:
            break
    return ordered


def select_top_stories(client: OpenAI, model: str, articles: list[Article]) -> list[Article]:
    prompt = (
        "You are a global news editor selecting stories for a short radio briefing.\n\n"
        "Select the 5 most important and distinct global news stories.\n\n"
        "Rules:\n"
        "- Avoid duplicate stories about the same event.\n"
        "- Do not select more than 2 stories from the same ongoing conflict, crisis, or macro-event unless they clearly represent different dimensions.\n"
        "- Prefer global impact.\n"
        "- Prefer recent stories.\n"
        "- Prefer diversity of topics such as politics, economy, conflict, technology, climate, and society.\n\n"
        "Return only the IDs as a comma-separated list.\n\n"
        f"{_build_selection_input(articles)}"
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a senior global news editor."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    response_text = completion.choices[0].message.content or ""
    selected_ids = _extract_ids(response_text, len(articles))

    if len(selected_ids) < SELECT_COUNT:
        return articles[:SELECT_COUNT]

    return [articles[idx - 1] for idx in selected_ids]


def _build_summary_batch_input(articles: list[Article]) -> str:
    lines: list[str] = []
    for idx, article in enumerate(articles, start=1):
        lines.append(
            f"{idx}. {article.title}\n"
            f"Source: {article.source}\n"
            f"Description: {article.description or '(no description)'}\n"
        )
    return "\n".join(lines)


def _parse_numbered_summaries(text: str, expected_count: int) -> list[tuple[int, str, str]]:
    pattern = re.compile(
        r"^\s*(\d{1,2})\s*[\.\)\-:]?\s*(.+?)\n(.+?)(?=^\s*\d{1,2}\s*[\.\)\-:]?\s|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    parsed: list[tuple[int, str, str]] = []
    for match in pattern.finditer(text):
        idx = int(match.group(1))
        title = match.group(2).strip()
        narration = match.group(3).strip()
        parsed.append((idx, title, narration))

    if not parsed:
        fallback_parts = re.split(r"\n\s*\n+", text.strip())
        for idx, part in enumerate(fallback_parts, start=1):
            if idx > expected_count:
                break
            lines = [line.strip() for line in part.splitlines() if line.strip()]
            if not lines:
                continue
            first = lines[0]
            title = re.sub(r"^\s*\d{1,2}\s*[\.\)\-:]?\s*", "", first).strip()
            narration = " ".join(lines[1:]).strip() if len(lines) > 1 else ""
            if title:
                parsed.append((idx, title, narration))

    parsed.sort(key=lambda row: row[0])
    if len(parsed) < expected_count:
        return []
    return parsed[:expected_count]


def summarize_all_for_radio(client: OpenAI, model: str, articles: list[Article]) -> list[str]:
    prompt = (
        "Write a short radio-style news script in English.\n"
        "Rules:\n"
        "- 2 short sentences only\n"
        "- clear spoken style\n"
        "- factual and concise\n"
        "- no unnecessary adjectives\n"
        "- no analyst-style filler\n"
        "- easy to read aloud with TTS\n\n"
        "Apply these rules to each story below.\n\n"
        "Return this exact structure:\n"
        "1. Title\n"
        "Narration\n\n"
        "2. Title\n"
        "Narration\n\n"
        "...\n\n"
        f"{_build_summary_batch_input(articles)}"
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You write concise news scripts for radio hosts."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )

    response_text = (completion.choices[0].message.content or "").strip()
    parsed = _parse_numbered_summaries(response_text, len(articles))
    if not parsed:
        return [response_text] + ["" for _ in range(len(articles) - 1)]

    narrations = [narration for _, _, narration in parsed]
    if len(narrations) < len(articles):
        narrations.extend(["" for _ in range(len(articles) - len(narrations))])
    return narrations[: len(articles)]


def _print_brief(selected: list[Article], narrations: list[str]) -> None:
    print("DAILY RADIO BRIEF (AI TEST)\n")
    for idx, article in enumerate(selected, start=1):
        narration = narrations[idx - 1] if idx - 1 < len(narrations) else ""
        print(f"{idx}. Source: {article.source}")
        print(f"   Published: {article.published_at.isoformat()}")
        print(f"   Title: {article.title}")
        print(f"   Narration: {narration}")
        print(f"   Link: {article.link}")
        print()


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set.")

    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    client = OpenAI(api_key=api_key)

    articles = fetch_latest_articles()
    if not articles:
        raise SystemExit("No articles were fetched from the configured RSS sources.")

    articles = deduplicate_articles(articles)
    articles = limit_articles_per_source(articles, MAX_PER_SOURCE)
    if not articles:
        raise SystemExit("No articles remained after deduplication and source balancing.")

    selected = select_top_stories(client, model, articles)
    narrations = summarize_all_for_radio(client, model, selected)
    _print_brief(selected, narrations)


if __name__ == "__main__":
    main()



