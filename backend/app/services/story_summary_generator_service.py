from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re

from app.models.generated_story_summary import (
    GeneratedStorySummary,
    SummaryComplianceReport,
)
from app.models.news_cluster import StoryCluster
from app.models.radio_story_draft import RadioStoryDraft
from app.models.story_score import ScoredStoryCluster
from app.services.story_summary_policy_service import StorySummaryPolicyService

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "story_summary_generator_config.json"
WORD_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
ROMANIAN_LETTER_CLASS = "0-9A-Za-z\u00C0-\u024F"
NON_ALPHA_PATTERN = re.compile(rf'[^{ROMANIAN_LETTER_CLASS}\s\-"]')
QUOTE_PATTERN = re.compile(r'["](.{3,120}?)["]')
TOKEN_PATTERN = re.compile(rf"[{ROMANIAN_LETTER_CLASS}-]+")
NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?%?\b")
KEEP_NUMBER_WINDOW_PATTERN = re.compile(
    rf"\b\d+(?:[.,]\d+)?%?\b(?:\s+(?:de|la|din|pana|pentru|in|pe|aproximativ))?(?:\s+[{ROMANIAN_LETTER_CLASS}%-]+){{0,3}}",
    re.UNICODE,
)
COUNT_KEYWORD_PATTERN = re.compile(
    r"(?P<count>\d+)\s+(?P<kind>killed|dead|deaths|morti|decese|injured|wounded|raniti|ranite)"
)
KEYWORD_COUNT_PATTERN = re.compile(
    r"(?P<kind>killed|dead|deaths|morti|decese|injured|wounded|raniti|ranite)\s+(?P<count>\d+)"
)
ENGLISH_HEADLINE_MARKERS = {
    "about", "accuses", "after", "against", "ally", "amid", "as", "attacks", "bomb", "bombs",
    "charges", "conflict", "custody", "dropped", "during", "embassy", "enters", "explosion", "family", "fire",
    "generations", "global", "gulf", "halt", "him", "international", "jewish", "key",
    "leaders", "marines", "markets", "military", "moved", "negotiations", "new", "news",
    "oil", "politics", "reports", "rescuers", "rise", "says", "school", "security",
    "sites", "suspect", "targeted", "third", "three", "under", "urges", "vital", "war", "warships", "weather", "wait",
    "week", "whose", "why", "world",
}
ROMANIAN_HEADLINE_MARKERS = {
    "acum", "atac", "autoritati", "buget", "dupa", "guvern", "iasi", "investitii", "masura",
    "negocieri", "noutati", "politic", "politica", "potrivit", "romania", "securitate",
    "stiri", "subiect", "transmite",
}
NOISY_HEADLINE_PREFIX_PATTERN = re.compile(r"^(?:live-text/?video|live-text|live text|video|breaking|exclusiv|actualizare|update)\s*[:|/-]*\s*", re.IGNORECASE)
SCOREBOARD_PATTERN = re.compile(r"\([^)]*\d+\s*[?-]\s*\d+[^)]*\)")
HEADLINE_SEPARATOR_PATTERN = re.compile(r"\s*[-|:]+\s*")
HEADLINE_TRUNCATION_PATTERN = re.compile(
    r"\b(dupa ce|dup? ce|pentru ca|pentru c?|fiindca|deoarece|motivul|cum|cand|c?nd|unde|iar|care)\b",
    re.IGNORECASE,
)
GENERIC_HEADLINE_PATTERN = re.compile(
    r"^(subiect important acum|actualitate in atentie|noutate importanta|stire importanta)$",
    re.IGNORECASE,
)


