from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re

from app.models.editorial_contract_validation import (
    BulletinValidationResult,
    EditorialContractAutoFix,
    EditorialContractViolation,
    StoryValidationResult,
)
from app.models.final_editorial_briefing import FinalEditorialBriefingPackage
from app.models.generated_briefing_draft import BriefingStoryItem
from app.models.user_personalization import UserPersonalization
from app.services.source_watcher_service import SourceWatcherService

DEBUG_REPORT_PATH = Path(__file__).resolve().parents[2] / "debug_output" / "editorial_validation_report.json"
PRESENTER_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "audio_presenter_config.json"
TOKEN_PATTERN = re.compile(r"[0-9A-Za-z\u00C0-\u024F-]+", re.UNICODE)
QUOTE_PATTERN = re.compile(r'["�](.+?)["�]')
NOISY_HEADLINE_PATTERN = re.compile(
    r"^(?:(?:live|live-text|video|breaking|update|actualizare|exclusiv|seo)\b[\s:/-]*)+",
    re.IGNORECASE,
)
SEO_FRAGMENT_PATTERN = re.compile(r"\b(click aici|vezi aici|tot ce trebuie sa stii|ultimele detalii|live update)\b", re.IGNORECASE)
ENGLISH_MARKERS = {
    "about", "accuses", "after", "against", "ally", "amid", "attacks", "bomb", "bombs",
    "charges", "conflict", "custody", "dropped", "during", "embassy", "enters", "explosion",
    "family", "fire", "generations", "global", "gulf", "halt", "hits", "international",
    "jewish", "key", "leaders", "marines", "markets", "military", "moved", "negotiations",
    "new", "news", "oil", "politics", "reports", "rescuers", "rise", "says", "school",
    "security", "sites", "suspect", "three", "under", "urges", "vital", "war", "warships",
    "weather", "wait", "whose", "world",
}
ROMANIAN_MARKERS = {
    "acum", "atac", "autoritati", "buget", "conform", "declarat", "dupa", "guvern", "iasi",
    "important", "masura", "politica", "potrivit", "romania", "scrie", "securitate", "spune",
    "stiri", "transmite", "urmeaza", "ziarul",
}
GENERIC_HEADLINES = {
    "subiect important acum",
    "actualitate in atentie",
    "noutate importanta din stiinta",
    "stire importanta",
}
POST_ATTRIBUTION_PATTERN = re.compile(
    r"^(?P<statement>[^.]{10,180}?),\s+a declarat\s+(?P<speaker>[^.]+)$",
    re.IGNORECASE,
)
ATTRIBUTION_PREFIXES = ("potrivit ", "conform ", "scrie ", "spune ", "transmite ", "afirma ", "arata ca ")


