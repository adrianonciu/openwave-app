from datetime import date

from app.models.briefing import DailyBriefing
from app.services.article_service import ArticleService


class BriefingService:
    def __init__(self, article_service: ArticleService | None = None) -> None:
        self.article_service = article_service or ArticleService()

    def get_today_briefing(self) -> DailyBriefing:
        articles = self.article_service.get_articles()
        highlights = [article.title for article in articles[:3]]

        return DailyBriefing(
            date=date.today(),
            headline="Your OpenWave Daily Briefing",
            highlights=highlights,
            articles=articles,
        )