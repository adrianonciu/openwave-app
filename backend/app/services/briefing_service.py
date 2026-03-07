from datetime import date

from app.models.briefing import DailyBriefing
from app.services.article_service import ArticleService
from app.services.segment_service import SegmentService


class BriefingService:
    def __init__(
        self,
        article_service: ArticleService | None = None,
        segment_service: SegmentService | None = None,
    ) -> None:
        self.article_service = article_service or ArticleService()
        self.segment_service = segment_service or SegmentService()

    def get_today_briefing(self) -> DailyBriefing:
        articles = self.article_service.get_articles()[:5]
        segments = [
            self.segment_service.create_segment_from_article(article, segment_id=index)
            for index, article in enumerate(articles, start=1)
        ]
        highlights = [segment.title for segment in segments]

        return DailyBriefing(
            date=date.today(),
            headline=f"Top {len(articles)} stories today",
            highlights=highlights,
            articles=articles,
        )