class EditorialContractValidationService:
    def __init__(self) -> None:
        presenter_config = json.loads(PRESENTER_CONFIG_PATH.read_text(encoding="utf-8"))
        self.presenter_mode: str = presenter_config.get("presenter_mode", "single")
        self.source_watcher_service = SourceWatcherService()

    def validate_bulletin(
        self,
        briefing: FinalEditorialBriefingPackage,
    ) -> tuple[FinalEditorialBriefingPackage, BulletinValidationResult]:
        data = self._dump_model(briefing)
        story_items_data = [self._dump_model(item) for item in briefing.story_items]
        story_results: list[StoryValidationResult] = []
        bulletin_violations: list[EditorialContractViolation] = []
        bulletin_auto_fixes: list[EditorialContractAutoFix] = []

        for index, item_data in enumerate(story_items_data):
            story_result = self.validate_story(
                item_data=item_data,
                listener_first_name=briefing.personalization.listener_profile.first_name,
            )
            story_items_data[index] = story_result[0]
            story_results.append(story_result[1])

        story_ids = [item_data["story"]["cluster_id"] for item_data in story_items_data]
        intro_violations, intro_auto_fixes = self.validate_intro(data)
        outro_violations, outro_auto_fixes = self.validate_outro(data)
        story_count_violations = self.validate_story_count(story_items_data)
        presenter_violations = self.validate_presenter_alternation(story_items_data)
        perspective_violations = self.validate_perspective_adjacency(story_items_data)
        local_anchor_violations = self.validate_local_anchor(briefing, story_items_data)
        user_name_violations = self.validate_user_name_usage(briefing.personalization, story_items_data)
        variant_violations = self.validate_intro_outro_variants(data)

        bulletin_violations.extend(intro_violations)
        bulletin_violations.extend(outro_violations)
        bulletin_violations.extend(story_count_violations)
        bulletin_violations.extend(presenter_violations)
        bulletin_violations.extend(perspective_violations)
        bulletin_violations.extend(local_anchor_violations)
        bulletin_violations.extend(user_name_violations)
        bulletin_violations.extend(variant_violations)
        bulletin_auto_fixes.extend(intro_auto_fixes)
        bulletin_auto_fixes.extend(outro_auto_fixes)

        data["story_items"] = story_items_data
        fixed_briefing = FinalEditorialBriefingPackage(**data)

        all_violations = bulletin_violations + [
            violation
            for story_result in story_results
            for violation in story_result.violations
        ]
        all_auto_fixes = bulletin_auto_fixes + [
            auto_fix
            for story_result in story_results
            for auto_fix in story_result.auto_fixes
        ]
        blocking_violation_count = sum(1 for violation in all_violations if violation.severity == "blocking")
        warning_count = sum(1 for violation in all_violations if violation.severity == "warning")

        result = BulletinValidationResult(
            passed=blocking_violation_count == 0,
            briefing_id=briefing.briefing_id,
            validated_at=datetime.now(UTC),
            blocking_violation_count=blocking_violation_count,
            warning_count=warning_count,
            auto_fix_count=len(all_auto_fixes),
            story_results=story_results,
            violations=bulletin_violations,
            auto_fixes=bulletin_auto_fixes,
            summary=self._build_summary(
                briefing_id=briefing.briefing_id,
                story_ids=story_ids,
                blocking_violation_count=blocking_violation_count,
                warning_count=warning_count,
                auto_fix_count=len(all_auto_fixes),
            ),
        )
        report_path = self._write_report(
            briefing=fixed_briefing,
            result=result,
            all_violations=all_violations,
            all_auto_fixes=all_auto_fixes,
        )
        result.report_path = str(report_path)
        return fixed_briefing, result

    def validate_story(
        self,
        item_data: dict,
        listener_first_name: str | None,
    ) -> tuple[dict, StoryValidationResult]:
        story = dict(item_data["story"])
        story_id = story["cluster_id"]
        violations: list[EditorialContractViolation] = []
        auto_fixes: list[EditorialContractAutoFix] = []

        title = str(story.get("short_headline") or "").strip()
        cleaned_title, title_auto_fixes, title_violations = self._normalize_title(title, story)
        story["short_headline"] = cleaned_title
        auto_fixes.extend([fix.model_copy(update={"story_id": story_id}) for fix in title_auto_fixes])
        violations.extend([violation.model_copy(update={"story_id": story_id}) for violation in title_violations])

        summary_text = str(story.get("summary_text") or "").strip()
        rewritten_summary, quote_auto_fixes, quote_violations = self.validate_quote_rules(
            summary_text=summary_text,
            story=story,
            story_id=story_id,
        )
        story["summary_text"] = rewritten_summary
        auto_fixes.extend(quote_auto_fixes)
        violations.extend(quote_violations)

        normalized_summary, attribution_auto_fixes, attribution_violations = self.validate_source_attribution(
            summary_text=story["summary_text"],
            source_labels=story.get("source_labels") or [],
            story_id=story_id,
        )
        story["summary_text"] = normalized_summary
        auto_fixes.extend(attribution_auto_fixes)
        violations.extend(attribution_violations)

        violations.extend(self.validate_language(story, story_id))
        violations.extend(self.validate_user_name_usage_in_story(listener_first_name, story, story_id))
        violations.extend(self.validate_title_requirements(story, story_id))

        item_data["story"] = story
        return item_data, StoryValidationResult(
            story_id=story_id,
            passed=not any(violation.severity == "blocking" for violation in violations),
            violations=violations,
            auto_fixes=auto_fixes,
        )

    def validate_title_requirements(self, story: dict, story_id: str) -> list[EditorialContractViolation]:
        violations: list[EditorialContractViolation] = []
        title = str(story.get("short_headline") or "").strip()
        if not title:
            violations.append(self._blocking("title_required", "Story title is required.", story_id=story_id, field_name="short_headline"))
            return violations
        if len(TOKEN_PATTERN.findall(title)) > 8:
            violations.append(self._warning("title_max_words", "Story title still exceeds the 8-word limit after deterministic cleanup.", story_id=story_id, field_name="short_headline"))
        if title.lower() in GENERIC_HEADLINES:
            violations.append(self._warning("headline_quality_generic_placeholder", "Story title fell back to a generic placeholder because no cleaner deterministic rewrite was available.", story_id=story_id, field_name="short_headline"))
        if self._headline_is_english_heavy(title):
            violations.append(self._blocking("headline_quality", "Story title remains English-heavy or malformed after cleanup.", story_id=story_id, field_name="short_headline"))
        return violations

    def validate_source_attribution(
        self,
        summary_text: str,
        source_labels: list[str],
        story_id: str,
    ) -> tuple[str, list[EditorialContractAutoFix], list[EditorialContractViolation]]:
        auto_fixes: list[EditorialContractAutoFix] = []
        violations: list[EditorialContractViolation] = []
        source_labels = [label.strip() for label in source_labels if label and label.strip()]
        if not source_labels:
            violations.append(self._blocking("source_required", "Story is missing source labels for on-air attribution.", story_id=story_id))
            return summary_text, auto_fixes, violations
        if self._summary_has_source_reference(summary_text, source_labels):
            return summary_text, auto_fixes, violations
        source_label = self._display_source_label(source_labels[0])
        fixed_summary = f"Potrivit {source_label}, {self._lowercase_lead(summary_text)}"
        auto_fixes.append(
            EditorialContractAutoFix(
                rule="source_required",
                message="Added a deterministic source-attribution lead to the story body.",
                story_id=story_id,
                field_name="summary_text",
                original_value=summary_text,
                updated_value=fixed_summary,
            )
        )
        return fixed_summary, auto_fixes, violations

    def validate_language(self, story: dict, story_id: str) -> list[EditorialContractViolation]:
        violations: list[EditorialContractViolation] = []
        if self._text_is_english_heavy(str(story.get("summary_text") or "")):
            violations.append(self._blocking("mixed_language", "Story body is still mixed Romanian/English and cannot proceed to audio.", story_id=story_id, field_name="summary_text"))
        return violations

    def validate_quote_rules(
        self,
        summary_text: str,
        story: dict,
        story_id: str,
    ) -> tuple[str, list[EditorialContractAutoFix], list[EditorialContractViolation]]:
        auto_fixes: list[EditorialContractAutoFix] = []
        violations: list[EditorialContractViolation] = []
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", summary_text) if sentence.strip()]
        rewritten_sentences: list[str] = []
        for sentence in sentences:
            trimmed = sentence.strip().rstrip(".?!")
            post_attribution_match = POST_ATTRIBUTION_PATTERN.match(trimmed)
            if post_attribution_match:
                speaker = self._capitalize_phrase(post_attribution_match.group("speaker"))
                statement = self._lowercase_lead(post_attribution_match.group("statement"))
                rewritten = f"{speaker} a declarat ca {statement}."
                auto_fixes.append(
                    EditorialContractAutoFix(
                        rule="quote_source_precedes_statement",
                        message="Reordered a post-attributed declaration into a radio-safe named-source lead.",
                        story_id=story_id,
                        field_name="summary_text",
                        original_value=sentence,
                        updated_value=rewritten,
                    )
                )
                rewritten_sentences.append(rewritten)
                continue
            if QUOTE_PATTERN.search(sentence) and not self._quote_sentence_is_pre_attributed(sentence):
                violations.append(self._warning("quote_source_precedes_statement", "A quoted statement appears without a clearly named source before the quote.", story_id=story_id, field_name="summary_text"))
            rewritten_sentences.append(sentence)

        quote_count = sum(1 for sentence in rewritten_sentences if QUOTE_PATTERN.search(sentence))
        is_major_story = story.get("story_type") == "major" or bool(story.get("expanded_summary_used")) or (story.get("score_total") or 0) >= 70 or story.get("lead_type") in {"impact", "conflict"}
        if not is_major_story and quote_count > 1:
            violations.append(self._warning("quote_count", "Short story carries more than one direct quote.", story_id=story_id, field_name="summary_text"))
        if is_major_story and quote_count < 2:
            violations.append(self._warning("major_story_quote_count", "Major story does not include 2-3 attributed quotes where available.", story_id=story_id, field_name="summary_text"))
        if quote_count > 3:
            violations.append(self._warning("quote_count", "Story exceeds the preferred maximum of three direct quotes.", story_id=story_id, field_name="summary_text"))

        return " ".join(rewritten_sentences).strip(), auto_fixes, violations

    def validate_intro(self, briefing_data: dict) -> tuple[list[EditorialContractViolation], list[EditorialContractAutoFix]]:
        intro_text = str(briefing_data.get("intro_text") or "").strip()
        if intro_text:
            return [], []
        return [self._blocking("intro_required", "Bulletin intro is required.", segment_id="intro")], []

    def validate_outro(self, briefing_data: dict) -> tuple[list[EditorialContractViolation], list[EditorialContractAutoFix]]:
        outro_text = str(briefing_data.get("outro_text") or "").strip()
        if outro_text:
            return [], []
        return [self._blocking("outro_required", "Bulletin outro is required.", segment_id="outro")], []

    def validate_story_count(self, story_items_data: list[dict]) -> list[EditorialContractViolation]:
        story_count = len(story_items_data)
        if 6 <= story_count <= 10:
            return []
        return [
            self._blocking(
                "story_count_range",
                f"Bulletin contains {story_count} stories; required range is 6-10 before audio generation.",
                field_name="story_items",
            )
        ]

    def validate_presenter_alternation(self, story_items_data: list[dict]) -> list[EditorialContractViolation]:
        if self.presenter_mode != "dual_test":
            return []
        violations: list[EditorialContractViolation] = []
        expected = ["female" if index % 2 == 1 else "male" for index in range(1, len(story_items_data) + 1)]
        actual = [item.get("presenter_voice") for item in story_items_data]
        if actual != expected:
            violations.append(
                self._warning(
                    "presenter_alternation",
                    "Dual presenter test mode is enabled, but assembled story presenters do not alternate Ana/Paul consistently.",
                    field_name="story_items.presenter_voice",
                )
            )
        return violations

    def validate_perspective_adjacency(self, story_items_data: list[dict]) -> list[EditorialContractViolation]:
        violations: list[EditorialContractViolation] = []
        for item in story_items_data:
            perspectives = list(item.get("perspective_segments") or [])
            if not perspectives:
                continue
            if len(perspectives) != 2:
                violations.append(
                    self._warning(
                        "perspective_adjacency",
                        "Perspective segments should appear as one supporters/critics pair immediately after the parent story.",
                        story_id=item["story"]["cluster_id"],
                        field_name="perspective_segments",
                    )
                )
                continue
            perspective_types = [segment.get("type") for segment in perspectives]
            if any(segment_type != "perspective" for segment_type in perspective_types):
                violations.append(
                    self._warning(
                        "perspective_adjacency",
                        "Perspective pair contains a non-perspective segment type.",
                        story_id=item["story"]["cluster_id"],
                        field_name="perspective_segments",
                    )
                )
        return violations

    def validate_local_anchor(
        self,
        briefing: FinalEditorialBriefingPackage,
        story_items_data: list[dict],
    ) -> list[EditorialContractViolation]:
        if not briefing.local_sources_enabled or briefing.local_source_count <= 0:
            return []
        monitored_configs, _ = self.source_watcher_service.resolve_monitored_source_configs(briefing.personalization)
        local_source_names = {
            self._normalize_text(getattr(config, "source_name", getattr(config, "name", "")))
            for config in monitored_configs
            if getattr(config, "scope", None) == "local"
        }
        for item in story_items_data:
            normalized_labels = {self._normalize_text(label) for label in item["story"].get("source_labels") or []}
            if normalized_labels & local_source_names:
                return []
        return [
            self._warning(
                "local_anchor_story_missing",
                "Local candidates existed for the listener region, but no local story survived into the final bulletin.",
                field_name="story_items",
            )
        ]

    def validate_user_name_usage(
        self,
        personalization: UserPersonalization,
        story_items_data: list[dict],
    ) -> list[EditorialContractViolation]:
        listener_first_name = personalization.listener_profile.first_name
        if not listener_first_name:
            return []
        return [
            self._blocking(
                "user_name_allowed_only_in_intro_outro",
                "Listener first name appeared inside a story body, but user names are allowed only in intro/outro.",
                story_id=item["story"]["cluster_id"],
                field_name="summary_text",
            )
            for item in story_items_data
            if self._contains_listener_name(item["story"].get("summary_text"), listener_first_name)
        ]

    def validate_user_name_usage_in_story(
        self,
        listener_first_name: str | None,
        story: dict,
        story_id: str,
    ) -> list[EditorialContractViolation]:
        if not listener_first_name:
            return []
        violations: list[EditorialContractViolation] = []
        if self._contains_listener_name(story.get("summary_text"), listener_first_name):
            violations.append(self._blocking("user_name_allowed_only_in_intro_outro", "Listener first name appeared inside story body.", story_id=story_id, field_name="summary_text"))
        if self._contains_listener_name(story.get("short_headline"), listener_first_name):
            violations.append(self._blocking("user_name_allowed_only_in_intro_outro", "Listener first name appeared inside story title.", story_id=story_id, field_name="short_headline"))
        return violations

    def validate_intro_outro_variants(self, briefing_data: dict) -> list[EditorialContractViolation]:
        violations: list[EditorialContractViolation] = []
        if not str(briefing_data.get("intro_variant") or "").strip():
            violations.append(self._warning("intro_variant_missing", "Intro variant metadata is missing from the assembled bulletin.", segment_id="intro", field_name="intro_variant"))
        if not str(briefing_data.get("outro_variant") or "").strip():
            violations.append(self._warning("outro_variant_missing", "Outro variant metadata is missing from the assembled bulletin.", segment_id="outro", field_name="outro_variant"))
        return violations

    def _normalize_title(
        self,
        title: str,
        story: dict,
    ) -> tuple[str, list[EditorialContractAutoFix], list[EditorialContractViolation]]:
        auto_fixes: list[EditorialContractAutoFix] = []
        violations: list[EditorialContractViolation] = []
        original_title = title
        cleaned = NOISY_HEADLINE_PATTERN.sub("", title).strip(" -:;,.")
        cleaned = SEO_FRAGMENT_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            fallback_title = str(story.get("representative_title") or "").strip()
            cleaned = NOISY_HEADLINE_PATTERN.sub("", fallback_title).strip(" -:;,.")
        tokens = TOKEN_PATTERN.findall(cleaned)
        if len(tokens) > 8:
            cleaned = " ".join(tokens[:8])
        if cleaned and cleaned != original_title:
            auto_fixes.append(
                EditorialContractAutoFix(
                    rule="headline_quality",
                    message="Normalized noisy or overlong story headline deterministically.",
                    field_name="short_headline",
                    original_value=original_title,
                    updated_value=cleaned,
                )
            )
        if not cleaned:
            violations.append(self._blocking("headline_quality", "Story title could not be normalized into a usable headline.", field_name="short_headline"))
        return cleaned, auto_fixes, violations

    def _summary_has_source_reference(self, summary_text: str, source_labels: list[str]) -> bool:
        lowered = summary_text.lower()
        if any(re.search(prefix, lowered) for prefix in ATTRIBUTION_PREFIXES):
            for label in source_labels:
                normalized = self._normalize_text(label)
                if not normalized:
                    continue
                source_tokens = normalized.split()
                if any(token in lowered for token in source_tokens if len(token) >= 3):
                    return True
        for label in source_labels:
            normalized_label = self._normalize_text(label)
            if normalized_label and normalized_label in self._normalize_text(summary_text):
                return True
        return False

    def _quote_sentence_is_pre_attributed(self, sentence: str) -> bool:
        lowered = self._normalize_text(sentence)
        for prefix in ("potrivit", "conform", "scrie", "spune", "transmite", "afirma", "a declarat"):
            if lowered.startswith(prefix):
                return True
        return bool(re.match(r"^[A-ZA��??][^,]{1,80}\s+(spune|transmite|afirma|a declarat)", sentence))

    def _text_is_english_heavy(self, text: str) -> bool:
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(text)]
        if not tokens:
            return False
        english_hits = sum(1 for token in tokens if token in ENGLISH_MARKERS)
        romanian_hits = sum(1 for token in tokens if token in ROMANIAN_MARKERS)
        return english_hits >= 3 and english_hits > romanian_hits

    def _headline_is_english_heavy(self, headline: str) -> bool:
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(headline)]
        if not tokens:
            return False
        english_hits = sum(1 for token in tokens if token in ENGLISH_MARKERS)
        romanian_hits = sum(1 for token in tokens if token in ROMANIAN_MARKERS)
        return english_hits >= 2 and english_hits > romanian_hits

    def _contains_listener_name(self, text: object, listener_first_name: str) -> bool:
        if not text:
            return False
        return listener_first_name.strip().lower() in str(text).lower()

    def _display_source_label(self, label: str) -> str:
        trimmed = label.strip()
        if trimmed.endswith(".ro"):
            return trimmed
        return trimmed.replace("http://", "").replace("https://", "")

    def _normalize_text(self, text: object) -> str:
        return " ".join(str(text or "").lower().split())

    def _lowercase_lead(self, text: str) -> str:
        value = text.strip()
        if not value:
            return value
        return value[0].lower() + value[1:]

    def _capitalize_phrase(self, text: str) -> str:
        value = " ".join(text.split()).strip(" ,")
        if not value:
            return value
        return value[0].upper() + value[1:]

    def _build_summary(
        self,
        briefing_id: str,
        story_ids: list[str],
        blocking_violation_count: int,
        warning_count: int,
        auto_fix_count: int,
    ) -> str:
        status = "passed" if blocking_violation_count == 0 else "failed"
        return (
            f"Editorial contract validation {status} for briefing '{briefing_id}' with "
            f"{len(story_ids)} stories, {blocking_violation_count} blocking violation(s), "
            f"{warning_count} warning(s), and {auto_fix_count} auto-fix(es)."
        )

    def _write_report(
        self,
        briefing: FinalEditorialBriefingPackage,
        result: BulletinValidationResult,
        all_violations: list[EditorialContractViolation],
        all_auto_fixes: list[EditorialContractAutoFix],
    ) -> Path:
        DEBUG_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "briefing_id": briefing.briefing_id,
            "passed": result.passed,
            "validated_at": result.validated_at.isoformat(),
            "summary": result.summary,
            "blocking_violation_count": result.blocking_violation_count,
            "warning_count": result.warning_count,
            "auto_fix_count": result.auto_fix_count,
            "briefing_context": {
                "story_count": len(briefing.story_items),
                "intro_variant": briefing.intro_variant,
                "outro_variant": briefing.outro_variant,
                "local_source_count": briefing.local_source_count,
                "local_sources_enabled": briefing.local_sources_enabled,
                "local_editorial_anchor": briefing.local_editorial_anchor,
            },
            "story_results": [result_item.model_dump() for result_item in result.story_results],
            "bulletin_violations": [violation.model_dump() for violation in result.violations],
            "bulletin_auto_fixes": [fix.model_dump() for fix in result.auto_fixes],
            "all_violations": [violation.model_dump() for violation in all_violations],
            "all_auto_fixes": [fix.model_dump() for fix in all_auto_fixes],
        }
        DEBUG_REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return DEBUG_REPORT_PATH

    def _blocking(self, rule: str, message: str, **kwargs) -> EditorialContractViolation:
        return EditorialContractViolation(rule=rule, severity="blocking", message=message, **kwargs)

    def _warning(self, rule: str, message: str, **kwargs) -> EditorialContractViolation:
        return EditorialContractViolation(rule=rule, severity="warning", message=message, **kwargs)

    def _dump_model(self, model) -> dict:
        if hasattr(model, "model_dump"):
            return model.model_dump()
        return model.dict()