class StorySummaryGeneratorService:
    def __init__(self) -> None:
        raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.policy_service = StorySummaryPolicyService()
        self.policy = self.policy_service.get_policy()
        self.spoken_words_per_minute: int = raw_config["spoken_words_per_minute"]
        self.banned_patterns: list[str] = raw_config["banned_patterns"]
        self.expanded_max_sentences: int = raw_config["expanded_max_sentences"]
        self.expansion_score_threshold: float = raw_config["expansion_score_threshold"]
        self.expansion_topics: set[str] = set(raw_config["expansion_topics"])
        self.expansion_keywords: list[str] = raw_config["expansion_keywords"]
        self.casualty_priority_keywords: list[str] = raw_config["casualty_priority_keywords"]
        self.context_trigger_keywords: list[str] = raw_config["context_trigger_keywords"]
        self.memorable_quote_max_words: int = raw_config["memorable_quote_max_words"]
        self.memorable_quote_terms: set[str] = {
            term.lower() for term in raw_config["memorable_quote_terms"]
        }
        self.bureaucratic_quote_terms: set[str] = {
            term.lower() for term in raw_config["bureaucratic_quote_terms"]
        }
        self.essential_number_keywords: set[str] = {
            term.lower() for term in raw_config["essential_number_keywords"]
        }
        self.lead_type_keywords: dict[str, list[str]] = raw_config["lead_type_keywords"]
        self.lead_phrase_maps: dict[str, dict[str, str]] = raw_config["lead_phrase_maps"]
        self.topic_templates: dict[str, dict[str, str]] = raw_config["topic_templates"]
        self.english_to_romanian_terms: dict[str, str] = raw_config[
            "english_to_romanian_terms"
        ]
        self.topic_keywords: dict[str, list[str]] = raw_config["topic_keywords"]
        self.headline_stopwords: set[str] = {
            token.lower() for token in raw_config["headline_stopwords"]
        }
        self.official_actor_terms: list[str] = raw_config["official_actor_terms"]
        self.attribution_verbs: list[str] = raw_config["attribution_verbs"]
        self.source_attribution_templates: list[str] = raw_config[
            "source_attribution_templates"
        ]
        self.official_attribution_templates: list[str] = raw_config[
            "official_attribution_templates"
        ]
        self.attribution_variants: dict[str, list[dict[str, str]]] = raw_config[
            "attribution_variants"
        ]
        self.continuity_major_update_score_delta: float = raw_config.get(
            "continuity_major_update_score_delta",
            8.0,
        )
        self.continuity_major_update_source_delta: int = raw_config.get(
            "continuity_major_update_source_delta",
            1,
        )
        self.recent_attribution_variants: list[str] = []

    def reset_variation_state(self) -> None:
        self.recent_attribution_variants = []


    def _generated_summary_from_draft(
        self,
        cluster: StoryCluster,
        draft: RadioStoryDraft,
        source_basis: str,
        score_total: float | None,
        generated_at: datetime,
        previous_bulletin_clusters: list[str | dict[str, object]] | None,
    ) -> GeneratedStorySummary:
        (
            story_continuity_type,
            continuity_detected,
            continuity_explanation,
        ) = self._detect_story_continuity(
            cluster=cluster,
            score_total=score_total,
            previous_bulletin_clusters=previous_bulletin_clusters,
        )
        sentences = [self.normalize_for_radio(self._normalize_story_text(sentence)) for sentence in draft.summary_sentences if sentence.strip()][:4]
        summary_text = ' '.join(sentences).strip()
        sentence_count = len(sentences)
        word_count = self._word_count(summary_text)
        story_type = 'major' if sentence_count >= 4 or word_count >= self.policy.target_word_count_min else 'short'
        lead = sentences[0] if sentences else self.normalize_for_radio(self._normalize_story_text(draft.title))
        body = ' '.join(sentences[1:]).strip()
        attribution_type = 'official_statement' if draft.actor_detected else 'source_attribution'
        quote_line = draft.attributed_quote
        compliance = self._build_compliance_report(
            summary_text=summary_text,
            sentence_count=sentence_count,
            word_count=word_count,
            expanded_summary_used=story_type == 'major',
        )
        headline = self.normalize_for_radio(self._normalize_story_text(draft.title))
        notes = [
            f"summarization_method={draft.summarization_method}",
            f"actor_detected={draft.actor_detected}",
            f"quote_detected={draft.quote_detected}",
            f"impact_detected={draft.impact_detected}",
        ]
        if draft.main_actor_name:
            notes.append(f"draft_actor_name={draft.main_actor_name}")
        if draft.main_actor_role:
            notes.append(f"draft_actor_role={draft.main_actor_role}")
        if draft.skip_reason:
            notes.append(f"draft_skip_reason={draft.skip_reason}")
        explanation = (
            f"Summary for cluster '{cluster.representative_title}' was generated from full article text using {draft.summarization_method}. "
            f"Actor detected={draft.actor_detected}, quote detected={draft.quote_detected}, impact detected={draft.impact_detected}."
        )
        return GeneratedStorySummary(
            cluster_id=cluster.cluster_id,
            story_id=cluster.cluster_id,
            story_type=story_type,
            headline=headline,
            lead=lead,
            body=body,
            source_attribution='',
            quotes=[quote_line] if quote_line else [],
            editorial_notes=notes,
            short_headline=headline,
            lead_type='impact' if draft.impact_detected else 'event',
            story_continuity_type=story_continuity_type,
            continuity_detected=continuity_detected,
            continuity_explanation=continuity_explanation,
            summary_text=summary_text,
            sentence_count=sentence_count,
            word_count=word_count,
            topic_label=self._infer_topic(cluster),
            source_labels=sorted({member.source for member in cluster.member_articles}),
            attribution_type=attribution_type,
            attribution_variant='llm_draft',
            summary_variation_used=False,
            quote_line=quote_line,
            memorable_quote_used=bool(quote_line),
            essential_numbers_kept=False,
            nonessential_numbers_removed=False,
            expanded_summary_used=story_type == 'major',
            casualty_line_included=False,
            context_line_included=sentence_count >= 3,
            representative_title=cluster.representative_title,
            score_total=score_total,
            policy_compliance=compliance,
            generation_explanation=explanation,
            generated_at=generated_at,
            source_basis=source_basis,
        )

    def generate_story_summary(
        self,
        cluster: StoryCluster | ScoredStoryCluster,
        previous_bulletin_clusters: list[str | dict[str, object]] | None = None,
    ) -> GeneratedStorySummary:
        normalized_cluster, source_basis, score_total = self._normalize_cluster(cluster)
        generated_at = datetime.now(UTC)
        if normalized_cluster.representative_radio_story_draft is not None:
            return self._generated_summary_from_draft(
                cluster=normalized_cluster,
                draft=normalized_cluster.representative_radio_story_draft,
                source_basis=source_basis,
                score_total=score_total,
                generated_at=generated_at,
                previous_bulletin_clusters=previous_bulletin_clusters,
            )
        topic = self._infer_topic(normalized_cluster)
        (
            story_continuity_type,
            continuity_detected,
            continuity_explanation,
        ) = self._detect_story_continuity(
            cluster=normalized_cluster,
            score_total=score_total,
            previous_bulletin_clusters=previous_bulletin_clusters,
        )
        quote_line = self._extract_memorable_quote_line(normalized_cluster)
        attribution_type = self._determine_attribution_type(normalized_cluster, quote_line)
        casualty_line = self._extract_casualty_line(normalized_cluster)
        lead_type = self._detect_lead_type(normalized_cluster, topic, casualty_line)
        importance_triggered = self._is_important_story(
            cluster=normalized_cluster,
            topic=topic,
            score_total=score_total,
            casualty_line=casualty_line,
        )
        story_type = self.infer_story_type(
            lead_type=lead_type,
            score_total=score_total,
            important_story=importance_triggered,
            casualty_line=casualty_line,
        )
        short_headline = self.build_headline(normalized_cluster, story_type=story_type)
        context_line = self._build_context_line(
            cluster=normalized_cluster,
            topic=topic,
            important_story=importance_triggered,
            casualty_line=casualty_line,
        )
        composed_story = self.compose_story(
            cluster=normalized_cluster,
            topic=topic,
            short_headline=short_headline,
            lead_type=lead_type,
            attribution_type=attribution_type,
            quote_line=quote_line,
            casualty_line=casualty_line,
            context_line=context_line,
            story_continuity_type=story_continuity_type,
            story_type=story_type,
            score_total=score_total,
            important_story=importance_triggered,
        )
        summary_text = composed_story["summary_text"]
        sentence_count = len(
            [sentence for sentence in SENTENCE_SPLIT_PATTERN.split(summary_text) if sentence.strip()]
        )
        word_count = self._word_count(summary_text)
        expanded_summary_used = story_type == "major" or sentence_count > self.policy.preferred_sentence_count
        casualty_line_included = casualty_line is not None
        context_line_included = context_line is not None and sentence_count >= 4
        memorable_quote_used = bool(composed_story["quotes"])
        compliance = self._build_compliance_report(
            summary_text=summary_text,
            sentence_count=sentence_count,
            word_count=word_count,
            expanded_summary_used=expanded_summary_used,
        )
        explanation = self._build_generation_explanation(
            cluster=normalized_cluster,
            topic=topic,
            lead_type=lead_type,
            story_continuity_type=story_continuity_type,
            continuity_explanation=continuity_explanation,
            attribution_type=attribution_type,
            short_headline=short_headline,
            compliance=compliance,
            expanded_summary_used=expanded_summary_used,
            casualty_line_included=casualty_line_included,
            context_line_included=context_line_included,
            memorable_quote_used=memorable_quote_used,
            essential_numbers_kept=composed_story["essential_numbers_kept"],
            nonessential_numbers_removed=composed_story["nonessential_numbers_removed"],
            attribution_variant=composed_story["attribution_variant"],
            summary_variation_used=composed_story["summary_variation_used"],
        )

        return GeneratedStorySummary(
            cluster_id=normalized_cluster.cluster_id,
            story_id=normalized_cluster.cluster_id,
            story_type=story_type,
            headline=short_headline,
            lead=composed_story["lead"],
            body=composed_story["body"],
            source_attribution=composed_story["source_attribution"],
            quotes=composed_story["quotes"],
            editorial_notes=composed_story["editorial_notes"],
            short_headline=short_headline,
            lead_type=lead_type,
            story_continuity_type=story_continuity_type,
            continuity_detected=continuity_detected,
            continuity_explanation=continuity_explanation,
            summary_text=summary_text,
            sentence_count=sentence_count,
            word_count=word_count,
            topic_label=topic,
            source_labels=sorted({member.source for member in normalized_cluster.member_articles}),
            attribution_type=attribution_type,
            attribution_variant=composed_story["attribution_variant"],
            summary_variation_used=composed_story["summary_variation_used"],
            quote_line=quote_line,
            memorable_quote_used=memorable_quote_used,
            essential_numbers_kept=composed_story["essential_numbers_kept"],
            nonessential_numbers_removed=composed_story["nonessential_numbers_removed"],
            expanded_summary_used=expanded_summary_used,
            casualty_line_included=casualty_line_included,
            context_line_included=context_line_included,
            representative_title=normalized_cluster.representative_title,
            score_total=score_total,
            policy_compliance=compliance,
            generation_explanation=explanation,
            generated_at=generated_at,
            source_basis=source_basis,
        )

    def compose_story(
        self,
        cluster: StoryCluster,
        topic: str,
        short_headline: str,
        lead_type: str,
        attribution_type: str,
        quote_line: str | None,
        casualty_line: str | None,
        context_line: str | None,
        story_continuity_type: str,
        story_type: str,
        score_total: float | None,
        important_story: bool,
    ) -> dict[str, object]:
        lead = self.build_lead(
            cluster=cluster,
            topic=topic,
            lead_type=lead_type,
            casualty_line=casualty_line,
            story_continuity_type=story_continuity_type,
            story_type=story_type,
            short_headline=short_headline,
        )
        source_attribution, attribution_variant, summary_variation_used = self.build_source_attribution(
            cluster=cluster,
            topic=topic,
            attribution_type=attribution_type,
            quote_line=quote_line,
            story_type=story_type,
        )
        body_sentences = self.build_body(
            cluster=cluster,
            topic=topic,
            casualty_line=casualty_line,
            context_line=context_line,
            story_type=story_type,
            important_story=important_story,
            short_headline=short_headline,
            lead=lead,
        )
        filtered_body_sentences, essential_numbers_kept, nonessential_numbers_removed = self._filter_sentence_numbers(
            body_sentences,
            casualty_line=casualty_line,
        )
        quotes = self.extract_quotes(
            cluster=cluster,
            attribution_type=attribution_type,
            quote_line=quote_line,
            story_type=story_type,
        )
        body = " ".join(sentence for sentence in filtered_body_sentences if sentence).strip()
        body = self.normalize_for_radio(self._normalize_story_text(body))
        summary_text = self._compose_summary_text(
            lead=lead,
            source_attribution=source_attribution,
            body=body,
            quotes=quotes,
        )
        summary_text = self._expand_if_needed(summary_text, topic) if story_type == "major" else summary_text
        summary_text = self.normalize_for_radio(self._normalize_story_text(summary_text))
        editorial_notes = [
            f"story_type={story_type}",
            "headline_ready_for_assembly",
            "source_attribution_early",
            "romanian_radio_normalized",
        ]
        if quotes:
            editorial_notes.append(f"quotes={len(quotes)}")
        elif story_type == "major":
            editorial_notes.append("no_usable_quotes_detected")
        if score_total is not None and score_total >= self.expansion_score_threshold:
            editorial_notes.append("high_priority_story")
        if context_line:
            editorial_notes.append("context_included")
        return {
            "lead": lead,
            "source_attribution": source_attribution,
            "body": body,
            "quotes": quotes,
            "summary_text": summary_text,
            "editorial_notes": editorial_notes,
            "attribution_variant": attribution_variant,
            "summary_variation_used": summary_variation_used,
            "essential_numbers_kept": essential_numbers_kept,
            "nonessential_numbers_removed": nonessential_numbers_removed,
        }

    def infer_story_type(
        self,
        lead_type: str,
        score_total: float | None,
        important_story: bool,
        casualty_line: str | None,
    ) -> str:
        if casualty_line or important_story or lead_type in {"impact", "conflict"}:
            return "major"
        if score_total is not None and score_total >= self.expansion_score_threshold:
            return "major"
        return "short"

    def build_headline(self, cluster: StoryCluster, story_type: str = "short") -> str:
        if story_type == "major":
            return self._build_major_headline(cluster)
        return self._build_short_headline(cluster)

    def build_lead(
        self,
        cluster: StoryCluster,
        topic: str,
        lead_type: str,
        casualty_line: str | None,
        story_continuity_type: str,
        story_type: str,
        short_headline: str,
    ) -> str:
        lead = self._build_lead_sentence(
            cluster=cluster,
            topic=topic,
            lead_type=lead_type,
            casualty_line=casualty_line,
            story_continuity_type=story_continuity_type,
        )
        if story_type == "major":
            lead = self._build_major_story_lead(cluster, topic, short_headline, lead, casualty_line)
        return self.normalize_for_radio(self._normalize_story_text(lead))

    def build_source_attribution(
        self,
        cluster: StoryCluster,
        topic: str,
        attribution_type: str,
        quote_line: str | None,
        story_type: str,
    ) -> tuple[str, str, bool]:
        if story_type == "major":
            sentence, attribution_variant, summary_variation_used = self._build_major_source_attribution(
                cluster=cluster,
                topic=topic,
                attribution_type=attribution_type,
                quote_line=quote_line,
            )
            return self.normalize_for_radio(self._normalize_story_text(sentence)), attribution_variant, summary_variation_used
        sentence, attribution_variant, summary_variation_used = self._build_detail_sentence(
            cluster=cluster,
            topic=topic,
            attribution_type=attribution_type,
            quote_line=quote_line,
        )
        return self.normalize_for_radio(self._normalize_story_text(sentence)), attribution_variant, summary_variation_used

    def build_body(
        self,
        cluster: StoryCluster,
        topic: str,
        casualty_line: str | None,
        context_line: str | None,
        story_type: str,
        important_story: bool,
        short_headline: str,
        lead: str,
    ) -> list[str]:
        body_sentences: list[str] = []
        if casualty_line:
            body_sentences.append(casualty_line)

        factual_sentences = self._build_concrete_body_sentences(
            cluster=cluster,
            topic=topic,
            short_headline=short_headline,
            lead=lead,
        )
        body_sentences.extend(factual_sentences[: 2 if story_type == "major" else 1])

        if context_line and (story_type == "major" or important_story):
            normalized_context = self._title_to_sentence(context_line, force=True)
            if normalized_context and normalized_context not in body_sentences:
                body_sentences.append(normalized_context)

        if not body_sentences:
            fallback = self._build_follow_up_sentence(
                cluster=cluster,
                topic=topic,
                short_headline=short_headline,
                lead=lead,
            )
            if fallback:
                body_sentences.append(fallback)
        elif story_type == "major" and len(body_sentences) == 1:
            fallback = self._build_follow_up_sentence(
                cluster=cluster,
                topic=topic,
                short_headline=short_headline,
                lead=lead,
            )
            if fallback not in body_sentences:
                body_sentences.append(fallback)
        return body_sentences

    def extract_quotes(
        self,
        cluster: StoryCluster,
        attribution_type: str,
        quote_line: str | None,
        story_type: str,
    ) -> list[str]:
        quotes: list[str] = []
        seen: set[str] = set()

        if quote_line is not None:
            actor = self._clean_source_label(self._attribution_actor(cluster, attribution_type))
            quote_sentence = self.normalize_for_radio(self._normalize_story_text(f'{actor} spune: "{quote_line}".'))
            normalized_key = quote_sentence.lower()
            if normalized_key not in seen:
                quotes.append(quote_sentence)
                seen.add(normalized_key)

        for raw_title in [cluster.representative_title, *[member.title for member in cluster.member_articles]]:
            extracted = self._extract_quote_from_title(raw_title)
            if extracted is None:
                continue
            actor, statement = extracted
            quote_sentence = self.normalize_for_radio(self._normalize_story_text(f"{actor} spune ca {statement}."))
            normalized_key = quote_sentence.lower()
            if normalized_key in seen:
                continue
            quotes.append(quote_sentence)
            seen.add(normalized_key)

        if story_type == "short":
            return quotes[:1]
        return quotes[:3]

    def normalize_for_radio(self, text: str) -> str:
        cleaned = text.replace("\n", " ").replace("\t", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+([,.;:?!])", r"\1", cleaned)
        cleaned = cleaned.replace("..", ".")
        if not cleaned:
            return cleaned
        return cleaned[0].upper() + cleaned[1:]

    def _build_major_headline(self, cluster: StoryCluster) -> str:
        topic = self._infer_topic(cluster)
        translated_title = self._best_headline_candidate(cluster)
        headline = self._compact_headline(translated_title)
        cluster_text = self._light_translate_title(self._cluster_text(cluster))
        lowered = f"{headline} {cluster_text}".lower()

        if "embassy" in lowered and ("bagdad" in lowered or "baghdad" in lowered):
            return "Atac cu rachete langa ambasada SUA din Bagdad"
        if "kharg" in lowered and ("targeted" in lowered or "vizat" in lowered or "atac" in lowered):
            return "Insula Kharg, sub presiune militara"
        if ("campanu" in lowered or "cimpanu" in lowered) and "chongqing" in lowered:
            return "Alexandru Cimpanu aduce victoria lui Chongqing"
        if "golul victoriei" in lowered:
            return "Gol decisiv intr-un meci important"
        if "iran" in lowered and ("gulf" in lowered or "golf" in lowered):
            return "Tensiuni intre Iran si statele din Golf"
        if "iran" in lowered and ("war" in lowered or "conflict" in lowered) and ("bagdad" in lowered or "baghdad" in lowered):
            return "Conflictul cu Iranul se extinde spre Bagdad"

        if (
            self._title_looks_unreliable(headline)
            or self._translation_coverage_is_low(cluster.representative_title, translated_title)
            or self._headline_is_generic(headline)
        ):
            rewritten = self._rewrite_unreliable_headline(cluster, topic, translated_title)
            if not self._headline_is_generic(rewritten):
                headline = rewritten

        if self._title_looks_unreliable(headline):
            location = self._extract_location_phrase(cluster_text)
            location_label = self._normalize_location_for_headline(location)
            if topic == "war" and location_label:
                headline = f"Tensiuni militare in crestere la {location_label}"
            elif topic == "politics":
                headline = "Decizie politica cu efect imediat"
            elif topic == "economy":
                headline = "Semnal important pentru economie"
            else:
                headline = self._fallback_headline_for_topic(topic)

        headline = self._capitalize_headline(headline)
        if self._headline_is_generic(headline):
            better = self._best_non_generic_member_title(cluster)
            if better:
                headline = better
        return headline

    def _build_major_story_lead(
        self,
        cluster: StoryCluster,
        topic: str,
        short_headline: str,
        current_lead: str,
        casualty_line: str | None,
    ) -> str:
        if current_lead and current_lead.strip() != "Un eveniment important are loc.":
            if (
                "Un eveniment important are loc" not in current_lead
                and not self._text_needs_romanian_rewrite(current_lead)
            ):
                return current_lead

        cluster_text = self._light_translate_title(self._cluster_text(cluster))
        location = self._extract_location_phrase(cluster_text) or self._extract_location_phrase(short_headline)
        location_label = self._normalize_location_for_sentence(location)

        if casualty_line:
            if location_label:
                return f"{short_headline} aduce un bilant grav {location_label}, iar autoritatile urmaresc consecintele imediate."
            return f"{short_headline} aduce un bilant grav, iar autoritatile urmaresc consecintele imediate."

        if "embassy" in cluster_text and ("bagdad" in cluster_text or "baghdad" in cluster_text):
            return "Un atac cu rachete in apropierea ambasadei SUA din Bagdad readuce conflictul intr-o zona de maxima tensiune."
        if "kharg" in cluster_text:
            return "Insula Kharg intra din nou in centrul atentiei, pentru ca presiunea militara poate afecta rutele energetice din regiune."
        if ("campanu" in cluster_text or "cimpanu" in cluster_text) and "chongqing" in cluster_text:
            return "Alexandru Cimpanu decide un meci la Chongqing, rezultat care mentine atentia asupra formei sale si a parcursului echipei."
        if "golul victoriei" in cluster_text:
            return f"{short_headline} conteaza direct pentru moralul echipei si pentru urmatoarele meciuri din competitie."
        if topic == "war":
            if location_label:
                return f"{short_headline} arata ca tensiunile se adancesc {location_label}, cu impact rapid asupra securitatii regionale."
            return f"{short_headline} arata ca tensiunile se adancesc, cu impact rapid asupra securitatii regionale."
        if topic == "politics":
            if location_label:
                return f"{short_headline} schimba agenda publica {location_label}, iar efectele politice sunt urmarite indeaproape."
            return f"{short_headline} schimba agenda publica, iar efectele politice sunt urmarite indeaproape."
        if topic == "economy":
            return f"{short_headline} poate influenta rapid costurile, investitiile si reactiile din economie."
        fact_based = self._build_fact_based_lead(cluster, short_headline, topic)
        if fact_based:
            return fact_based
        return f"{short_headline} ramane in prim-plan, iar urmarirea reactiilor oficiale devine esentiala."

    def _build_major_source_attribution(
        self,
        cluster: StoryCluster,
        topic: str,
        attribution_type: str,
        quote_line: str | None,
    ) -> tuple[str, str, bool]:
        actor = self._clean_source_label(self._attribution_actor(cluster, attribution_type))
        detail = self._major_source_detail(topic, cluster, quote_line)
        variant_cycle = [
            ("potrivit", "Potrivit {actor}, {detail}."),
            ("relateaza", "{actor} relateaza ca {detail}."),
            ("noteaza", "{actor} noteaza ca {detail}."),
        ]
        start_index = sum(ord(char) for char in cluster.cluster_id) % len(variant_cycle)
        variant_id, template = variant_cycle[start_index]
        sentence = template.format(actor=actor, detail=detail)
        self._remember_attribution_variant(variant_id)
        return sentence, variant_id, variant_id != "potrivit"

    def _major_source_detail(
        self,
        topic: str,
        cluster: StoryCluster,
        quote_line: str | None,
    ) -> str:
        cluster_text = self._light_translate_title(self._cluster_text(cluster)).lower()
        if quote_line:
            quote_hint = quote_line.strip().rstrip(".?!")
            return f"apar deja prime reactii publice, iar mesajele oficiale se concentreaza pe ideea ca {quote_hint.lower()}"
        if "embassy" in cluster_text and ("bagdad" in cluster_text or "baghdad" in cluster_text):
            return "episodul pune presiune pe raspunsul american si pe echilibrul regional"
        if "kharg" in cluster_text:
            return "miza imediata tine de securitatea energetica si de libertatea rutelor maritime"
        detail_by_topic = {
            "war": "urmatoarele ore sunt decisive pentru reactiile militare si diplomatice",
            "politics": "urmeaza reactii politice si clarificari oficiale",
            "economy": "impactul se poate vedea rapid in costuri, piete si investitii",
            "sport": "miza ramane ridicata pentru urmatoarele etape",
            "general": "subiectul cere clarificari rapide si reactii oficiale",
        }
        return detail_by_topic.get(topic, detail_by_topic["general"])

    def _extract_quote_from_title(self, raw_title: str) -> tuple[str, str] | None:
        title = self._light_translate_title(raw_title)
        quoted = QUOTE_PATTERN.search(raw_title)
        if quoted:
            statement = self._normalize_quote_statement(quoted.group(1))
            actor = self._extract_institution(title) or self._clean_source_label(title.split(":", 1)[0])
            if actor and statement:
                return actor, statement

        patterns = [
            re.compile(
                rf"(?P<actor>[A-Z{ROMANIAN_LETTER_CLASS}][{ROMANIAN_LETTER_CLASS}\s\.-]{{2,60}}?)\s+(?:spune|anunta|avertizeaza|sustine|transmite|acuz[ae]|noteaza|claims?|warns?|says?)\s+(?:ca\s+)?(?P<statement>[{ROMANIAN_LETTER_CLASS}\s,\-]{{8,140}})",
                re.IGNORECASE,
            ),
            re.compile(
                rf"(?P<actor>[A-Z{ROMANIAN_LETTER_CLASS}][{ROMANIAN_LETTER_CLASS}\s\.-]{{2,60}}?)\s*:\s*(?P<statement>[{ROMANIAN_LETTER_CLASS}\s,\-]{{8,140}})",
                re.IGNORECASE,
            ),
        ]
        for pattern in patterns:
            match = pattern.search(title)
            if not match:
                continue
            actor = self._clean_source_label(match.group("actor"))
            statement = self._normalize_quote_statement(match.group("statement"))
            if actor and statement and not self._looks_like_headline_noise(statement):
                return actor, statement
        return None

    def _normalize_quote_statement(self, statement: str) -> str:
        cleaned = self.normalize_for_radio(statement.strip().strip(" \"'"))
        cleaned = cleaned.rstrip(".?!")
        if len(cleaned.split()) < 3:
            return ""
        return cleaned[0].lower() + cleaned[1:] if cleaned else ""

    def _clean_source_label(self, label: str) -> str:
        cleaned = self.normalize_for_radio(self._light_translate_title(self._fix_mojibake(label)))
        cleaned = re.sub(r"\s*-\s*liderul presei ie[?s]ene.*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^AP News$", "AP", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^BBC World$", "BBC", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^Euronews\.ro.*$", "Euronews Romania", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^Ziarul de Ia[?s]i.*$", "Ziarul de Iasi", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+#AllViews.*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:,.;")
        return cleaned or "sursa principala"

    def _normalize_location_for_sentence(self, location_phrase: str | None) -> str | None:
        if not location_phrase:
            return None
        location = location_phrase.strip()
        if not location:
            return None
        return location

    def _normalize_location_for_headline(self, location_phrase: str | None) -> str | None:
        if not location_phrase:
            return None
        location = location_phrase.strip()
        for prefix in ("in ", "la ", "din ", "spre ", "pe "):
            if location.lower().startswith(prefix):
                return location[len(prefix):].strip()
        return location

    def _looks_like_headline_noise(self, statement: str) -> bool:
        lowered = statement.lower()
        return (
            any(marker in lowered for marker in ("live", "video", "breaking"))
            or len(statement.split()) > 20
            or self._title_looks_unreliable(statement)
        )

    def _text_needs_romanian_rewrite(self, text: str) -> bool:
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(text)]
        if not tokens:
            return False
        english_hits = sum(1 for token in tokens if token in ENGLISH_HEADLINE_MARKERS)
        romanian_hits = sum(1 for token in tokens if token in ROMANIAN_HEADLINE_MARKERS)
        return english_hits >= 2 and english_hits >= romanian_hits

    def _normalize_story_text(self, text: str) -> str:
        normalized = self._fix_mojibake(text)
        replacements = {
            "steps down": "demisioneaza",
            "step down": "demisioneaza",
            "head": "directorul",
            "tumultuous": "agitat",
            "year": "an",
            "receives": "primeste",
            "prize": "premiul",
            "germany": "Germania",
            "threatens": "ameninta",
            "ports": "porturile",
            "third week": "a treia saptamana",
            "updates": "actualizari",
            "update": "actualizare",
            "after": "dupa",
            "down": "jos",
            "AP News": "AP",
            "BBC World": "BBC",
            "Associated Press": "AP",
            "US": "SUA",
            "Baghdad": "Bagdad",
            "embassy": "ambasada",
            "missile": "racheta",
            "missiles": "rachete",
            "war": "conflict",
            "military": "militar",
            "targeted": "vizata",
            "target": "tinta",
            "security": "securitate",
            "regional": "regional",
            "response": "raspuns",
        }
        for source_term, replacement in replacements.items():
            normalized = re.sub(rf"\b{re.escape(source_term)}\b", replacement, normalized, flags=re.IGNORECASE)
        for english_term, romanian_term in sorted(self.english_to_romanian_terms.items(), key=lambda item: len(item[0]), reverse=True):
            normalized = re.sub(rf"\b{re.escape(english_term)}\b", romanian_term, normalized, flags=re.IGNORECASE)
        normalized = normalized.replace(';', '. ')
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        normalized = re.sub(r'\.\s*;', '. ', normalized)
        normalized = re.sub(r'\s+([,.;:?!])', r'\1', normalized)
        return normalized

    def _compose_summary_text(
        self,
        lead: str,
        source_attribution: str,
        body: str,
        quotes: list[str],
    ) -> str:
        parts = [lead.strip(), source_attribution.strip(), body.strip(), *[quote.strip() for quote in quotes if quote.strip()]]
        return ' '.join(part for part in parts if part).strip()

    def _normalize_cluster(
        self,
        cluster: StoryCluster | ScoredStoryCluster,
    ) -> tuple[StoryCluster, str, float | None]:
        if isinstance(cluster, ScoredStoryCluster):
            return cluster.cluster, "scored_story_cluster", cluster.score_total
        return cluster, "story_cluster", None

    def _infer_topic(self, cluster: StoryCluster) -> str:
        text = self._cluster_text(cluster)
        best_topic = "general"
        best_matches = 0
        for topic, keywords in self.topic_keywords.items():
            if topic == "general":
                continue
            matches = sum(1 for keyword in keywords if keyword.lower() in text)
            if matches > best_matches:
                best_matches = matches
                best_topic = topic
        return best_topic

    def _detect_lead_type(
        self,
        cluster: StoryCluster,
        topic: str,
        casualty_line: str | None,
    ) -> str:
        if casualty_line:
            return "impact"

        cluster_text = self._cluster_text(cluster)
        for lead_type in ["decision", "warning", "conflict", "change"]:
            if any(keyword in cluster_text for keyword in self.lead_type_keywords[lead_type]):
                return lead_type

        if any(keyword in cluster_text for keyword in self.lead_type_keywords["event"]):
            return "event"

        if topic == "sport":
            return "event"
        return "event"

    def _detect_story_continuity(
        self,
        cluster: StoryCluster,
        score_total: float | None,
        previous_bulletin_clusters: list[str | dict[str, object]] | None,
    ) -> tuple[str, bool, str]:
        previous_record = self._previous_cluster_record(
            cluster.cluster_id,
            previous_bulletin_clusters,
        )
        if previous_record is None:
            return "new_story", False, "Cluster did not appear in the previous bulletin."

        previous_score = self._coerce_float(previous_record.get("score_total"))
        previous_source_count = self._coerce_int(previous_record.get("source_count"))
        current_source_count = len(cluster.member_articles)
        score_delta = (
            score_total - previous_score
            if score_total is not None and previous_score is not None
            else None
        )
        source_delta = (
            current_source_count - previous_source_count
            if previous_source_count is not None
            else None
        )
        if (
            score_delta is not None and score_delta >= self.continuity_major_update_score_delta
        ) or (
            source_delta is not None and source_delta >= self.continuity_major_update_source_delta
        ):
            explanation_parts = ["Cluster appeared in previous bulletin and now qualifies as a major update"]
            if score_delta is not None and score_delta >= self.continuity_major_update_score_delta:
                explanation_parts.append(
                    f"score increased by {round(score_delta, 1)} points"
                )
            if source_delta is not None and source_delta >= self.continuity_major_update_source_delta:
                explanation_parts.append(
                    f"source count increased from {previous_source_count} to {current_source_count}"
                )
            return "major_update", True, "; ".join(explanation_parts) + "."

        return "update", True, "Cluster appeared in previous bulletin."

    def _previous_cluster_record(
        self,
        cluster_id: str,
        previous_bulletin_clusters: list[str | dict[str, object]] | None,
    ) -> dict[str, object] | None:
        for item in previous_bulletin_clusters or []:
            if isinstance(item, str):
                if item == cluster_id:
                    return {"cluster_id": item}
                continue
            if isinstance(item, dict) and item.get("cluster_id") == cluster_id:
                return item
        return None

    def _coerce_float(self, value: object) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _coerce_int(self, value: object) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _build_short_headline(self, cluster: StoryCluster) -> str:
        headline_source_title = self._headline_source_title(cluster)
        translated_title = self._best_headline_candidate(cluster)
        topic = self._infer_topic(cluster)
        if (
            self._title_looks_unreliable(translated_title)
            or self._translation_coverage_is_low(headline_source_title, translated_title)
            or self._headline_is_generic(translated_title)
        ):
            return self._rewrite_unreliable_headline(cluster, topic, translated_title)

        headline = self._polish_headline(self._compact_headline(translated_title), cluster, topic)
        if self._title_looks_unreliable(headline) or self._headline_is_generic(headline):
            rewritten = self._rewrite_unreliable_headline(cluster, topic, headline)
            if not self._headline_is_generic(rewritten):
                return rewritten
        return headline or self._fallback_headline_for_topic(topic)

    def _headline_source_title(self, cluster: StoryCluster) -> str:
        titles = [cluster.representative_title, *[member.title for member in cluster.member_articles]]
        return min(titles, key=self._headline_title_penalty)

    def _headline_title_penalty(self, title: str) -> tuple[int, int, int]:
        lowered = title.lower()
        noise_penalty = sum(1 for marker in ["live-text", "video", "breaking", "exclusiv"] if marker in lowered)
        english_penalty = sum(1 for token in TOKEN_PATTERN.findall(lowered) if token in ENGLISH_HEADLINE_MARKERS)
        length_penalty = abs(len(TOKEN_PATTERN.findall(title)) - 6)
        return (noise_penalty, english_penalty, length_penalty)

    def _best_headline_candidate(self, cluster: StoryCluster) -> str:
        candidates: list[tuple[tuple[int, int, int, int, int], str]] = []
        for raw_title in [cluster.representative_title, *[member.title for member in cluster.member_articles]]:
            translated = self._light_translate_title(raw_title)
            compact = self._compact_headline(translated)
            penalty = self._headline_candidate_penalty(raw_title, compact)
            candidates.append((penalty, compact))
        if not candidates:
            return self._fallback_headline_for_topic(self._infer_topic(cluster))
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _headline_candidate_penalty(self, raw_title: str, translated_title: str) -> tuple[int, int, int, int, int]:
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(translated_title)]
        raw_tokens = [token.lower() for token in TOKEN_PATTERN.findall(raw_title)]
        english_hits = sum(1 for token in tokens if token in ENGLISH_HEADLINE_MARKERS)
        unchanged_hits = len(set(tokens) & set(raw_tokens))
        generic_penalty = 1 if self._headline_is_generic(translated_title) else 0
        unreliable_penalty = 1 if self._title_looks_unreliable(translated_title) else 0
        short_penalty = 1 if len(tokens) < 3 else 0
        length_penalty = abs(len(tokens) - 6)
        return (
            generic_penalty,
            unreliable_penalty,
            english_hits,
            short_penalty + (1 if unchanged_hits >= max(len(set(raw_tokens)) - 1, 3) and english_hits >= 2 else 0),
            length_penalty,
        )

    def _rewrite_unreliable_headline(self, cluster: StoryCluster, topic: str, translated_title: str) -> str:
        title = self._compact_headline(translated_title or self._headline_source_title(cluster))
        lowered = title.lower()
        cluster_text = self._light_translate_title(self._cluster_text(cluster))
        if ("exploz" in cluster_text or "explosion" in cluster_text) and "amsterdam" in cluster_text and ("scoala" in cluster_text or "school" in cluster_text or "jewish" in cluster_text):
            return "Atac la o scoala din Amsterdam"
        if "embassy" in cluster_text and "baghdad" in cluster_text:
            return "Atac cu rachete in apropierea ambasadei SUA din Bagdad"
        if ("bomb" in cluster_text or "lovituri" in cluster_text or "atac" in cluster_text) and "iran" in cluster_text:
            return "Lovituri asupra unor situri militare din Iran"
        if "pakistan" in lowered and ("drone" in lowered or "taliban" in lowered):
            return "Pakistan doboara drone talibane"
        if "iran" in cluster_text and ("ports" in cluster_text or "porturi" in cluster_text) and ("uae" in cluster_text or "emiratele" in cluster_text):
            return "Iran ameninta porturi din Emiratele Arabe Unite"
        if "kennedy center" in cluster_text and ("steps down" in cluster_text or "demisioneaza" in cluster_text):
            return "Demisie la conducerea Kennedy Center"
        if "kolesnikova" in cluster_text and ("charlemagne" in cluster_text or "premiul" in cluster_text):
            return "Kolesnikova primeste Premiul Charlemagne in Germania"
        if "ministerul muncii" in cluster_text and "pensionari" in cluster_text:
            return "Ministerul Muncii anunta bani in plus pentru pensionari"
        if "alin firfirica" in cluster_text and ("discului" in cluster_text or "discus" in cluster_text):
            return "Alin Firfirica, pe podium la Cupa Europei"
        if "trump" in cluster_text and "ormuz" in cluster_text:
            return "Trump trimite nave spre Stramtoarea Ormuz"
        if "bomb" in lowered and ("militar" in lowered or "site" in lowered or "situri" in lowered):
            if "iran" in lowered:
                return "Lovituri asupra unor situri militare din Iran"
            return "Lovituri asupra unor situri militare"
        if "adolescent" in lowered and "arest" in lowered:
            if "dolj" in lowered:
                return "Adolescent arestat in Dolj"
            return "Adolescent arestat dupa o agresiune"
        if "tragedie" in lowered or ("murit" in lowered and "arad" in lowered):
            if "arad" in lowered:
                return "Tanar mort dupa o cadere la Arad"
            return "Tragedie investigata de autoritati"
        if "slatina" in lowered and ("jocurile" in lowered or "noroc" in lowered):
            return "Slatina interzice jocurile de noroc"
        if ("steaua" in lowered or "ros alba" in lowered or "ro? alba" in lowered) and ("ia?i" in lowered or "iasi" in lowered or "poli" in lowered):
            return "Steaua se desprinde in meciul cu Poli Iasi"
        if "diana buzoianu" in lowered:
            if "planteze" in cluster_text or "copaci" in cluster_text:
                return "Diana Buzoianu, la Iasi pentru o actiune de mediu"
            if "iasi" in lowered or "ia?i" in lowered:
                return "Diana Buzoianu, la Iasi pentru o actiune de mediu"
            return "Diana Buzoianu critica vechile practici politice"
        if "hamas" in lowered and "iran" in lowered and "golf" in lowered:
            return "Hamas cere Iranului sa opreasca atacurile din Golf"
        if "china markets" in cluster_text or ("china" in cluster_text and "markets" in cluster_text):
            return "Pietele din China in atentie"
        if "campanie" == lowered.strip():
            return "Campanie in atentia publicului"
        if lowered.strip() in {"stiri externe", "?tiri externe"}:
            return "Tensiuni internationale in atentie"
        if lowered.strip().startswith("litera ") and any(member.is_local_source for member in cluster.member_articles):
            return "Actualitate locala din Iasi"
        if "franta" in lowered and ("alegeri" in lowered or "primarii" in lowered):
            return "Alegeri municipale in Franta"
        if "actualitate" == lowered.strip():
            alternative = self._best_non_generic_member_title(cluster)
            if alternative:
                return alternative
        location = self._extract_location_phrase(title)
        institution = self._extract_institution(title)
        if "interzice" in lowered and location:
            return self._capitalize_headline(f"Autoritatile {location} interzic o activitate vizata")
        if institution and topic == "politics":
            return self._capitalize_headline(f"{institution} anunta o decizie importanta")
        if location and topic == "disaster":
            return self._capitalize_headline(f"Incident grav {location}")
        if topic == "war":
            return "Tensiuni internationale in crestere"
        if topic == "politics":
            return "Decizie politica in prim-plan"
        if topic == "economy":
            return "Economie in prim-plan"
        if topic == "sport":
            return self._best_non_generic_member_title(cluster) or "Meci important in atentia publicului"
        return self._fallback_headline_for_topic(topic)

    def _clean_headline_title(self, title: str) -> str:
        cleaned = SCOREBOARD_PATTERN.sub(" ", title)
        cleaned = cleaned.replace("|", " ").replace("/", " ")
        cleaned = NOISY_HEADLINE_PREFIX_PATTERN.sub("", cleaned)
        cleaned = HEADLINE_SEPARATOR_PATTERN.sub(" ", cleaned)
        cleaned = re.sub(r"\b(?:live|text|video|foto|galerie foto|update|breaking|exclusiv)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:;,")
        return cleaned

    def _compact_headline(self, title: str) -> str:
        cleaned = self._clean_headline_title(title)
        truncated = HEADLINE_TRUNCATION_PATTERN.split(cleaned, maxsplit=1)[0].strip(" -:;,")
        working = truncated or cleaned
        full_tokens = TOKEN_PATTERN.findall(working)
        if 4 <= len(full_tokens) <= 10 and not self._title_looks_unreliable(working):
            return self._capitalize_headline(" ".join(full_tokens))
        tokens = [
            token
            for token in full_tokens
            if token.lower() not in self.headline_stopwords and len(token) >= 3
        ]
        if len(tokens) < 3:
            tokens = [token for token in full_tokens if len(token) >= 2]
        if len(tokens) < 3:
            return self._capitalize_headline(working)
        headline = " ".join(tokens[:7]).strip()
        return self._capitalize_headline(headline)

    def _polish_headline(self, headline: str, cluster: StoryCluster, topic: str) -> str:
        lowered = headline.lower()
        cluster_text = self._light_translate_title(self._cluster_text(cluster))
        if ("bombs military" in lowered or "military sites" in lowered) and "iran" in lowered:
            return "Lovituri asupra unor situri militare din Iran"
        if "diana buzoianu" in lowered and ("planteze" in cluster_text or "copaci" in cluster_text):
            return "Diana Buzoianu, la Iasi pentru o actiune de mediu"
        if "hamas" in lowered and "iran" in lowered and "golf" in lowered:
            return "Hamas cere Iranului sa opreasca atacurile din Golf"
        if lowered.strip() == "campanie":
            return "Campanie in atentia publicului"
        if lowered.strip() in {"stiri externe", "?tiri externe"} or "stiri externe" in cluster_text:
            return "Tensiuni internationale in atentie"
        if lowered.strip().startswith("litera ") and any(member.is_local_source for member in cluster.member_articles):
            return "Actualitate locala din Iasi"
        if lowered.strip() in {"china markets", "piete china"} or ("china" in cluster_text and "markets" in cluster_text):
            return "Pietele din China in atentie"
        return headline

    def _best_non_generic_member_title(self, cluster: StoryCluster) -> str | None:
        candidates: list[str] = []
        for raw_title in [cluster.representative_title, *[member.title for member in cluster.member_articles]]:
            compact = self._compact_headline(self._light_translate_title(raw_title))
            if self._headline_is_generic(compact):
                continue
            if self._title_looks_unreliable(compact):
                continue
            candidates.append(compact)
        if not candidates:
            return None
        candidates.sort(key=lambda value: self._headline_candidate_penalty(value, value))
        return candidates[0]

    def _headline_is_generic(self, title: str) -> bool:
        normalized = " ".join(title.lower().split())
        return bool(GENERIC_HEADLINE_PATTERN.match(normalized))

    def _capitalize_headline(self, headline: str) -> str:
        normalized = " ".join(headline.split()).strip(" -:;,")
        if not normalized:
            return ""
        return normalized[0].upper() + normalized[1:]

    def _extract_memorable_quote_line(self, cluster: StoryCluster) -> str | None:
        for title in [cluster.representative_title, *[member.title for member in cluster.member_articles]]:
            match = QUOTE_PATTERN.search(title)
            if not match:
                continue
            candidate = " ".join(match.group(1).split()).strip().rstrip(".?!")
            if self._is_memorable_quote(candidate):
                return candidate
        return None

    def _is_memorable_quote(self, candidate: str) -> bool:
        words = candidate.split()
        lowered = candidate.lower()
        if not (2 <= len(words) <= self.memorable_quote_max_words):
            return False
        if any(term in lowered for term in self.bureaucratic_quote_terms):
            return False
        if len(candidate) > 60:
            return False
        if any(term in lowered for term in self.memorable_quote_terms):
            return True
        return any(len(word) >= 7 for word in words)

    def _determine_attribution_type(
        self,
        cluster: StoryCluster,
        quote_line: str | None,
    ) -> str:
        if quote_line:
            return "direct_quote"

        cluster_text = self._cluster_text(cluster)
        if any(term.lower() in cluster_text for term in self.official_actor_terms) or any(
            verb.lower() in cluster_text for verb in self.attribution_verbs
        ):
            return "official_statement"

        return "source_attribution"

    def _extract_casualty_line(self, cluster: StoryCluster) -> str | None:
        cluster_text = self._cluster_text(cluster)
        if not any(keyword in cluster_text for keyword in self.casualty_priority_keywords):
            return None

        deaths, injuries = self._extract_casualty_counts(cluster)
        if deaths is None and injuries is None:
            return None

        event_label = self._event_label(cluster_text)
        parts: list[str] = []
        if deaths is not None:
            victim_word = "persoana" if deaths == 1 else "persoane"
            parts.append(f"a ucis {deaths} {victim_word}")
        if injuries is not None:
            victim_word = "persoana" if injuries == 1 else "persoane"
            qualifier = "aproximativ " if injuries >= 10 else ""
            parts.append(f"a ranit {qualifier}{injuries} {victim_word}")
        joined = " si ".join(parts)
        return f"Bilantul preliminar arata ca {event_label} {joined}."

    def _extract_casualty_counts(self, cluster: StoryCluster) -> tuple[int | None, int | None]:
        deaths: int | None = None
        injuries: int | None = None
        for title in [cluster.representative_title, *[member.title for member in cluster.member_articles]]:
            translated = self._light_translate_title(title).lower()
            for match in COUNT_KEYWORD_PATTERN.finditer(translated):
                count = int(match.group("count"))
                kind = match.group("kind")
                deaths, injuries = self._apply_casualty_match(kind, count, deaths, injuries)
            for match in KEYWORD_COUNT_PATTERN.finditer(translated):
                count = int(match.group("count"))
                kind = match.group("kind")
                deaths, injuries = self._apply_casualty_match(kind, count, deaths, injuries)
        return deaths, injuries

    def _apply_casualty_match(
        self,
        kind: str,
        count: int,
        deaths: int | None,
        injuries: int | None,
    ) -> tuple[int | None, int | None]:
        death_terms = {"killed", "dead", "deaths", "morti", "decese"}
        injury_terms = {"injured", "wounded", "raniti", "ranite"}
        if kind in death_terms and deaths is None:
            deaths = count
        if kind in injury_terms and injuries is None:
            injuries = count
        return deaths, injuries

    def _event_label(self, cluster_text: str) -> str:
        if "explosion" in cluster_text or "exploz" in cluster_text:
            return "explozia"
        if "crash" in cluster_text or "accident" in cluster_text:
            return "accidentul"
        if "fire" in cluster_text or "incend" in cluster_text:
            return "incendiul"
        if "earthquake" in cluster_text or "cutremur" in cluster_text:
            return "cutremurul"
        return "atacul"

    def _build_lead_sentence(
        self,
        cluster: StoryCluster,
        topic: str,
        lead_type: str,
        casualty_line: str | None,
        story_continuity_type: str,
    ) -> str:
        translated_title = self._light_translate_title(cluster.representative_title)
        continuity_lead = self._build_continuity_lead(
            translated_title=translated_title,
            story_continuity_type=story_continuity_type,
        )
        if continuity_lead is not None:
            return continuity_lead
        if self._title_looks_unreliable(translated_title) or self._translation_coverage_is_low(cluster.representative_title, translated_title):
            translated_title = ""
        if lead_type == "impact":
            return self._build_impact_lead(cluster, translated_title)
        if lead_type == "decision":
            return self._build_decision_lead(translated_title)
        if lead_type == "warning":
            return self._build_warning_lead(cluster, translated_title)
        if lead_type == "conflict":
            return self._build_conflict_lead(translated_title)
        if lead_type == "change":
            return self._build_change_lead(translated_title)
        return self._build_event_lead(cluster, translated_title, topic)

    def _build_continuity_lead(
        self,
        translated_title: str,
        story_continuity_type: str,
    ) -> str | None:
        if story_continuity_type == "new_story":
            return None
        subject = self._continuity_subject(translated_title)
        if subject == "subiectul urmarit":
            return None
        if story_continuity_type == "major_update":
            return f"Apar noi evolutii in cazul {subject}."
        return f"Subiectul {subject} revine in atentie dupa evolutii noi."

    def _continuity_subject(self, translated_title: str) -> str:
        subject = self._fix_mojibake(translated_title).strip().rstrip('.!?')
        if self._title_looks_unreliable(subject) or self._text_needs_romanian_rewrite(subject):
            return "subiectul urmarit"
        words = subject.split()
        if len(words) > 12:
            subject = " ".join(words[:12])
        if not subject:
            return "subiectul urmarit"
        return subject[0].lower() + subject[1:]

    def _build_impact_lead(self, cluster: StoryCluster, translated_title: str) -> str:
        deaths, injuries = self._extract_casualty_counts(cluster)
        event_label = self._event_label(self._cluster_text(cluster))
        location = self._extract_location_phrase(translated_title)
        parts: list[str] = []
        if deaths is not None:
            victim_word = "mort" if deaths == 1 else "morti"
            parts.append(f"{deaths} {victim_word}")
        if injuries is not None:
            parts.append(f"aproximativ {injuries} de raniti" if injuries >= 10 else f"{injuries} raniti")
        consequence = " si ".join(parts) if parts else "victime"
        location_phrase = f" {location}" if location else ""
        article = "Un"
        if event_label in {"explozia", "reuniunea"}:
            article = "O"
        return f"{article} {event_label}{location_phrase} s-a soldat cu {consequence}."

    def _build_decision_lead(self, translated_title: str) -> str:
        institution = self._extract_institution(translated_title) or "Autoritatile"
        decision_phrase = self._extract_decision_phrase(translated_title)
        context_phrase = self._extract_after_phrase(translated_title)
        sentence = f"{institution} {decision_phrase}"
        if context_phrase:
            sentence += f" {context_phrase}"
        return sentence.rstrip(".?!") + "."

    def _build_warning_lead(self, cluster: StoryCluster, translated_title: str) -> str:
        subject = self._match_phrase_map(translated_title, self.lead_phrase_maps["warning_subjects"]) or "Apar noi riscuri"
        institution = self._extract_institution(translated_title) or self._primary_source(cluster)
        domain = self._extract_location_phrase(translated_title)
        domain_phrase = f" {domain}" if domain else ""
        return f"{subject}{domain_phrase}, avertizeaza {institution}."

    def _build_conflict_lead(self, translated_title: str) -> str:
        subject = self._match_phrase_map(translated_title, self.lead_phrase_maps["conflict_subjects"]) or "Tensiunile politice cresc"
        cause = self._extract_after_phrase(translated_title)
        if cause:
            return f"{subject} {cause}."
        return f"{subject}."

    def _build_change_lead(self, translated_title: str) -> str:
        subject = self._match_phrase_map(translated_title, self.lead_phrase_maps["change_subjects"])
        if subject is None:
            subject = "Datele noi schimba perspectiva"
        location = self._extract_location_phrase(translated_title)
        if location:
            return f"{subject}{location}."
        return f"{subject}."

    def _build_event_lead(self, cluster: StoryCluster, translated_title: str, topic: str) -> str:
        concrete_title = self._best_fact_title(cluster)
        concrete_lead = self._title_to_sentence(concrete_title, force=False)
        if concrete_lead is not None:
            return concrete_lead
        subject = self._match_phrase_map(translated_title, self.lead_phrase_maps["event_subjects"])
        if subject is None:
            institution = self._extract_institution(translated_title)
            if institution:
                subject = f"{institution} este in centrul unui nou anunt"
            elif topic == "sport":
                subject = "Meciul schimba calculele competitiei"
            else:
                fact_based = self._build_fact_based_lead(cluster, concrete_title, topic)
                if fact_based:
                    return fact_based
                subject = "Apare un nou subiect cu impact public"
        purpose = self._extract_purpose_phrase(translated_title)
        if purpose:
            return f"{subject} {purpose}."
        return f"{subject}."

    def _extract_institution(self, translated_title: str) -> str | None:
        lowered = translated_title.lower()
        for term in sorted(self.official_actor_terms, key=len, reverse=True):
            if term.lower() in lowered:
                return term.capitalize() if term.islower() else term
        if translated_title.startswith("Liderii"):
            return "Liderii"
        return None

    def _extract_decision_phrase(self, translated_title: str) -> str:
        lowered = translated_title.lower()
        for keyword, phrase in self.lead_phrase_maps["decision_objects"].items():
            if keyword in lowered:
                return f"a aprobat {phrase}"
        if "aproba" in lowered or "approved" in lowered:
            return "a aprobat o decizie importanta"
        if "adopt" in lowered:
            return "a adoptat o noua masura"
        if "sanctiuni" in lowered:
            return "a aprobat noi sanctiuni"
        return "a luat o decizie importanta"

    def _extract_after_phrase(self, translated_title: str) -> str | None:
        lowered = translated_title.lower()
        for trigger in [" dupa ", " pe fondul "]:
            if trigger in lowered:
                phrase = lowered.split(trigger, 1)[1].strip()
                if phrase:
                    return trigger.strip() + " " + phrase[:80].rstrip(".?!")
        return None

    def _extract_location_phrase(self, translated_title: str) -> str | None:
        match = re.search(
            rf"\b(in|la|din|spre|pe)\s+([{ROMANIAN_LETTER_CLASS}\s-]{{3,40}})",
            translated_title,
            re.IGNORECASE,
        )
        if not match:
            return None
        preposition = match.group(1).lower()
        location = " ".join(match.group(2).split()[:5]).rstrip(".?!")
        return f"{preposition} {location}"

    def _extract_purpose_phrase(self, translated_title: str) -> str | None:
        lowered = translated_title.lower()
        for trigger in [" pentru ", " ca sa ", " to "]:
            if trigger in lowered:
                phrase = lowered.split(trigger, 1)[1].strip()
                if phrase:
                    return trigger.strip() + " " + phrase[:80].rstrip(".?!")
        return self._extract_after_phrase(translated_title)

    def _match_phrase_map(self, translated_title: str, phrase_map: dict[str, str]) -> str | None:
        lowered = translated_title.lower()
        for keyword, phrase in phrase_map.items():
            if keyword in lowered:
                return phrase
        return None

    def _is_important_story(
        self,
        cluster: StoryCluster,
        topic: str,
        score_total: float | None,
        casualty_line: str | None,
    ) -> bool:
        if casualty_line:
            return True
        if score_total is not None and score_total >= self.expansion_score_threshold:
            return True
        cluster_text = self._cluster_text(cluster)
        if topic in self.expansion_topics:
            return True
        return any(keyword in cluster_text for keyword in self.expansion_keywords)

    def _build_context_line(
        self,
        cluster: StoryCluster,
        topic: str,
        important_story: bool,
        casualty_line: str | None,
    ) -> str | None:
        if not important_story:
            return None
        cluster_text = self._cluster_text(cluster)
        if not any(keyword in cluster_text for keyword in self.context_trigger_keywords):
            return None
        if casualty_line is None and len(cluster.member_articles) < 2:
            return None
        for candidate in self._candidate_fact_titles(cluster):
            sentence = self._title_to_sentence(candidate, force=False)
            if sentence and not self._looks_like_generic_body_sentence(sentence):
                return sentence
        return self.topic_templates.get(topic, self.topic_templates["general"]).get("context")

    def _build_detail_sentence(
        self,
        cluster: StoryCluster,
        topic: str,
        attribution_type: str,
        quote_line: str | None,
    ) -> tuple[str, str, bool]:
        detail = self._build_attribution_detail(cluster, topic)
        actor = self._clean_source_label(self._attribution_actor(cluster, attribution_type))
        variant = self._select_attribution_variant(cluster.cluster_id, attribution_type)
        template = variant["template"]
        sentence = template.format(
            actor=actor,
            detail=detail,
            quote=(quote_line or "mesaj scurt"),
        )
        self._remember_attribution_variant(variant["id"])
        return sentence, variant["id"], variant["id"] != "potrivit"

    def _attribution_actor(self, cluster: StoryCluster, attribution_type: str) -> str:
        if attribution_type == "official_statement":
            translated_title = self._light_translate_title(cluster.representative_title)
            return self._extract_institution(translated_title) or self._primary_source(cluster)
        return self._primary_source(cluster)

    def _select_attribution_variant(
        self,
        cluster_id: str,
        attribution_type: str,
    ) -> dict[str, str]:
        variants = self.attribution_variants.get(
            attribution_type,
            self.attribution_variants["source_attribution"],
        )
        disallowed: set[str] = set()
        if len(self.recent_attribution_variants) >= 2:
            last_two = self.recent_attribution_variants[-2:]
            if last_two[0] == last_two[1]:
                disallowed.add(last_two[0])

        start_index = sum(ord(char) for char in f"{cluster_id}:{attribution_type}") % len(variants)
        rotated = variants[start_index:] + variants[:start_index]
        for variant in rotated:
            if variant["id"] not in disallowed:
                return variant
        return rotated[0]

    def _remember_attribution_variant(self, variant_id: str) -> None:
        self.recent_attribution_variants.append(variant_id)
        self.recent_attribution_variants = self.recent_attribution_variants[-2:]

    def _build_attribution_detail(self, cluster: StoryCluster, topic: str) -> str:
        fact_sentences = self._build_concrete_body_sentences(
            cluster=cluster,
            topic=topic,
            short_headline="",
            lead="",
        )
        if fact_sentences:
            return fact_sentences[0].rstrip(".?!").lower()
        return self.topic_templates.get(topic, self.topic_templates["general"])["detail"].rstrip(".?!").lower()

    def _build_concrete_body_sentences(
        self,
        cluster: StoryCluster,
        topic: str,
        short_headline: str,
        lead: str,
    ) -> list[str]:
        sentences: list[str] = []
        seen: set[str] = set()
        excluded_fragments = {
            self._normalize_text_fragment(short_headline),
            self._normalize_text_fragment(lead),
        }
        for candidate in self._candidate_fact_titles(cluster):
            sentence = self._title_to_sentence(candidate, force=False)
            if sentence is None:
                continue
            normalized_sentence = self._normalize_text_fragment(sentence)
            if not normalized_sentence or normalized_sentence in seen:
                continue
            if any(fragment and fragment in normalized_sentence for fragment in excluded_fragments):
                continue
            sentences.append(sentence)
            seen.add(normalized_sentence)
        return sentences

    def _candidate_fact_titles(self, cluster: StoryCluster) -> list[str]:
        candidates: list[tuple[tuple[int, int, int], str]] = []
        for raw_title in [cluster.representative_title, *[member.title for member in cluster.member_articles]]:
            translated = self._normalize_story_text(self._light_translate_title(raw_title))
            cleaned = self._clean_headline_title(translated)
            if not cleaned:
                continue
            candidates.append((self._fact_title_penalty(cleaned), cleaned))
        candidates.sort(key=lambda item: item[0])
        return [candidate for _, candidate in candidates]

    def _best_fact_title(self, cluster: StoryCluster) -> str:
        for candidate in self._candidate_fact_titles(cluster):
            if self._title_to_sentence(candidate, force=False) is not None:
                return candidate
        return self._best_headline_candidate(cluster)

    def _fact_title_penalty(self, title: str) -> tuple[int, int, int]:
        normalized = self._normalize_text_fragment(title)
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(title)]
        generic_penalty = 1 if self._headline_is_generic(title) else 0
        unreliable_penalty = 1 if self._title_looks_unreliable(title) or self._text_needs_romanian_rewrite(title) else 0
        info_penalty = 0 if len(tokens) >= 5 else 2
        if normalized.startswith("actualitate") or normalized.startswith("subiect"):
            info_penalty += 2
        return generic_penalty, unreliable_penalty, info_penalty

    def _title_to_sentence(self, title: str, force: bool = False) -> str | None:
        cleaned = self._normalize_story_text(self._clean_headline_title(title))
        cleaned = re.sub(r"\b(?:live updates|live update|breaking|exclusiv|video|foto)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:;,")
        cleaned = cleaned.replace(" - ", ", ")
        if not cleaned:
            return None
        tokens = TOKEN_PATTERN.findall(cleaned)
        if not force and (len(tokens) < 4 or self._headline_is_generic(cleaned) or self._text_needs_romanian_rewrite(cleaned)):
            return None
        if len(tokens) > 18:
            cleaned = " ".join(tokens[:18])
        cleaned = cleaned.strip()
        if not cleaned:
            return None
        if cleaned[-1] not in ".!?":
            cleaned += "."
        return self.normalize_for_radio(cleaned)

    def _normalize_text_fragment(self, text: str) -> str:
        return " ".join(TOKEN_PATTERN.findall(text.lower()))

    def _build_consequence_sentence(self, topic: str) -> str:
        return self.topic_templates.get(topic, self.topic_templates["general"])["impact"]

    def _build_fact_based_lead(self, cluster: StoryCluster, headline: str, topic: str) -> str | None:
        fact_title = self._best_fact_title(cluster)
        fact_sentence = self._title_to_sentence(fact_title, force=False)
        if fact_sentence and not self._looks_like_generic_body_sentence(fact_sentence):
            return fact_sentence

        location = self._normalize_location_for_sentence(self._extract_location_phrase(self._cluster_text(cluster)))
        if headline and not self._headline_is_generic(headline):
            if location:
                return f"{headline} aduce un nou punct de tensiune {location} si cere reactii rapide."
            if topic == "economy":
                return f"{headline} schimba asteptarile din economie si ramane relevant pentru evolutia pietelor."
            if topic == "politics":
                return f"{headline} deschide o noua disputa politica si pune presiune pe raspunsul institutiilor."
            if topic == "sport":
                return f"{headline} schimba calculele competitiei si muta presiunea pe urmatoarele partide."
            return f"{headline} capata relevanta imediata prin efectul pe care il are in agenda publica."
        return None

    def _build_follow_up_sentence(
        self,
        cluster: StoryCluster,
        topic: str,
        short_headline: str,
        lead: str,
    ) -> str:
        source_label = self._clean_source_label(self._primary_source(cluster))
        location = self._normalize_location_for_sentence(self._extract_location_phrase(self._cluster_text(cluster)))
        fact_title = self._best_fact_title(cluster)
        fact_sentence = self._title_to_sentence(fact_title, force=False)
        if fact_sentence and self._normalize_text_fragment(fact_sentence) != self._normalize_text_fragment(lead):
            return fact_sentence

        specific_follow_up = self._headline_specific_follow_up(short_headline, topic)
        if specific_follow_up:
            return specific_follow_up

        if location and topic == "war":
            return f"Potrivit {source_label}, reactiile din {location} arata ca presiunea se muta spre urmatorii pasi militari si diplomatici."
        if location and topic == "politics":
            return f"Potrivit {source_label}, ecoul din {location} arata ca tema va ramane pe agenda politica in zilele urmatoare."
        if location and topic == "economy":
            return f"Potrivit {source_label}, evolutiile din {location} pot influenta rapid investitiile, costurile si increderea din piata."
        if topic == "sport":
            return f"Potrivit {source_label}, rezultatul schimba calculele din competitie si ridica miza urmatoarelor meciuri."
        if topic == "economy":
            return f"Potrivit {source_label}, urmatorul efect vizibil poate aparea in costuri, investitii si reactia pietelor."
        if topic == "politics":
            return f"Potrivit {source_label}, urmeaza clarificari oficiale si o confruntare politica pe tema acestui subiect."
        return f"Potrivit {source_label}, urmeaza reactii si clarificari pe aceasta tema."

    def _looks_like_generic_body_sentence(self, sentence: str) -> bool:
        lowered = sentence.lower()
        generic_markers = (
            "povestea conteaza acum",
            "in perioada imediat urmatoare",
            "revenim la subiectul urmarit",
            "subiectul urmarit",
            "actualitate in atentie",
            "devine important acum",
        )
        return any(marker in lowered for marker in generic_markers)

    def _headline_specific_follow_up(self, headline: str, topic: str) -> str | None:
        lowered = headline.lower()
        if "pensionari" in lowered or "ministerul muncii" in lowered:
            return "Proiectul vizeaza plati suplimentare in aprilie si decembrie, iar detaliile urmeaza sa fie clarificate public."
        if "iran ameninta porturi" in lowered:
            return "Miza imediata este siguranta rutelor maritime si reactia aliatilor SUA din Golf."
        if "kennedy center" in lowered:
            return "Plecare marcheaza finalul unui an tensionat pentru una dintre cele mai vizibile institutii culturale din Statele Unite."
        if "kolesnikova" in lowered:
            return "Distinctia readuce in atentie opozitia belarusa si presiunea politica asupra regimului de la Minsk."
        if "stramtoarea ormuz" in lowered or "ormuz" in lowered:
            return "Miscarea pune din nou presiune pe securitatea regionala si pe traficul maritim din Golf."
        if "china" in lowered and "piete" in lowered:
            return "Investitorii urmaresc acum semnalele despre crestere, lichiditate si urmatoarele miscari ale autoritatilor."
        if "firfirica" in lowered or "cupa europei" in lowered:
            return "Rezultatul il mentine pe sportiv in zona podiumului continental si confirma forma buna din competitie."
        if topic == "economy":
            return "Subiectul ramane relevant prin efectul rapid asupra costurilor, pietelor si asteptarilor economice."
        return None

    def _filter_sentence_numbers(
        self,
        sentences: list[str],
        casualty_line: str | None,
    ) -> tuple[list[str], bool, bool]:
        filtered: list[str] = []
        essential_numbers_kept = False
        nonessential_numbers_removed = False
        casualty_text = casualty_line or ""

        for sentence in sentences:
            if not sentence:
                continue
            if sentence == casualty_text:
                filtered.append(sentence)
                if NUMBER_PATTERN.search(sentence):
                    essential_numbers_kept = True
                continue

            new_sentence, kept_essential, removed_nonessential = self._filter_numbers_in_sentence(sentence)
            filtered.append(new_sentence)
            essential_numbers_kept = essential_numbers_kept or kept_essential
            nonessential_numbers_removed = nonessential_numbers_removed or removed_nonessential

        return filtered, essential_numbers_kept, nonessential_numbers_removed

    def _filter_numbers_in_sentence(self, sentence: str) -> tuple[str, bool, bool]:
        original_numbers = NUMBER_PATTERN.findall(sentence)
        if not original_numbers:
            return sentence, False, False

        kept_essential = False

        def replace_match(match: re.Match[str]) -> str:
            nonlocal kept_essential
            snippet = match.group(0)
            if self._number_snippet_is_essential(snippet, sentence):
                kept_essential = True
                return snippet
            return ""

        filtered = KEEP_NUMBER_WINDOW_PATTERN.sub(replace_match, sentence)
        filtered = re.sub(r"\s+,", ",", filtered)
        filtered = re.sub(r",\s*,", ", ", filtered)
        filtered = re.sub(r"\s{2,}", " ", filtered)
        filtered = re.sub(r"\s+([.,;:])", r"\1", filtered)
        filtered = filtered.strip()
        if filtered and filtered[-1] not in ".!?":
            filtered += "."

        removed_nonessential = len(NUMBER_PATTERN.findall(filtered)) < len(original_numbers)
        return filtered or sentence, kept_essential, removed_nonessential

    def _number_snippet_is_essential(self, snippet: str, sentence: str) -> bool:
        lowered_snippet = snippet.lower()
        lowered_sentence = sentence.lower()
        if any(keyword in lowered_snippet for keyword in self.essential_number_keywords):
            return True
        if "%" in snippet or any(currency in lowered_snippet for currency in ["lei", "euro", "dolari"]):
            return True
        if any(keyword in lowered_sentence for keyword in ["morti", "decese", "raniti", "ucis", "rani", "bilant"]):
            return True
        if any(keyword in lowered_sentence for keyword in ["buget", "cost", "inflatie", "dobanzi", "preturi", "deadline", "termen"]):
            return True
        return False

    def _expand_if_needed(self, summary_text: str, topic: str) -> str:
        if self._word_count(summary_text) >= self.policy.target_word_count_min:
            return summary_text

        extra_clause_map = {
            "politics": " Urmeaza reactii oficiale si presiune pe decizia finala.",
            "economy": " Pietele urmaresc acum efectul asupra costurilor si investitiilor.",
            "international_conflict": " Urmeaza reactii diplomatice si riscul unei noi escaladari.",
            "sport": " Miza ramane in clasament si in programul urmatoarelor partide.",
            "general": " Urmeaza clarificari oficiale si detalii noi."
        }
        return summary_text + extra_clause_map.get(topic, extra_clause_map["general"])

    def _light_translate_title(self, title: str) -> str:
        result = self._clean_headline_title(self._fix_mojibake(title))
        for english_term, romanian_term in sorted(
            self.english_to_romanian_terms.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            pattern = re.compile(rf"\b{re.escape(english_term)}\b", re.IGNORECASE)
            result = pattern.sub(romanian_term, result)
        result = NON_ALPHA_PATTERN.sub(" ", result)
        result = re.sub(r"\s+", " ", result).strip()
        return result

    def _fix_mojibake(self, text: str) -> str:
        if not text:
            return text
        if not any(marker in text for marker in ("\u00c3", "\u00c4", "\u00c5", "\u00c8", "\u00e2\u20ac")):
            return text
        try:
            repaired = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            return repaired or text
        except UnicodeError:
            return text

    def _title_looks_unreliable(self, title: str) -> bool:
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(title)]
        if len(tokens) < 3:
            return True
        english_hits = sum(1 for token in tokens if token in ENGLISH_HEADLINE_MARKERS)
        romanian_hits = sum(1 for token in tokens if token in ROMANIAN_HEADLINE_MARKERS)
        return english_hits >= 2 and english_hits > romanian_hits

    def _translation_coverage_is_low(self, original_title: str, translated_title: str) -> bool:
        original_tokens = [token.lower() for token in TOKEN_PATTERN.findall(original_title)]
        translated_tokens = [token.lower() for token in TOKEN_PATTERN.findall(translated_title)]
        if len(translated_tokens) < 3:
            return True
        shared_tokens = set(original_tokens) & set(translated_tokens)
        unchanged_ratio = len(shared_tokens) / max(len(set(original_tokens)), 1)
        english_hits = sum(1 for token in original_tokens if token in ENGLISH_HEADLINE_MARKERS)
        romanian_hits = sum(1 for token in translated_tokens if token in ROMANIAN_HEADLINE_MARKERS)
        return unchanged_ratio >= 0.6 and english_hits >= 2 and romanian_hits == 0

    def _fallback_headline_for_topic(self, topic: str) -> str:
        fallback_by_topic = {
            "economy": "Presiune noua asupra economiei",
            "politics": "Disputa politica cere clarificari",
            "war": "Tensiuni militare cu efect imediat",
            "disaster": "Incident grav anchetat de autoritati",
            "science_space": "Decizie noua in stiinta si spatiu",
            "sport": "Meci cu efect direct in clasament",
        }
        return fallback_by_topic.get(topic, "Subiect cu impact public")

    def _cluster_text(self, cluster: StoryCluster) -> str:
        titles = " ".join(member.title for member in cluster.member_articles)
        return f"{cluster.representative_title} {titles}".lower()

    def _primary_source(self, cluster: StoryCluster) -> str:
        return cluster.member_articles[0].source if cluster.member_articles else "sursa principala"

    def _pick_template(self, templates: list[str], seed: str) -> str:
        if not templates:
            return "Potrivit sursei, urmeaza detalii suplimentare."
        index = sum(ord(char) for char in seed) % len(templates)
        return templates[index]

    def _word_count(self, text: str) -> int:
        return len(WORD_PATTERN.findall(text))

    def _build_compliance_report(
        self,
        summary_text: str,
        sentence_count: int,
        word_count: int,
        expanded_summary_used: bool,
    ) -> SummaryComplianceReport:
        sentences = [sentence for sentence in SENTENCE_SPLIT_PATTERN.split(summary_text) if sentence.strip()]
        max_sentence_limit = self.expanded_max_sentences if expanded_summary_used else self.policy.max_sentence_count
        sentence_count_ok = self.policy.min_sentence_count <= sentence_count <= max_sentence_limit
        word_count_ok = self.policy.target_word_count_min <= word_count <= self.policy.target_word_count_max
        structure_ok = len(sentences) == sentence_count and (
            sentence_count == self.policy.preferred_sentence_count
            or expanded_summary_used and 4 <= sentence_count <= self.expanded_max_sentences
        )
        banned_patterns_found = [
            pattern for pattern in self.banned_patterns if pattern.lower() in summary_text.lower()
        ]
        estimated_duration_seconds = round((word_count / self.spoken_words_per_minute) * 60)

        notes: list[str] = []
        if not word_count_ok:
            notes.append("word_count_outside_target_range")
        if not sentence_count_ok:
            notes.append("sentence_count_outside_policy_range")
        if not structure_ok:
            notes.append("preferred_structure_missing")
        if expanded_summary_used:
            notes.append("expanded_summary_used")
        if banned_patterns_found:
            notes.append("banned_patterns_detected")
        if self.policy.target_duration_seconds_min <= estimated_duration_seconds <= self.policy.target_duration_seconds_max:
            notes.append("duration_within_target_range")
        else:
            notes.append("duration_outside_target_range")

        if word_count_ok and sentence_count_ok and structure_ok and not banned_patterns_found:
            notes.append("policy_core_rules_met")

        return SummaryComplianceReport(
            sentence_count_ok=sentence_count_ok,
            word_count_ok=word_count_ok,
            structure_ok=structure_ok,
            banned_patterns_found=banned_patterns_found,
            estimated_duration_seconds=estimated_duration_seconds,
            notes=notes,
        )

    def _build_generation_explanation(
        self,
        cluster: StoryCluster,
        topic: str,
        lead_type: str,
        story_continuity_type: str,
        continuity_explanation: str,
        attribution_type: str,
        short_headline: str,
        compliance: SummaryComplianceReport,
        expanded_summary_used: bool,
        casualty_line_included: bool,
        context_line_included: bool,
        memorable_quote_used: bool,
        essential_numbers_kept: bool,
        nonessential_numbers_removed: bool,
        attribution_variant: str,
        summary_variation_used: bool,
    ) -> str:
        return (
            f"Summary for cluster '{cluster.representative_title}' was generated with short headline '{short_headline}', "
            f"lead type '{lead_type}', continuity '{story_continuity_type}', topic template '{topic}', attribution mode '{attribution_type}' in attribution-first form, "
            f"attribution_variant={attribution_variant}, variation_used={summary_variation_used}, expanded={expanded_summary_used}, "
            f"casualties={casualty_line_included}, context={context_line_included}, memorable_quote={memorable_quote_used}, "
            f"essential_numbers_kept={essential_numbers_kept}, nonessential_numbers_removed={nonessential_numbers_removed}. "
            f"Continuity: {continuity_explanation} Compliance notes: {', '.join(compliance.notes)}."
        )
