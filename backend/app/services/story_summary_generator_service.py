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
NON_ALPHA_PATTERN = re.compile(r'[^A-Za-z0-9\s\-"]')
QUOTE_PATTERN = re.compile(r'["](.{3,120}?)["]')
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9-]+")
NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?%?\b")
KEEP_NUMBER_WINDOW_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?%?\b(?:\s+(?:de|la|din|pana|pentru|in|pe|aproximativ))?(?:\s+[A-Za-z%-]+){0,3}",
    re.UNICODE,
)
COUNT_KEYWORD_PATTERN = re.compile(
    r"(?P<count>\d+)\s+(?P<kind>killed|dead|deaths|morti|decese|injured|wounded|raniti|ranite)"
)
KEYWORD_COUNT_PATTERN = re.compile(
    r"(?P<kind>killed|dead|deaths|morti|decese|injured|wounded|raniti|ranite)\s+(?P<count>\d+)"
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

    def generate_story_summary(
        self,
        cluster: StoryCluster | ScoredStoryCluster,
    ) -> GeneratedStorySummary:
        normalized_cluster, source_basis, score_total = self._normalize_cluster(cluster)
        generated_at = datetime.now(UTC)
        topic = self._infer_topic(normalized_cluster)
        short_headline = self._build_short_headline(normalized_cluster)
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
        context_line = self._build_context_line(
            cluster=normalized_cluster,
            topic=topic,
            important_story=importance_triggered,
            casualty_line=casualty_line,
        )

        lead_sentence = self._build_lead_sentence(
            cluster=normalized_cluster,
            topic=topic,
            lead_type=lead_type,
            casualty_line=casualty_line,
        )
        detail_sentence = self._build_detail_sentence(
            cluster=normalized_cluster,
            topic=topic,
            attribution_type=attribution_type,
            quote_line=quote_line,
        )
        consequence_sentence = self._build_consequence_sentence(topic)

        sentences = [lead_sentence, detail_sentence]
        if casualty_line and lead_type != "impact":
            sentences.append(casualty_line)
        if importance_triggered and (casualty_line or context_line):
            sentences.append(consequence_sentence)
            if context_line and (
                casualty_line or score_total is not None and score_total >= self.expansion_score_threshold
            ):
                sentences.append(context_line)
        else:
            sentences.append(consequence_sentence)

        filtered_sentences, essential_numbers_kept, nonessential_numbers_removed = self._filter_sentence_numbers(
            sentences,
            casualty_line=casualty_line,
        )
        summary_text = " ".join(sentence for sentence in filtered_sentences if sentence).strip()
        summary_text = self._expand_if_needed(summary_text, topic)
        sentence_count = len(
            [sentence for sentence in SENTENCE_SPLIT_PATTERN.split(summary_text) if sentence.strip()]
        )
        word_count = self._word_count(summary_text)
        expanded_summary_used = sentence_count > self.policy.preferred_sentence_count
        casualty_line_included = casualty_line is not None
        context_line_included = context_line is not None and sentence_count >= 5
        memorable_quote_used = quote_line is not None and attribution_type == "direct_quote"
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
            attribution_type=attribution_type,
            short_headline=short_headline,
            compliance=compliance,
            expanded_summary_used=expanded_summary_used,
            casualty_line_included=casualty_line_included,
            context_line_included=context_line_included,
            memorable_quote_used=memorable_quote_used,
            essential_numbers_kept=essential_numbers_kept,
            nonessential_numbers_removed=nonessential_numbers_removed,
        )

        return GeneratedStorySummary(
            cluster_id=normalized_cluster.cluster_id,
            short_headline=short_headline,
            lead_type=lead_type,
            summary_text=summary_text,
            sentence_count=sentence_count,
            word_count=word_count,
            topic_label=topic,
            source_labels=sorted({member.source for member in normalized_cluster.member_articles}),
            attribution_type=attribution_type,
            quote_line=quote_line,
            memorable_quote_used=memorable_quote_used,
            essential_numbers_kept=essential_numbers_kept,
            nonessential_numbers_removed=nonessential_numbers_removed,
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

    def _build_short_headline(self, cluster: StoryCluster) -> str:
        translated_title = self._light_translate_title(cluster.representative_title)
        tokens = [
            token
            for token in TOKEN_PATTERN.findall(translated_title)
            if token.lower() not in self.headline_stopwords and len(token) >= 3
        ]
        if len(tokens) < 3:
            tokens = TOKEN_PATTERN.findall(translated_title)

        selected = tokens[:6]
        if len(selected) < 3:
            fallback_tokens = [
                token for token in TOKEN_PATTERN.findall(translated_title) if len(token) >= 2
            ]
            selected = fallback_tokens[:3] or ["Subiect", "important", "acum"]

        headline = " ".join(selected[:6]).strip()
        words = headline.split()
        if len(words) > 6:
            words = words[:6]
        if len(words) < 3:
            words = (words + ["acum", "in", "atentie"])[:3]
        headline = " ".join(words)
        return headline[0].upper() + headline[1:] if headline else "Subiect important acum"

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
    ) -> str:
        translated_title = self._light_translate_title(cluster.representative_title)
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
        match = re.search(r"\b(in|la|din|spre|pe)\s+([A-Za-z0-9\s-]{3,40})", translated_title, re.IGNORECASE)
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
    ) -> str:
        detail = self.topic_templates.get(topic, self.topic_templates["general"])["detail"].rstrip(".?!")
        source = self._primary_source(cluster)

        if attribution_type == "direct_quote" and quote_line:
            return f'Potrivit {source}, mesajul-cheie este simplu: "{quote_line}", iar {detail.lower()}.'

        if attribution_type == "official_statement":
            attribution = self._pick_template(
                self.official_attribution_templates,
                cluster.cluster_id,
            ).rstrip(".?!")
            return f"{attribution}, iar {detail.lower()}."

        attribution = self._pick_template(
            self.source_attribution_templates,
            source,
        ).format(source=source).rstrip(".?!")
        return f"{attribution}, iar {detail.lower()}."

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
        result = title
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
        attribution_type: str,
        short_headline: str,
        compliance: SummaryComplianceReport,
        expanded_summary_used: bool,
        casualty_line_included: bool,
        context_line_included: bool,
        memorable_quote_used: bool,
        essential_numbers_kept: bool,
        nonessential_numbers_removed: bool,
    ) -> str:
        return (
            f"Summary for cluster '{cluster.representative_title}' was generated with short headline '{short_headline}', "
            f"lead type '{lead_type}', topic template '{topic}', attribution mode '{attribution_type}' in attribution-first form, "
            f"expanded={expanded_summary_used}, casualties={casualty_line_included}, context={context_line_included}, "
            f"memorable_quote={memorable_quote_used}, essential_numbers_kept={essential_numbers_kept}, "
            f"nonessential_numbers_removed={nonessential_numbers_removed}. "
            f"Compliance notes: {', '.join(compliance.notes)}."
        )
