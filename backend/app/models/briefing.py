from datetime import date

from pydantic import BaseModel

from app.models.article import Article


class DailyBriefingArticle(Article):
    section: str


class DailyBriefing(BaseModel):
    date: date
    headline: str
    highlights: list[str]
    articles: list[DailyBriefingArticle]
