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
                    summary="",
                    url=item.get("link", ""),
                    published_at=published_at,
                )
            )

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

