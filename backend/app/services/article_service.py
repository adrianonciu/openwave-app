from datetime import datetime, timezone

from app.models.article import Article


class ArticleService:
    def get_articles(self) -> list[Article]:
        now = datetime.now(timezone.utc)
        return [
            Article(
                id=1,
                title="Global markets open mixed as inflation cools",
                source="OpenWave Newswire",
                summary="Analysts report cautious optimism after a lower-than-expected inflation print.",
                url="https://example.com/articles/1",
                published_at=now,
            ),
            Article(
                id=2,
                title="New battery breakthrough promises faster charging",
                source="Tech Dispatch",
                summary="Researchers unveiled a prototype chemistry that may reduce charge times.",
                url="https://example.com/articles/2",
                published_at=now,
            ),
            Article(
                id=3,
                title="City pilots AI-assisted traffic control",
                source="Civic Daily",
                summary="The pilot project aims to optimize signal timing and reduce commute times.",
                url="https://example.com/articles/3",
                published_at=now,
            ),
        ]