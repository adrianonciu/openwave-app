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
NON_ALPHA_PATTERN = re.compile(r"[^A-Za-z0-9\s-]")


class StorySummaryGeneratorService:
    def __init__(self) -> None:
        raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.policy_service = StorySummaryPolicyService()
        self.policy = self.policy_service.get_policy()
        self.spoken_words_per_minute: int = raw_config["spoken_words_per_minute"]
        self.banned_patterns: list[str] = raw_config["banned_patterns"]
        self.topic_templates: dict[str, dict[str, str]] = raw_config["topic_templates"]
        self.english_to_romanian_terms: dict[str, str] = raw_config[
            "english_to_romanian_terms"
        ]
        self.topic_keywords: dict[str, list[str]] = raw_config["topic_keywords"]

    def generate_story_summary(
        self,
        cluster: StoryCluster | ScoredStoryCluster,
    ) -> GeneratedStorySummary:
        normalized_cluster, source_basis = self._normalize_cluster(cluster)
        generated_at = datetime.now(UTC)
        topic = self._infer_topic(normalized_cluster)
        lead_sentence = self._build_lead_sentence(normalized_cluster)
        impact_sentence = self._build_impact_sentence(topic)
        detail_sentence = self._build_detail_sentence(normalized_cluster, topic)

        sentences = [lead_sentence, impact_sentence, detail_sentence]
        summary_text = " ".join(sentence for sentence in sentences if sentence).strip()
        summary_text = self._expand_if_needed(summary_text, topic)
        sentence_count = len([sentence for sentence in SENTENCE_SPLIT_PATTERN.split(summary_text) if sentence.strip()])
        word_count = self._word_count(summary_text)
        compliance = self._build_compliance_report(summary_text, sentence_count, word_count)
        explanation = self._build_generation_explanation(normalized_cluster, topic, compliance)

        return GeneratedStorySummary(
            cluster_id=normalized_cluster.cluster_id,
            summary_text=summary_text,
            sentence_count=sentence_count,
            word_count=word_count,
            policy_compliance=compliance,
            generation_explanation=explanation,
            generated_at=generated_at,
            source_basis=source_basis,
        )

    def _normalize_cluster(
        self,
        cluster: StoryCluster | ScoredStoryCluster,
    ) -> tuple[StoryCluster, str]:
        if isinstance(cluster, ScoredStoryCluster):
            return cluster.cluster, "scored_story_cluster"
        return cluster, "story_cluster"

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

    def _build_lead_sentence(self, cluster: StoryCluster) -> str:
        title = cluster.representative_title.strip()
        translated = self._light_translate_title(title)
        translated = translated[0].upper() + translated[1:] if translated else title
        translated = translated.rstrip(".?!")
        return f"{translated}."

    def _build_impact_sentence(self, topic: str) -> str:
        return self.topic_templates.get(topic, self.topic_templates["general"])["impact"]

    def _build_detail_sentence(self, cluster: StoryCluster, topic: str) -> str:
        source_count = len({member.source for member in cluster.member_articles})
        if source_count >= 2:
            return (
                f"Subiectul este urmarit de {source_count} surse, iar detaliile comune indica faptul ca urmeaza "
                f"reactii si clarificari suplimentare cu efect direct asupra evolutiilor urmatoare."
            )

        return self.topic_templates.get(topic, self.topic_templates["general"])["detail"]

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

    def _word_count(self, text: str) -> int:
        return len(WORD_PATTERN.findall(text))

    def _build_compliance_report(
        self,
        summary_text: str,
        sentence_count: int,
        word_count: int,
    ) -> SummaryComplianceReport:
        sentences = [sentence for sentence in SENTENCE_SPLIT_PATTERN.split(summary_text) if sentence.strip()]
        sentence_count_ok = self.policy.min_sentence_count <= sentence_count <= self.policy.max_sentence_count
        word_count_ok = self.policy.target_word_count_min <= word_count <= self.policy.target_word_count_max
        structure_ok = len(sentences) == sentence_count and sentence_count == self.policy.preferred_sentence_count
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
            notes.append("preferred_three_sentence_structure_missing")
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
        compliance: SummaryComplianceReport,
    ) -> str:
        return (
            f"Summary for cluster '{cluster.representative_title}' was generated from the representative title "
            f"with topic template '{topic}'. Compliance notes: {', '.join(compliance.notes)}."
        )

