from app.models.article import Article
from app.models.segment import Segment


class SegmentService:
    def create_segment_from_article(self, article: Article, segment_id: int) -> Segment:
        return Segment(
            id=segment_id,
            type="news",
            title=article.title,
            summary=article.summary,
            source=article.source,
            estimated_duration_seconds=30,
            tags=[],
            article_id=article.id,
        )
