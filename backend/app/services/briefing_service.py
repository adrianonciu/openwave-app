from datetime import date

from app.models.article import Article
from app.models.briefing import DailyBriefing, DailyBriefingArticle
from app.models.segment import Segment
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

    def _resolve_section_for_segment(self, article: Article, index: int, segment: Segment) -> str:
        if segment.section and segment.section != 'General':
            return segment.section
        if index == 0:
            return 'Top story'
        return self._infer_section(article)

    def _build_section_cue_text(self, section_name: str) -> str:
        section_lower = section_name.lower()
        if section_lower == 'economy':
            return 'In economy news.'
        if section_lower == 'tech':
            return 'In technology.'
        if section_lower == 'international':
            return 'In international news.'

        return f"In {section_lower}."

    def _insert_section_cues(self, ordered_segments: list[Segment]) -> list[Segment]:
        if not ordered_segments:
            return []

        segments_with_cues: list[Segment] = []
        previous_section = ordered_segments[0].section
        next_segment_id = max(segment.id for segment in ordered_segments) + 1

        for index, segment in enumerate(ordered_segments):
            if index > 0 and segment.section != previous_section:
                cue = self.segment_service.create_section_cue(segment.section, segment_id=next_segment_id)
                cue_text = self._build_section_cue_text(segment.section)
                cue.title = cue_text
                cue.narration_text = cue_text
                cue.summary = cue_text
                cue.section = segment.section
                segments_with_cues.append(cue)
                next_segment_id += 1

            segments_with_cues.append(segment)
            previous_section = segment.section

        return segments_with_cues

    def _build_internal_playback_segments(self, article_segments: list[Segment]) -> list[Segment]:
        # Perspective pairs now live in the modern briefing assembly pipeline;
        # the legacy briefing path keeps only section cues.
        return self._insert_section_cues(article_segments)

    def _prepend_intro_segment(self, playback_segments: list[Segment], headline: str) -> list[Segment]:
        next_segment_id = (
            max(segment.id for segment in playback_segments) + 1
            if playback_segments
            else 1
        )
        intro_segment = self.segment_service.create_intro_segment(
            headline=headline,
            segment_id=next_segment_id,
        )
        return [intro_segment, *playback_segments]

    def _build_briefing_articles(
        self,
        articles: list[Article],
        segments: list[Segment],
    ) -> list[DailyBriefingArticle]:
        briefing_articles: list[DailyBriefingArticle] = []

        for article, segment in zip(articles, segments):
            article_data = article.model_dump()
            briefing_articles.append(
                DailyBriefingArticle(
                    **article_data,
                    section=segment.section,
                )
            )

        return briefing_articles

    def _select_briefing_articles(self) -> list[Article]:
        return self.article_service.get_articles()[:5]

    def _build_briefing_segments(self, ordered_articles: list[Article]) -> list[Segment]:
        segments = [
            self.segment_service.create_segment_from_article(article, segment_id=index)
            for index, article in enumerate(ordered_articles, start=1)
        ]

        for index, (article, segment) in enumerate(zip(ordered_articles, segments)):
            segment.section = self._resolve_section_for_segment(article, index, segment)

        return segments

    def _build_highlights_from_segments(self, segments: list[Segment]) -> list[str]:
        return [segment.title for segment in segments]

    def get_today_briefing(self) -> DailyBriefing:
        articles = self._select_briefing_articles()
        headline = f"Top {len(articles)} stories today"
        article_segments = self._build_briefing_segments(articles)
        playback_segments = self._build_internal_playback_segments(article_segments)
        playback_segments = self._prepend_intro_segment(playback_segments, headline=headline)
        highlights = self._build_highlights_from_segments(article_segments)
        briefing_articles = self._build_briefing_articles(articles, article_segments)

        return DailyBriefing(
            date=date.today(),
            headline=headline,
            highlights=highlights,
            articles=briefing_articles,
            segments=playback_segments,
        )


