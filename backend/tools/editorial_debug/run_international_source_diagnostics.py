from __future__ import annotations

from pathlib import Path
import json
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.article_fetch_service import ArticleFetchService
from app.services.source_watcher_service import SourceWatcherService

OUTPUT_DIR = BACKEND_ROOT / "debug_output"
JSON_OUTPUT_PATH = OUTPUT_DIR / "international_source_diagnostics.json"
TEXT_OUTPUT_PATH = OUTPUT_DIR / "international_source_diagnostics.txt"
AUDIT_SOURCE_IDS = [
    "intl-reuters",
    "intl-guardian",
    "intl-nyt",
    "intl-cnn",
    "intl-bloomberg",
    "intl-ft",
    "intl-wsj",
    "intl-washington-post",
    "intl-economist",
    "intl-npr",
    "intl-foxnews",
]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    watcher = SourceWatcherService()
    fetcher = ArticleFetchService()
    configs = {config.source_id: config for config in watcher.load_source_configs()}

    diagnostics: list[dict[str, object]] = []
    for source_id in AUDIT_SOURCE_IDS:
        config = configs[source_id]
        entry: dict[str, object] = {
            "source_id": config.source_id,
            "source_name": config.source_name,
            "source_url": config.source_url,
            "rss_url": config.rss_url,
            "parser_type": config.parser_type,
            "discovered_items_count": 0,
            "fetched_successfully_count": 0,
            "candidate_count_after_cleaning": 0,
            "failure_stage": None,
            "failure_reason": None,
            "latest_url": None,
            "latest_title": None,
        }
        try:
            latest = watcher.get_latest_content(config)
            entry["discovered_items_count"] = 1
            entry["latest_url"] = latest.url
            entry["latest_title"] = latest.title
        except Exception as exc:
            entry["failure_stage"] = "source_discovery"
            entry["failure_reason"] = str(exc)
            diagnostics.append(entry)
            continue

        fetch_result = fetcher.fetch_article(latest)
        if fetch_result.status == "success" and fetch_result.article is not None:
            entry["fetched_successfully_count"] = 1
            entry["candidate_count_after_cleaning"] = 1
        else:
            entry["failure_stage"] = "article_fetch"
            entry["failure_reason"] = fetch_result.error_message or fetch_result.status
        diagnostics.append(entry)

    payload = {
        "audited_sources": len(diagnostics),
        "sources": diagnostics,
    }
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "INTERNATIONAL SOURCE DIAGNOSTICS",
        "",
        f"audited_sources: {payload['audited_sources']}",
        "",
    ]
    for index, item in enumerate(diagnostics, start=1):
        lines.extend([
            f"{index}. {item['source_name']}",
            f"   source_id: {item['source_id']}",
            f"   source_url: {item['source_url']}",
            f"   rss_url: {item['rss_url'] or 'none'}",
            f"   parser_type: {item['parser_type']}",
            f"   discovered_items_count: {item['discovered_items_count']}",
            f"   fetched_successfully_count: {item['fetched_successfully_count']}",
            f"   candidate_count_after_cleaning: {item['candidate_count_after_cleaning']}",
            f"   failure_stage: {item['failure_stage'] or 'none'}",
            f"   failure_reason: {item['failure_reason'] or 'none'}",
            f"   latest_url: {item['latest_url'] or 'none'}",
            f"   latest_title: {item['latest_title'] or 'none'}",
            "",
        ])
    TEXT_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {JSON_OUTPUT_PATH}")
    print(f"Wrote {TEXT_OUTPUT_PATH}")
    print(json.dumps({
        "audited_sources": payload["audited_sources"],
        "sources_with_candidates": sum(1 for item in diagnostics if item["candidate_count_after_cleaning"] > 0),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
