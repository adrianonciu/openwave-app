from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from app.models.article_fetch import ArticleFetchResult, FetchedArticle
from app.models.live_source_ingestion import LiveStoryCandidate
from app.services.article_fetch_service import ArticleFetchService

CACHE_PATH = Path(__file__).resolve().parents[2] / 'data' / 'article_fetch_cache.json'
ARTICLE_CACHE_TTL_SECONDS = 7200


class ArticleFetchAndCleanService:
    def __init__(self) -> None:
        self.fetch_service = ArticleFetchService()

    def fetch_candidate_article(self, candidate: LiveStoryCandidate) -> ArticleFetchResult:
        cached_article = self._load_cached_article(candidate.original_url)
        if cached_article is not None:
            return ArticleFetchResult(status='success', article=cached_article, extraction_method=None, cached=True)

        result = self.fetch_service.fetch_article(candidate.original_url)
        if result.status == 'success' and result.article is not None:
            article = result.article.model_copy(
                update={
                    'source': candidate.source_name,
                    'source_scope': candidate.source_scope,
                    'source_region': candidate.county if candidate.source_scope == 'local' else candidate.region,
                    'is_local_source': candidate.source_scope == 'local',
                    'published_at': candidate.published_at,
                }
            )
            self._save_cached_article(article)
            return result.model_copy(update={'article': article})
        return result

    def _load_cached_article(self, url: str) -> FetchedArticle | None:
        payload = self._read_cache()
        record = payload.get(url)
        if not record:
            return None
        cached_at = datetime.fromisoformat(record['cached_at'])
        if (datetime.now(UTC) - cached_at).total_seconds() > ARTICLE_CACHE_TTL_SECONDS:
            return None
        return FetchedArticle(**record['article'])

    def _save_cached_article(self, article: FetchedArticle) -> None:
        payload = self._read_cache()
        payload[article.url] = {
            'cached_at': datetime.now(UTC).isoformat(),
            'article': article.model_dump(mode='json'),
        }
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    def _read_cache(self) -> dict[str, dict[str, object]]:
        if not CACHE_PATH.exists():
            return {}
        try:
            return json.loads(CACHE_PATH.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return {}
