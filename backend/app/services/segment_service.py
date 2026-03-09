import re

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

    def create_section_cue(self, section_name: str, segment_id: int) -> Segment:
        cleaned_section = section_name.strip() or "General"
        cue_duration_seconds = 3

        return Segment(
            id=segment_id,
            type=Segment.TYPE_SECTION_CUE,
            title=cleaned_section,
            summary=cleaned_section,
            source="OpenWave",
            estimated_duration_seconds=cue_duration_seconds,
            tags=[],
            article_id=0,
            narration_text=cleaned_section,
            section=cleaned_section,
            duration_estimate=cue_duration_seconds,
        )

    def create_intro_segment(self, headline: str, segment_id: int) -> Segment:
        normalized_headline = headline.strip().lower()
        count_match = re.search(r"top\s+(\d+)\s+stories", normalized_headline)
        if count_match:
            story_count = count_match.group(1)
            intro_text = f"Good morning. Here are the top {story_count} stories today."
        else:
            intro_text = "Good morning. Here are the top stories today."
        intro_duration_seconds = 5

        return Segment(
            id=segment_id,
            type=Segment.TYPE_INTRO,
            title="Intro",
            summary=intro_text,
            source="OpenWave",
            estimated_duration_seconds=intro_duration_seconds,
            tags=[],
            article_id=0,
            narration_text=intro_text,
            section="Intro",
            duration_estimate=intro_duration_seconds,
        )
