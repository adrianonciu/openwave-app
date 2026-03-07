import re
from datetime import datetime, timezone

from app.models.article import Article
from app.services.rss_ingestion_service import ingest_rss


class ArticleService:
    def get_articles(self) -> list[Article]:
        rss_items = ingest_rss()[:20]
        articles: list[Article] = []

        for index, item in enumerate(rss_items, start=1):
            published_at = self._parse_published_at(item.get("published_date", ""))
            articles.append(
                Article(
                    id=index,
                    title=item.get("title", ""),
                    source=item.get("source_name", "Unknown source"),
                    summary=self._strip_html(item.get("description", "") or ""),
                    url=item.get("link", ""),
                    published_at=published_at,
                )
            )

        articles.sort(key=lambda article: article.published_at, reverse=True)
        return articles

    @staticmethod
    def _parse_published_at(raw_date: str) -> datetime:
        if not raw_date:
            return datetime.now(timezone.utc)

        try:
            parsed = datetime.fromisoformat(raw_date)
        except ValueError:
            return datetime.now(timezone.utc)

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _strip_html(raw_html: str) -> str:
        return re.sub(r"<[^>]+>", "", raw_html).strip()
