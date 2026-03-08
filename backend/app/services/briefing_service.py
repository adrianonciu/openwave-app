from datetime import date

from app.models.article import Article
from app.models.briefing import DailyBriefing, DailyBriefingArticle
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

    def _article_to_text_blob(self, article: Article) -> str:
        return f"{article.title} {article.summary} {article.source}".lower()

    def _infer_section(self, article: Article) -> str:
        text = self._article_to_text_blob(article)

        economy_keywords = (
            'economy',
            'economic',
            'inflation',
            'gdp',
            'market',
            'stock',
            'stocks',
            'bank',
            'banking',
            'interest rate',
            'fed',
            'earnings',
            'recession',
            'trade',
            'tariff',
        )
        tech_keywords = (
            'tech',
            'technology',
            'ai',
            'artificial intelligence',
            'software',
            'chip',
            'semiconductor',
            'cyber',
            'startup',
            'apple',
            'google',
            'microsoft',
            'meta',
            'tesla',
            'iphone',
            'android',
        )

        if any(keyword in text for keyword in economy_keywords):
            return 'Economy'
        if any(keyword in text for keyword in tech_keywords):
            return 'Tech'

        return 'International'

    def _build_briefing_articles(
        self,
        articles: list[Article],
    ) -> list[DailyBriefingArticle]:
        briefing_articles: list[DailyBriefingArticle] = []

        for index, article in enumerate(articles):
            section = 'Top story' if index == 0 else self._infer_section(article)
            article_data = article.model_dump()
            briefing_articles.append(
                DailyBriefingArticle(
                    **article_data,
                    section=section,
                )
            )

        return briefing_articles

    def get_today_briefing(self) -> DailyBriefing:
        articles = self.article_service.get_articles()[:5]
        segments = [
            self.segment_service.create_segment_from_article(article, segment_id=index)
            for index, article in enumerate(articles, start=1)
        ]
        highlights = [segment.title for segment in segments]
        briefing_articles = self._build_briefing_articles(articles)

        return DailyBriefing(
            date=date.today(),
            headline=f"Top {len(articles)} stories today",
            highlights=highlights,
            articles=briefing_articles,
        )
