from fastapi import APIRouter

from app.models.article import Article
from app.models.briefing import DailyBriefing
from app.services.article_service import ArticleService
from app.services.briefing_service import BriefingService

router = APIRouter()

article_service = ArticleService()
briefing_service = BriefingService(article_service=article_service)


@router.get("/articles", response_model=list[Article])
def get_articles() -> list[Article]:
    return article_service.get_articles()


@router.get("/briefing/today", response_model=DailyBriefing)
def get_today_briefing() -> DailyBriefing:
    return briefing_service.get_today_briefing()