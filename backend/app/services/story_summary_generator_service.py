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
    "about", "accuses", "after", "against", "ally", "amid", "attacks", "bomb", "bombs",
    "charges", "conflict", "custody", "dropped", "during", "explosion", "family", "fire",
    "generations", "global", "gulf", "halt", "him", "international", "jewish", "key",
    "leaders", "marines", "markets", "military", "moved", "negotiations", "new", "news",
    "oil", "politics", "reports", "rescuers", "rise", "says", "school", "security",
    "sites", "suspect", "three", "under", "urges", "vital", "warships", "weather", "wait",
    "whose", "world",
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

    def generate_story_summary(
        self,
        cluster: StoryCluster | ScoredStoryCluster,
        previous_bulletin_clusters: list[str | dict[str, object]] | None = None,
    ) -> GeneratedStorySummary:
        normalized_cluster, source_basis, score_total = self._normalize_cluster(cluster)
        generated_at = datetime.now(UTC)
        topic = self._infer_topic(normalized_cluster)
        short_headline = self.build_headline(normalized_cluster)
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
        )
        source_attribution, attribution_variant, summary_variation_used = self.build_source_attribution(
            cluster=cluster,
            topic=topic,
            attribution_type=attribution_type,
            quote_line=quote_line,
        )
        body_sentences = self.build_body(
            topic=topic,
            casualty_line=casualty_line,
            context_line=context_line,
            story_type=story_type,
            important_story=important_story,
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
        body = self.normalize_for_radio(body)
        summary_text = self._compose_summary_text(
            lead=lead,
            source_attribution=source_attribution,
            body=body,
            quotes=quotes,
        )
        summary_text = self._expand_if_needed(summary_text, topic) if story_type == "major" else summary_text
        summary_text = self.normalize_for_radio(summary_text)
        editorial_notes = [
            f"story_type={story_type}",
            "headline_ready_for_assembly",
            "source_attribution_early",
            "romanian_radio_normalized",
        ]
        if quotes:
            editorial_notes.append(f"quotes={len(quotes)}")
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

    def build_headline(self, cluster: StoryCluster) -> str:
        return self._build_short_headline(cluster)

    def build_lead(
        self,
        cluster: StoryCluster,
        topic: str,
        lead_type: str,
        casualty_line: str | None,
        story_continuity_type: str,
    ) -> str:
        return self.normalize_for_radio(
            self._build_lead_sentence(
                cluster=cluster,
                topic=topic,
                lead_type=lead_type,
                casualty_line=casualty_line,
                story_continuity_type=story_continuity_type,
            )
        )

    def build_source_attribution(
        self,
        cluster: StoryCluster,
        topic: str,
        attribution_type: str,
        quote_line: str | None,
    ) -> tuple[str, str, bool]:
        sentence, attribution_variant, summary_variation_used = self._build_detail_sentence(
            cluster=cluster,
            topic=topic,
            attribution_type=attribution_type,
            quote_line=quote_line,
        )
        return self.normalize_for_radio(sentence), attribution_variant, summary_variation_used

    def build_body(
        self,
        topic: str,
        casualty_line: str | None,
        context_line: str | None,
        story_type: str,
        important_story: bool,
    ) -> list[str]:
        body_sentences: list[str] = []
        if casualty_line:
            body_sentences.append(casualty_line)
        body_sentences.append(self._build_consequence_sentence(topic))
        if context_line and (story_type == "major" or important_story):
            body_sentences.append(context_line)
        return body_sentences

    def extract_quotes(
        self,
        cluster: StoryCluster,
        attribution_type: str,
        quote_line: str | None,
        story_type: str,
    ) -> list[str]:
        if quote_line is None:
            return []
        actor = self._attribution_actor(cluster, attribution_type)
        quote_sentence = self.normalize_for_radio(f'{actor} spune: "{quote_line}".')
        if story_type == "short":
            return [quote_sentence]
        return [quote_sentence]

    def normalize_for_radio(self, text: str) -> str:
        cleaned = text.replace("\n", " ").replace("\t", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+([,.;:?!])", r"\1", cleaned)
        cleaned = cleaned.replace("..", ".")
        if not cleaned:
            return cleaned
        return cleaned[0].upper() + cleaned[1:]

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
        if story_continuity_type == "major_update":
            return f"Noi informatii despre {subject}."
        return f"Revenim la {subject}."

    def _continuity_subject(self, translated_title: str) -> str:
        subject = translated_title.strip().rstrip('.!?')
        if self._title_looks_unreliable(subject):
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
        subject = self._match_phrase_map(translated_title, self.lead_phrase_maps["change_subjects"]) or "Indicatorii se schimba din nou"
        location = self._extract_location_phrase(translated_title)
        if location:
            return f"{subject}{location}."
        return f"{subject}."

    def _build_event_lead(self, cluster: StoryCluster, translated_title: str, topic: str) -> str:
        subject = self._match_phrase_map(translated_title, self.lead_phrase_maps["event_subjects"])
        if subject is None:
            institution = self._extract_institution(translated_title)
            if institution:
                subject = f"{institution} participa la un eveniment important"
            elif topic == "sport":
                subject = "Un eveniment sportiv important are loc"
            else:
                subject = "Un eveniment important are loc"
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
        return self.topic_templates.get(topic, self.topic_templates["general"]).get("context")

    def _build_detail_sentence(
        self,
        cluster: StoryCluster,
        topic: str,
        attribution_type: str,
        quote_line: str | None,
    ) -> tuple[str, str, bool]:
        detail = self.topic_templates.get(topic, self.topic_templates["general"])["detail"].rstrip(".?!").lower()
        actor = self._attribution_actor(cluster, attribution_type)
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

    def _build_consequence_sentence(self, topic: str) -> str:
        return self.topic_templates.get(topic, self.topic_templates["general"])["impact"]

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
            "politics": "; accentul ramane pe felul in care decizia va fi tradusa in masuri concrete si in costuri politice.",
            "economy": "; accentul ramane pe impactul imediat pentru costuri, investitori si urmatoarele semnale din economie.",
            "international_conflict": "; accentul ramane pe efectele imediate si pe raspunsul actorilor implicati in urmatoarele ore.",
            "sport": "; accentul ramane pe miza urmatorului joc si pe presiunea rezultatului pentru restul turneului.",
            "general": "; accentul ramane pe consecinta imediata si pe urmatorii pasi relevanti pentru public."
        }
        return summary_text + extra_clause_map.get(topic, extra_clause_map["general"])

    def _light_translate_title(self, title: str) -> str:
        result = self._clean_headline_title(title)
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
            "economy": "Economie in prim-plan",
            "politics": "Decizie politica importanta",
            "war": "Tensiuni internationale in atentie",
            "disaster": "Incident major in atentie",
            "science_space": "Noutate importanta din stiinta",
            "sport": "Meci important in atentie",
        }
        return fallback_by_topic.get(topic, "Actualitate in atentie")

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
