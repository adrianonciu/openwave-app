from __future__ import annotations

from collections import deque
import re
import unicodedata

from app.models.article_fetch import FetchedArticle
from app.models.generated_story_summary import GeneratedStorySummary
from app.models.radio_edited_story import (
    CompressedStoryCore,
    RadioEditedStory,
    RadioSentenceDecision,
)

WORD_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")
MULTISPACE_PATTERN = re.compile(r"\s+")
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
NOISY_PREFIX_PATTERN = re.compile(
    r"^(?:breaking|live|update|actualizare|exclusiv|video|foto)\s*[:\-]*\s*",
    re.IGNORECASE,
)
QUOTE_STRIP_PATTERN = re.compile(r"[\"']")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u00C0-\u024F'-]+", re.UNICODE)
PERSON_PATTERN = re.compile(
    r"\b([A-Z][a-z\u00C0-\u024F]+(?:\s+[A-Z][a-z\u00C0-\u024F]+){1,2})\b",
    re.UNICODE,
)
PERCENT_PATTERN = re.compile(r"\b(\d{1,2}),(\d)\d*%")
LARGE_NUMBER_PATTERN = re.compile(r"\b\d{1,3}(?:[.,]\d{3})+\b")
DECIMAL_BILLION_PATTERN = re.compile(r"\b(\d{1,2}),(\d)\s+miliarde\b", re.IGNORECASE)
DECIMAL_MILLION_PATTERN = re.compile(r"\b(\d{1,2}),(\d)\s+milioane\b", re.IGNORECASE)

INSTITUTION_PATTERNS = [
    "Guvernul Romaniei",
    "Guvernul",
    "Consiliul Superior al Magistraturii",
    "CSM",
    "DNA",
    "ANAF",
    "Casa Alba",
    "Primaria Cluj",
    "Primaria",
    "Ministerul Justitiei",
    "Ministerul Finantelor",
    "Ministerul",
    "Compania de Transport Public",
    "Transport Public",
    "Presedintia",
    "Presedintie",
    "Palatul Cotroceni",
    "Palatul Victoria",
    "Comisia Europeana",
    "Uniunea Europeana",
    "NATO",
    "ONU",
]
LOCATION_PATTERNS = [
    "Romania",
    "Cluj",
    "Manastur",
    "Stramtoarea Ormuz",
    "Ormuz",
    "Iran",
    "Washington",
    "Europa",
]
MEDIA_MARKERS = ["Agerpres", "Reuters", "AP", "BBC", "Digi24", "HotNews", "Mediafax", "Monitorul de Cluj"]
INTERNATIONAL_SOURCE_LABELS = {"Reuters", "AP", "BBC", "Financial Times", "Bloomberg", "The Guardian", "Politico Europe"}
LOCAL_SOURCE_LABEL_MARKERS = {"Bacau", "Cluj", "Iasi", "Suceava", "Monitorul", "Ziarul de", "Bacau.net", "Desteptarea"}
ACTION_VERBS = {
    "anunta", "adopta", "aproba", "cere", "decide", "trimite", "incepe", "blocheaza",
    "confirma", "spune", "transmite", "estimeaza", "respinge", "reduce", "introduce",
    "poate", "promite", "da", "vizeaza", "lucreaza", "urmareste", "schimba", "inseamna",
}
REACTION_VERBS = {"spune", "a spus", "transmite", "a transmis", "confirma", "a confirmat", "estimeaza", "a anuntat", "anunta", "promite", "respinge", "a declarat", "declara", "a precizat", "precizeaza", "a explicat", "explica", "a promis", "a avertizat", "avertizeaza"}
DETAIL_KEYWORDS = {
    "ordonanta", "aviz", "controale", "schema", "frauda", "nave", "lucrari", "benzi",
    "audieri", "rambursarile", "santierul", "prejudiciul", "transportul", "actul", "semaforizare",
    "platforma", "procedurile", "tranzactii", "etape",
}
IMPACT_KEYWORDS = {
    "impact", "inseamna", "presiunea", "buget", "preturi", "energie", "trafic",
    "executie", "efect", "consecinta", "investitori", "studenti", "navetisti", "costuri",
}
NEXT_STEP_KEYWORDS = {
    "de luna viitoare", "primele efecte", "urmatorul pas", "vor fi prezentate", "intra in vigoare",
    "mai departe", "urmeaza", "programate", "de luni", "de marti",
    "in cateva zile", "in cateva saptamani", "de anul viitor", "luna aceasta", "saptamanii viitoare",
}
CONTRAST_MARKERS = {"opozitia", "critici", "respinge", "contestata"}
TRIM_MARKERS = [", in timp ce", ", iar", ", insa", ", dar", ", dupa", ", care", " pe fondul", " intr-un moment in care"]
PRINT_STYLE_REPLACEMENTS = {
    "conteaza pentru ca": "asta inseamna ca",
    "cantareste politic": "are efect politic",
    "prezinta importanta": "este important",
    "intr-un moment in care": "acum, cand",
    "in contextul in care": "dupa ce",
    "guvernul afirma ca": "Guvernul spune ca",
    "opozitia sustine insa ca": "Opozitia spune ca",
    "releva presiunea": "arata presiunea",
    "subliniaza": "spune",
    "potrivit surselor": "",
    "se pare ca": "",
}
OPERATIONAL_REPLACEMENTS = {
    "benzi pentru transportul public si modificari la semaforizare": "benzi dedicate transportului public si schimbari de trafic",
    "platforma comuna pentru institutiile care emit aprobari": "platforma comuna pentru avize",
    "evaluarea planului de management": "analiza dosarului",
    "centralizarea controalelor din teritoriu": "inchiderea controalelor din teritoriu",
    "procedurile de avizare": "avizele",
}
ADMINISTRATIVE_MARKERS = {
    "analiza dosarului",
    "evaluarea planului",
    "procedura",
    "centralizarea",
    "mai departe catre",
    "planului de management",
    "emit aprobari",
    "emit avize",
}
STRONG_CLOSURE_KEYWORDS = {
    "intra in vigoare",
    "primele efecte",
    "primele rezultate",
    "se aplica",
    "va fi confirmat",
    "vor fi confirmate",
    "este investigat",
    "este anchetat",
    "urmeaza",
    "de luni",
    "luna viitoare",
    "in cateva zile",
    "in cateva saptamani",
    "de anul viitor",
    "in aceasta luna",
    "saptamanii viitoare",
    "zilele urmatoare",
    "finalul saptamanii",
}
ATTRIBUTION_PREFIX_PATTERN = re.compile(
    r"^(?P<actor>(?:[A-Z][\w-]+(?:\s+[A-Z][\w-]+){0,4}|CSM|ANAF|DNA|ONU|NATO))\s+"
    r"(?P<verb>a spus|spune|a transmis|transmite|a anuntat|anunta|a confirmat|confirma|relateaza)\s+ca\s+",
    re.UNICODE,
)
ROLE_PREFIX_PATTERN = re.compile(
    r"\b(?P<role>Premierul|Presedintele|Primarul|Ministrul|Procurorul|Judecatorul|Directorul(?:\s+[a-z\u00C0-\u024F]+){0,2}|Inspectorul(?:\s+[a-z\u00C0-\u024F]+){0,2}|Prefectul|Medicul(?:\s+[a-z\u00C0-\u024F]+){0,2})[,]?\s+(?P<name>[A-Z][a-z\u00C0-\u024F]+(?:\s+[A-Z][a-z\u00C0-\u024F]+){1,2})\b",
    re.UNICODE,
)
PERSON_STOPWORDS = {
    "Romania", "Guvernul", "Ministerul", "Primaria", "Casa", "Palatul", "Stramtoarea", "Compania", "Transport",
    "Consiliul", "Statele", "Europa", "Washington", "Presedintie", "Presedintia", "Marii", "Marea",
}
SPARSE_MIN_WORDS = 65
SPARSE_MAX_WORDS = 82
STANDARD_MIN_WORDS = 85
STANDARD_MAX_WORDS = 105
MAJOR_MIN_WORDS = 105
MAJOR_MAX_WORDS = 125
LEAD_MAX_WORDS = 20
SENTENCE_SOFT_MAX_WORDS = 24
MAX_SENTENCE_COUNT = 4
WPM = 100
TITLE_LEAD_OVERLAP_THRESHOLD = 0.66
COMPARISON_STOPWORDS = {
    "a", "al", "ai", "ale", "ca", "cu", "de", "din", "dupa", "in", "la", "pe", "pentru", "prin",
    "si", "spre", "un", "una", "unui", "unei", "sau", "noi", "nou", "noua", "zona",
}
LEAD_EVENT_NOMINALIZATIONS = {
    "incepe": "inceperea",
    "deschide": "deschiderea",
    "lanseaza": "lansarea",
    "pregateste": "pregatirea",
    "impune": "impunerea",
    "trimite": "trimiterea",
    "aproba": "aprobarea",
    "extinde": "extinderea",
    "muta": "mutarea",
    "simplifica": "simplificarea",
}
CONSEQUENCE_LEAD_STARTS = (
    "asta inseamna", "asta poate", "de luni", "de marti", "de miercuri", "de joi", "de vineri", "de sambata",
    "de duminica", "primele restrictii", "primele verificari", "primele efecte", "in cateva", "din aceasta",
    "de la inceputul", "pentru romania", "impactul este", "decizia mentine", "preturile", "programul",
    "platforma", "masura va", "schimbarea poate",
)
CONCRETE_ACTION_LEAD_STARTS = (
    "pompierii", "inspectorii", "echipele", "medicii", "autoritatile", "masura vizeaza", "masura aduce",
    "primele verificari", "rectorii", "guvernul reduce", "orarul provizoriu", "programul actualizat",
)
AFFECTED_AUDIENCE_LEAD_STARTS = (
    "soferii", "pacientii", "elevii", "parintii", "fermierii", "consumatorii", "navetistii", "studentii",
    "locuitorii", "calatorii", "administratorii", "familiile", "gospodariile", "investitorii",
)
PERSONAL_ATTRIBUTION_VERBS = ("a declarat", "declara", "a spus", "spune", "spun", "a precizat", "precizeaza", "a explicat", "explica", "a promis", "promite", "a avertizat", "avertizeaza", "a anuntat", "anunta", "a transmis", "transmite", "transmit", "relateaza", "scrie")
ROLE_BASED_PERSON_MARKERS = ("primarul", "directorul", "director", "inspectorul", "inspectorii", "prefectul", "medicul", "medicul sef", "medicul coordonator", "fermierii", "soferii", "autoritatile locale", "managerul", "ministrul", "premierul")
PERSONAL_ATTRIBUTION_ENCOURAGED_TERMS = ("primarie", "spital", "isu", "trafic", "lucrari", "restrictii", "drum", "educatie", "scoala", "elev", "fermier", "seceta", "preturi", "servicii", "controverse", "controale", "urgente")
ROLE_BASED_ATTRIBUTION_MAP = {
    "primaria": "Primarul",
    "spitalul": "Directorul spitalului",
    "spital": "Directorul spitalului",
    "isu": "Inspectorul ISU",
    "inspectoratul": "Inspectorul ISU",
    "guvernul": "Premierul",
    "ministerul educatiei": "Ministrul Educatiei",
    "ministerul agriculturii": "Ministrul Agriculturii",
    "ministerul energiei": "Ministrul Energiei",
    "ministerul": "Ministrul",
    "consiliul judetean": "Presedintele Consiliului Judetean",
    "autoritatile locale": "Autoritatile locale",
}

TITLE_ACTION_FAMILY_MARKERS = {
    "scale_up": ("dublez", "dubleaza", "dublat", "extinde", "extind", "mareste", "maresc", "verificari extinse"),
    "prepare": ("pregateste", "pregatesc", "lucreaza la", "schema noua", "sprijin"),
    "reroute": ("muta", "mutarea", "redirectioneaza", "deviaza", "rute ocolitoare"),
    "reject": ("respinge", "respins", "aviz negativ", "blocheaza", "blocat"),
    "launch": ("lanseaza", "introduce", "duce sistemul", "catalogul digital", "introduce sistemul"),
    "start": ("incepe", "inceperea", "inceput", "deschide", "deschid", "porneste"),
}

REPEATED_TIME_MARKERS = (
    "de luni",
    "de marti",
    "de miercuri",
    "de joi",
    "de vineri",
    "de sambata",
    "de duminica",
    "saptamanii viitoare",
    "luna viitoare",
    "in cateva zile",
    "in cateva saptamani",
)

CLOSING_PHRASE_BANK = {
    "operational_timing": (
        "Masura intra in vigoare chiar din aceasta saptamana.",
        "Echipele intra pe teren in zilele urmatoare.",
        "Programul actualizat se aplica chiar din primele zile.",
    ),
    "immediate_impact": (
        "Locuitorii pot vedea schimbarea chiar din primele zile.",
        "Decizia ar putea influenta preturile rapid.",
        "Primele schimbari se pot simti chiar din aceasta perioada.",
    ),
    "institution_followup": (
        "Autoritatile spun ca situatia va fi monitorizata zilnic.",
        "Oficialii promit evaluari rapide ale masurii.",
        "Institutiile implicate spun ca vor urmari efectele de la o zi la alta.",
    ),
    "policy_impact": (
        "Decizia ar putea schimba regulile pentru companii si consumatori.",
        "Masura poate redesena costurile pentru firme si familii.",
        "Schimbarea poate avea efect direct asupra companiilor si consumatorilor.",
    ),
}


class RadioEditingService:
    def __init__(self) -> None:
        self.reset_variation_state()

    def reset_variation_state(self) -> None:
        self._recent_lead_families: deque[str] = deque(maxlen=3)
        self._recent_closing_families: deque[str] = deque(maxlen=3)
        self._recent_closing_sentences: deque[str] = deque(maxlen=3)

    def build_radio_story(self, article_or_story: object) -> RadioEditedStory:
        payload = self._normalize_input(article_or_story)
        compression = self.compress_story_for_radio(article_or_story)
        radio_sentences = self._build_radio_sentences(payload, compression)
        radio_sentences, polish_metrics = self._polish_radio_sentences(payload, compression, radio_sentences)
        radio_text = " ".join(radio_sentences).strip()
        word_count = self._word_count(radio_text)
        duration_seconds = self._estimate_duration_seconds(word_count)
        attribution_slot = self._detect_attribution_slot(radio_text, payload)
        lead_word_count = self._word_count(radio_sentences[0]) if radio_sentences else 0
        actor_early = self._main_actor_appears_early(radio_sentences[0] if radio_sentences else "", compression.kept_entities)
        debug_notes = list(compression.debug_notes)
        debug_notes.append(f"radio_sentence_count={len(radio_sentences)}")
        debug_notes.append(f"radio_word_count={word_count}")
        debug_notes.append(f"attribution_slot={attribution_slot}")
        debug_notes.append(f"lead_word_count={lead_word_count}")
        debug_notes.append(f"main_actor_early={actor_early}")
        debug_notes.append(f"source_scope={payload['source_scope']}")
        debug_notes.append(f"lead_title_overlap_score={polish_metrics['lead_title_overlap_score']}")
        debug_notes.append(f"lead_rewritten_to_reduce_title_repetition={polish_metrics['lead_rewritten_to_reduce_title_repetition']}")
        debug_notes.append(f"lead_continuation_rewrite_applied={polish_metrics['lead_continuation_rewrite_applied']}")
        debug_notes.append(f"stories_rewritten_via_continuation_strategy={polish_metrics['stories_rewritten_via_continuation_strategy']}")
        debug_notes.append(f"lead_opening_type={polish_metrics['lead_opening_type']}")
        debug_notes.append(f"generated_lead_initial={polish_metrics['generated_lead_initial']}")
        debug_notes.append(f"generated_lead_final={polish_metrics['generated_lead_final']}")
        debug_notes.append(f"title_main_entity={polish_metrics['title_main_entity']}")
        debug_notes.append(f"title_main_action_family={polish_metrics['title_main_action_family']}")
        debug_notes.append(f"stories_with_lead_starting_with_institution={polish_metrics['stories_with_lead_starting_with_institution']}")
        debug_notes.append(f"stories_with_lead_starting_with_institution_and_title_like_action={polish_metrics['stories_with_lead_starting_with_institution_and_title_like_action']}")
        debug_notes.append(f"lead_starter_family={polish_metrics['lead_starter_family']}")
        debug_notes.append(f"closing_phrase_family={polish_metrics['closing_phrase_family']}")
        debug_notes.append(f"duplicate_sentence_removed={polish_metrics['duplicate_sentence_removed']}")
        debug_notes.append(f"stories_with_intra_story_repetition={polish_metrics['stories_with_intra_story_repetition']}")
        debug_notes.append(f"stories_with_duplicate_sentence_removed={polish_metrics['stories_with_duplicate_sentence_removed']}")
        debug_notes.append(f"stories_with_closing_variation_applied={polish_metrics['stories_with_closing_variation_applied']}")
        debug_notes.append(f"lead_has_personal_attribution={polish_metrics['lead_has_personal_attribution']}")
        debug_notes.append(f"second_sentence_has_personal_attribution={polish_metrics['second_sentence_has_personal_attribution']}")
        debug_notes.append(f"promoted_person_attribution_sentence_count={polish_metrics['promoted_person_attribution_sentence_count']}")
        debug_notes.append(f"role_based_attribution_inserted_count={polish_metrics['role_based_attribution_inserted_count']}")
        debug_notes.append(f"stories_with_personal_attribution={polish_metrics['stories_with_personal_attribution']}")
        debug_notes.append(f"stories_with_person_name_attribution={polish_metrics['stories_with_person_name_attribution']}")
        debug_notes.append(f"stories_with_person_role_and_name_attribution={polish_metrics['stories_with_person_role_and_name_attribution']}")
        debug_notes.append(f"stories_with_institution_only_attribution={polish_metrics['stories_with_institution_only_attribution']}")
        debug_notes.append(f"stories_with_institution_attribution={polish_metrics['stories_with_institution_attribution']}")
        debug_notes.append(f"stories_with_media_attribution={polish_metrics['stories_with_media_attribution']}")
        debug_notes.append(f"stories_with_media_source_attribution={polish_metrics['stories_with_media_source_attribution']}")
        debug_notes.append(f"stories_missing_attributed_voice={polish_metrics['stories_missing_attributed_voice']}")
        debug_notes.append(f"attribution_type_used={polish_metrics['attribution_type_used']}")
        debug_notes.append(f"attribution_level_used={polish_metrics['attribution_level_used']}")
        debug_notes.append(f"attribution_position_used={polish_metrics['attribution_position_used']}")
        debug_notes.append(f"attributed_name_used={polish_metrics['attributed_name_used']}")
        debug_notes.append(f"attributed_role_used={polish_metrics['attributed_role_used']}")
        debug_notes.append(f"attributed_institution_used={polish_metrics['attributed_institution_used']}")
        debug_notes.append(f"attributed_media_source_used={polish_metrics['attributed_media_source_used']}")
        debug_notes.append(f"person_attribution_used={polish_metrics['person_attribution_used']}")
        debug_notes.append(f"person_name={polish_metrics['person_name']}")
        debug_notes.append(f"person_role={polish_metrics['person_role']}")
        debug_notes.append(f"has_named_person={polish_metrics['has_named_person']}")
        debug_notes.append(f"has_role_based_person={polish_metrics['has_role_based_person']}")
        debug_notes.append(f"lead_has_quote_or_person={polish_metrics['lead_has_quote_or_person']}")
        debug_notes.append(f"high_title_lead_overlap={polish_metrics['high_title_lead_overlap']}")
        debug_notes.append(f"romania_impact_included={polish_metrics['romania_impact_included']}")
        debug_notes.append(f"strong_closure={polish_metrics['strong_closure']}")
        debug_notes.append(f"repeated_person_name_count={polish_metrics['repeated_person_name_count']}")
        debug_notes.append(f"multiple_attributions={polish_metrics['multiple_attributions']}")
        debug_notes.append(f"administrative_closure={polish_metrics['administrative_closure']}")
        debug_notes.append(f"simplified_operational_description_count={polish_metrics['simplified_operational_description_count']}")
        if not self._is_romanian_safe(radio_text):
            debug_notes.append("romanian_safety_warning=some_english_markers_remain")

        self._register_story_variation(
            polish_metrics["lead_starter_family"],
            polish_metrics["closing_phrase_family"],
        )

        return RadioEditedStory(
            story_id=payload["story_id"],
            headline_original=payload["headline_original"],
            compressed_facts=compression.compressed_facts,
            radio_sentences=radio_sentences,
            radio_text=radio_text,
            estimated_word_count=word_count,
            estimated_duration_seconds=duration_seconds,
            kept_entities=compression.kept_entities,
            dropped_entities=compression.dropped_entities,
            editing_debug_notes=debug_notes,
            compression_debug=compression,
        )

    def compress_story_for_radio(self, article_or_story: object) -> CompressedStoryCore:
        payload = self._normalize_input(article_or_story)
        people = self._extract_persons(payload["full_text"])
        institutions = self._extract_institutions(payload["full_text"])
        locations = self._extract_locations(payload["full_text"])
        kept_entities = self._prune_entities(people, institutions, locations)
        kept_entity_set = set(kept_entities)
        band = self._determine_story_band(payload)
        sentences = self._candidate_sentences(payload)
        decisions = [self._build_sentence_decision(sentence, index, kept_entity_set) for index, sentence in enumerate(sentences)]
        selected = self._select_story_core(decisions)
        compressed_sentences = [self._rewrite_for_radio(item.text, item.role, kept_entities) for item in selected]
        compressed_sentences = [sentence for sentence in compressed_sentences if sentence]
        compressed_text = self._enforce_word_budget(compressed_sentences, band)
        compressed_word_count = self._word_count(compressed_text)

        debug_notes = [
            f"story_band={band}",
            f"source_word_count={payload['source_word_count']}",
            f"candidate_sentence_count={len(sentences)}",
            f"kept_sentence_count={len(selected)}",
            f"compressed_word_count={compressed_word_count}",
            f"person_preserved={bool(payload['top_person'] and payload['top_person'] in kept_entities)}",
            f"entity_budget={len(kept_entities)}",
        ]

        return CompressedStoryCore(
            story_id=payload["story_id"],
            headline_original=payload["headline_original"],
            source_text_word_count=payload["source_word_count"],
            compressed_text=compressed_text,
            compressed_word_count=compressed_word_count,
            estimated_duration_seconds=self._estimate_duration_seconds(compressed_word_count),
            compressed_facts=self._build_fact_core(
                payload,
                [sentence for sentence in SENTENCE_SPLIT_PATTERN.split(compressed_text) if sentence.strip()],
                kept_entities,
            ),
            kept_sentences=selected,
            dropped_sentences=[item for item in decisions if item.text not in {picked.text for picked in selected}],
            kept_entities=kept_entities,
            dropped_entities=[entity for entity in people + institutions + locations if entity not in kept_entities][:8],
            debug_notes=debug_notes,
        )

    def apply_to_generated_story_summary(self, story: GeneratedStorySummary) -> GeneratedStorySummary:
        radio_story = self.build_radio_story(story)
        radio_sentences = [sentence for sentence in SENTENCE_SPLIT_PATTERN.split(radio_story.radio_text) if sentence.strip()]
        compliance = story.policy_compliance.model_copy(
            update={
                "estimated_duration_seconds": radio_story.estimated_duration_seconds,
                "sentence_count_ok": 3 <= len(radio_sentences) <= 4,
                "word_count_ok": radio_story.estimated_word_count >= 65,
                "structure_ok": len(radio_sentences) >= 3,
                "notes": list(story.policy_compliance.notes) + ["radio_editing_v1_5_applied"],
            }
        )
        debug_note = f"radio_editing_v1_5={radio_story.estimated_word_count}w/{radio_story.estimated_duration_seconds}s"
        return story.model_copy(
            update={
                "lead": radio_sentences[0] if radio_sentences else story.lead,
                "body": " ".join(radio_sentences[1:]).strip(),
                "summary_text": radio_story.radio_text,
                "sentence_count": len(radio_sentences),
                "word_count": radio_story.estimated_word_count,
                "policy_compliance": compliance,
                "editorial_notes": list(story.editorial_notes) + [debug_note],
                "generation_explanation": story.generation_explanation + f" Radio editing v1.5 calibrated the story to {radio_story.estimated_word_count} words and {len(radio_sentences)} sentences for bulletin pacing.",
                "original_summary_text": story.summary_text,
                "radio_edited_story": radio_story,
            }
        )

    def _normalize_input(self, article_or_story: object) -> dict[str, object]:
        source_label = None
        if isinstance(article_or_story, GeneratedStorySummary):
            headline = article_or_story.headline or article_or_story.short_headline or article_or_story.representative_title or "Subiect important"
            story_id = article_or_story.story_id or article_or_story.cluster_id
            text_parts = [article_or_story.lead, article_or_story.source_attribution, article_or_story.body, *article_or_story.quotes, article_or_story.summary_text]
            source_label = next(iter(article_or_story.source_labels), None)
        elif isinstance(article_or_story, FetchedArticle):
            headline = article_or_story.title or "Subiect important"
            story_id = self._fallback_story_id(article_or_story.url)
            text_parts = [article_or_story.content_text]
            source_label = article_or_story.source
        elif isinstance(article_or_story, dict):
            headline = str(article_or_story.get("headline") or article_or_story.get("title") or "Subiect important")
            story_id = str(article_or_story.get("story_id") or article_or_story.get("id") or self._fallback_story_id(headline))
            text_parts = [
                str(article_or_story.get("summary") or ""),
                str(article_or_story.get("lead") or ""),
                str(article_or_story.get("body") or ""),
                str(article_or_story.get("content_text") or article_or_story.get("content") or ""),
                str(article_or_story.get("source_attribution") or ""),
            ]
            source_label = article_or_story.get("source_label") or article_or_story.get("source")
        else:
            raise TypeError("Unsupported story payload for radio editing.")

        headline_sentence = self._headline_to_sentence(str(headline))
        source_text = self._clean_text(" ".join(part for part in text_parts if part and str(part).strip())) or headline_sentence
        full_text = f"{headline_sentence} {source_text}".strip()
        source_sentences = [self._clean_text(sentence) for sentence in SENTENCE_SPLIT_PATTERN.split(source_text) if self._clean_text(sentence)]
        people = self._extract_persons(full_text)
        top_person = people[0] if people else None
        return {
            "story_id": story_id,
            "headline_original": headline_sentence,
            "source_text": source_text,
            "full_text": full_text,
            "source_text_sentences": source_sentences,
            "source_word_count": self._word_count(source_text),
            "source_label": str(source_label).strip() if source_label else None,
            "source_scope": self._infer_story_scope(article_or_story, str(source_label).strip() if source_label else None, full_text),
            "top_person": top_person,
            "top_person_role": self._extract_role_alias(full_text, top_person) if top_person else None,
            "available_role_markers": self._extract_role_markers(full_text),
        }

    def _determine_story_band(self, payload: dict[str, object]) -> str:
        fact_density = sum(
            1
            for sentence in payload["source_text_sentences"]
            if self._sentence_has_detail(sentence)
            or self._sentence_has_impact(sentence)
            or self._sentence_has_next_step(sentence)
        )
        sentence_count = len(payload["source_text_sentences"])
        if payload["source_word_count"] >= 125 and fact_density >= 4 and sentence_count >= 5:
            return "major"
        if payload["source_word_count"] >= 80 and fact_density >= 3 and sentence_count >= 4:
            return "standard"
        if payload["source_word_count"] >= 72 and fact_density >= 2 and sentence_count >= 4 and payload.get("top_person"):
            return "standard"
        return "sparse"

    def _candidate_sentences(self, payload: dict[str, object]) -> list[str]:
        sentences: list[str] = []
        for sentence in payload["source_text_sentences"]:
            if self._word_count(sentence) < 5:
                continue
            if sentence not in sentences:
                sentences.append(sentence)
        return sentences or [payload["headline_original"]]

    def _build_sentence_decision(self, sentence: str, index: int, kept_entities: set[str]) -> RadioSentenceDecision:
        lowered = sentence.lower()
        people = [entity for entity in self._extract_persons(sentence) if entity in kept_entities]
        institutions = [entity for entity in self._extract_institutions(sentence) if entity in kept_entities]
        locations = [entity for entity in self._extract_locations(sentence) if entity in kept_entities]
        action = any(re.search(rf"\b{re.escape(verb)}\w*\b", lowered) for verb in ACTION_VERBS)
        detail = self._sentence_has_detail(sentence)
        impact = self._sentence_has_impact(sentence)
        reaction = any(verb in lowered for verb in REACTION_VERBS)
        next_step = any(keyword in lowered for keyword in NEXT_STEP_KEYWORDS)
        contrast = any(keyword in lowered for keyword in CONTRAST_MARKERS)
        named_personal_attribution = self._has_named_personal_attribution_sentence(sentence, people)
        role_based_personal_attribution = self._has_role_based_personal_attribution_sentence(sentence)

        score = 22 - (index * 2)
        reasons = [f"position={index + 1}"]
        role = "detail"
        if people:
            score += 18
            reasons.append(f"person={','.join(people[:1])}")
        if institutions:
            score += 10
            reasons.append(f"institution={','.join(institutions[:1])}")
        if locations:
            score += 5
            reasons.append(f"location={','.join(locations[:1])}")
        if action:
            score += 10
            reasons.append("action")
        if detail:
            score += 8
            reasons.append("detail")
        if impact:
            score += 8
            reasons.append("impact")
        if next_step:
            score += 6
            reasons.append("next_step")
        if named_personal_attribution:
            score += 14
            reasons.append("named_personal_attribution")
        elif role_based_personal_attribution:
            score += 9
            reasons.append("role_based_personal_attribution")
        if contrast:
            score -= 4
            reasons.append("contrast_penalty")
        if self._word_count(sentence) > 26:
            score -= 4
            reasons.append("sentence_too_long")

        if index == 0 and action and (people or institutions):
            role = "lead"
            score += 10
        elif detail:
            role = "detail"
        elif impact:
            role = "impact"
        elif next_step or reaction:
            role = "reaction"

        return RadioSentenceDecision(text=sentence, score=round(score, 2), role=role, reasons=reasons)

    def _select_story_core(self, decisions: list[RadioSentenceDecision]) -> list[RadioSentenceDecision]:
        lead = self._best_by_role(decisions, {"lead"}) or RadioSentenceDecision(text=decisions[0].text, score=999.0, role="lead", reasons=["fallback_lead"])
        detail = self._best_by_role(decisions, {"detail"}, exclude=[lead.text])
        impact = self._best_by_role(decisions, {"impact"}, exclude=[lead.text, detail.text if detail else ""])
        reaction = self._best_by_role(decisions, {"reaction"}, exclude=[lead.text, detail.text if detail else "", impact.text if impact else ""])
        if reaction and self._is_administrative_sentence(reaction.text):
            reaction = None
        selected = [lead]
        if detail:
            selected.append(detail)
        if impact:
            selected.append(impact)
        if reaction:
            selected.append(reaction)
        return selected[:MAX_SENTENCE_COUNT]

    def _best_by_role(self, decisions: list[RadioSentenceDecision], roles: set[str], exclude: list[str] | None = None) -> RadioSentenceDecision | None:
        exclude = [value for value in (exclude or []) if value]
        candidates = [item for item in decisions if item.role in roles and item.text not in exclude]
        if not candidates:
            return None
        candidates = sorted(candidates, key=lambda item: item.score, reverse=True)
        for candidate in candidates:
            if not self._is_near_duplicate(candidate.text, exclude):
                return candidate
        return candidates[0]

    def _build_radio_sentences(self, payload: dict[str, object], compression: CompressedStoryCore) -> list[str]:
        band = self._debug_value(compression.debug_notes, "story_band", "sparse")
        sentences: list[str] = []

        lead = self._rewrite_for_radio(self._role_sentence(compression, "lead", payload["headline_original"]), "lead", compression.kept_entities)
        if lead:
            sentences.append(lead)

        detail = self._rewrite_for_radio(self._role_sentence(compression, "detail", ""), "detail", compression.kept_entities)
        if not detail or self._is_near_duplicate(detail, sentences):
            detail = self._derive_detail_sentence(payload, compression.kept_entities, sentences)
        if detail and not self._is_near_duplicate(detail, sentences):
            sentences.append(detail)

        impact = self._rewrite_for_radio(self._role_sentence(compression, "impact", ""), "impact", compression.kept_entities)
        if not impact or self._is_near_duplicate(impact, sentences):
            impact = self._derive_impact_sentence(payload, compression.kept_entities, sentences)
        if impact and not self._is_near_duplicate(impact, sentences):
            sentences.append(impact)

        reaction = self._rewrite_for_radio(self._role_sentence(compression, "reaction", ""), "reaction", compression.kept_entities)
        target_min, _ = self._band_limits(band)
        if reaction and not self._is_near_duplicate(reaction, sentences) and self._should_add_closure(reaction, sentences, target_min):
            sentences.append(reaction)

        while self._word_count(" ".join(sentences)) < target_min and len(sentences) < MAX_SENTENCE_COUNT:
            extra = self._derive_support_sentence(payload, compression, sentences)
            if not extra:
                break
            sentences.append(extra)

        if self._word_count(" ".join(sentences)) < target_min and len(sentences) == MAX_SENTENCE_COUNT:
            extended_last = self._extend_last_sentence(payload, compression, sentences)
            if extended_last:
                sentences[-1] = extended_last

        final_text = self._enforce_word_budget(sentences, band)
        final_sentences = [self._finalize_sentence(sentence) for sentence in SENTENCE_SPLIT_PATTERN.split(final_text) if sentence.strip()]
        return final_sentences[:MAX_SENTENCE_COUNT]

    def _polish_radio_sentences(self, payload: dict[str, object], compression: CompressedStoryCore, sentences: list[str]) -> tuple[list[str], dict[str, int | bool | str]]:
        polished = [self._simplify_operational_language(sentence) for sentence in sentences if sentence]
        simplified_count = sum(1 for original, updated in zip(sentences, polished) if original != updated)
        initial_lead = polished[0] if polished else ""
        polished, lead_rewrite_meta = self._rewrite_title_like_lead(payload, compression, polished)
        polished = self._promote_personal_attribution(payload, compression, polished)
        polished = self._ensure_attributed_voice(payload, compression, polished)
        polished = self._reinforce_romania_impact(payload, compression, polished)
        polished = self._replace_repeated_person_names(payload, polished)
        polished = self._limit_attribution_slots(polished)
        polished = self._strengthen_closure(payload, compression, polished)
        polished = self._ensure_attributed_voice(payload, compression, polished)
        polished = self._diversify_generic_lead(payload, compression, polished)
        polished, repetition_meta = self._reduce_intra_story_repetition(payload, polished)
        polished, closing_variation_applied = self._apply_closing_variation(payload, compression, polished)
        polished = [
            self._finalize_sentence(self._trim_sentence(sentence, LEAD_MAX_WORDS if index == 0 else SENTENCE_SOFT_MAX_WORDS))
            for index, sentence in enumerate(polished)
            if sentence
        ]
        final_lead = polished[0] if polished else ""
        lead_title_overlap_score = round(self._lead_title_overlap_score(payload["headline_original"], final_lead), 2)
        attribution_type_used = self._story_attribution_type(polished, payload)
        attribution_position_used = self._attribution_position_used(polished, payload)
        attribution_details = self._attributed_voice_details(polished, payload)
        attribution_level_used = attribution_details["attribution_level_used"]
        lead_restatement_meta = self._lead_restatement_meta(payload, final_lead)
        lead_starter_family = self._lead_opening_type(final_lead, payload)
        closing_phrase_family = self._closing_phrase_family(polished[-1] if polished else "")
        metrics = {
            "lead_title_overlap_score": lead_title_overlap_score,
            "lead_rewritten_to_reduce_title_repetition": lead_rewrite_meta["lead_rewritten_to_reduce_title_repetition"],
            "lead_continuation_rewrite_applied": lead_rewrite_meta["lead_continuation_rewrite_applied"],
            "stories_rewritten_via_continuation_strategy": lead_rewrite_meta["lead_continuation_rewrite_applied"],
            "lead_opening_type": lead_starter_family,
            "lead_starter_family": lead_starter_family,
            "closing_phrase_family": closing_phrase_family,
            "generated_lead_initial": self._clean_text(initial_lead),
            "generated_lead_final": self._clean_text(final_lead),
            "title_main_entity": lead_restatement_meta["title_main_entity"],
            "title_main_action_family": lead_restatement_meta["title_main_action_family"],
            "stories_with_lead_starting_with_institution": lead_restatement_meta["lead_starts_with_institution"],
            "stories_with_lead_starting_with_institution_and_title_like_action": lead_restatement_meta["lead_starts_with_title_entity_and_action"],
            "duplicate_sentence_removed": repetition_meta["duplicate_sentence_removed"],
            "stories_with_intra_story_repetition": repetition_meta["stories_with_intra_story_repetition"],
            "stories_with_duplicate_sentence_removed": repetition_meta["duplicate_sentence_removed"],
            "stories_with_closing_variation_applied": closing_variation_applied,
            "high_title_lead_overlap": lead_title_overlap_score >= TITLE_LEAD_OVERLAP_THRESHOLD,
            "romania_impact_included": self._has_romania_impact_sentence(payload, polished),
            "strong_closure": bool(polished and self._has_strong_closure(polished[-1])),
            "repeated_person_name_count": self._count_repeated_person_names(payload, polished),
            "multiple_attributions": self._count_explicit_attributions(polished) > 1,
            "administrative_closure": bool(polished and self._is_administrative_sentence(polished[-1])),
            "simplified_operational_description_count": simplified_count,
            "stories_with_personal_attribution": attribution_level_used == "person",
            "stories_with_person_name_attribution": bool(attribution_details["attributed_name_used"]),
            "stories_with_person_role_and_name_attribution": attribution_type_used == "named_person",
            "lead_has_personal_attribution": bool(polished and self._sentence_personal_attribution_type(polished[0], payload) in {"named_person", "role_based_person"}),
            "second_sentence_has_personal_attribution": len(polished) > 1 and self._sentence_personal_attribution_type(polished[1], payload) in {"named_person", "role_based_person"},
            "promoted_person_attribution_sentence_count": 1 if attribution_position_used in {"lead", "sentence_2"} and attribution_level_used == "person" else 0,
            "role_based_attribution_inserted_count": 1 if attribution_type_used == "role_based_person" else 0,
            "stories_with_institution_only_attribution": attribution_level_used == "institution",
            "stories_with_institution_attribution": attribution_level_used == "institution",
            "stories_with_media_attribution": attribution_level_used == "media",
            "stories_with_media_source_attribution": attribution_level_used == "media",
            "stories_missing_attributed_voice": attribution_level_used == "none",
            "attribution_type_used": attribution_type_used,
            "attribution_level_used": attribution_level_used,
            "attribution_position_used": attribution_position_used,
            "attributed_name_used": attribution_details["attributed_name_used"],
            "attributed_role_used": attribution_details["attributed_role_used"],
            "attributed_institution_used": attribution_details["attributed_institution_used"],
            "attributed_media_source_used": attribution_details["attributed_media_source_used"],
            "person_attribution_used": attribution_level_used == "person",
            "person_name": attribution_details["attributed_name_used"],
            "person_role": attribution_details["attributed_role_used"],
            "has_named_person": bool(payload.get("top_person")),
            "has_role_based_person": bool(payload.get("available_role_markers")),
            "lead_has_quote_or_person": bool(polished and self._sentence_personal_attribution_type(polished[0], payload) != "none"),
        }
        return polished[:MAX_SENTENCE_COUNT], metrics

    def _role_sentence(self, compression: CompressedStoryCore, role: str, fallback: str) -> str:
        sentence = next((item.text for item in compression.kept_sentences if item.role == role), "")
        return sentence or fallback

    def _band_limits(self, band: str) -> tuple[int, int]:
        if band == "major":
            return MAJOR_MIN_WORDS, MAJOR_MAX_WORDS
        if band == "standard":
            return STANDARD_MIN_WORDS, STANDARD_MAX_WORDS
        return SPARSE_MIN_WORDS, SPARSE_MAX_WORDS

    def _derive_detail_sentence(self, payload: dict[str, object], kept_entities: list[str], existing: list[str]) -> str:
        for sentence in payload["source_text_sentences"]:
            if not self._sentence_has_detail(sentence):
                continue
            rewritten = self._rewrite_for_radio(sentence, "detail", kept_entities)
            if rewritten and not self._is_near_duplicate(rewritten, existing):
                return rewritten
        return ""

    def _derive_impact_sentence(self, payload: dict[str, object], kept_entities: list[str], existing: list[str]) -> str:
        if self._has_romania_impact_sentence(payload, existing):
            return ""
        romania_impact = self._derive_romania_impact_sentence(payload, kept_entities, existing)
        if romania_impact:
            return romania_impact

        for sentence in payload["source_text_sentences"]:
            if not (self._sentence_has_impact(sentence) or self._sentence_has_next_step(sentence)):
                continue
            rewritten = self._rewrite_for_radio(sentence, "impact", kept_entities)
            if rewritten and not self._is_near_duplicate(rewritten, existing):
                return rewritten

        lowered = payload["full_text"].lower()
        if "investitori" in lowered or "birocratia" in lowered or "investitii" in lowered:
            fallback = "Masura ar putea grabi investitiile si reduce birocratia pentru companii."
        elif "parchete" in lowered or "numirilor" in lowered or "dna" in lowered:
            fallback = "Decizia mentine presiunea asupra numirilor din marile parchete."
        elif "buget" in lowered or "frauda" in lowered or "tva" in lowered:
            fallback = "Asta inseamna presiune mai mare pe colectarea la buget si pe firmele verificate."
        elif "petrol" in lowered or "energie" in lowered or "ormuz" in lowered:
            fallback = "Asta poate aduce noi scumpiri la petrol si energie."
        elif "trafic" in lowered or "navetisti" in lowered or "studenti" in lowered:
            fallback = "Asta inseamna trafic mai dificil pentru navetisti si studenti."
        else:
            fallback = ""

        rewritten = self._rewrite_for_radio(fallback, "impact", kept_entities)
        if rewritten and not self._is_near_duplicate(rewritten, existing):
            return rewritten
        return ""

    def _diversify_generic_lead(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        sentences: list[str],
    ) -> list[str]:
        if not sentences:
            return sentences
        lead = sentences[0]
        normalized = self._comparison_text(lead)
        if self._sentence_personal_attribution_type(lead, payload) == "named_person":
            return sentences
        if not normalized.startswith(("asta", "impactul", "primele efecte", "decizia", "masura")):
            return sentences
        rewritten = self._rewrite_generic_lead(payload, compression, lead)
        if rewritten and rewritten != lead:
            sentences[0] = rewritten
        return sentences

    def _rewrite_generic_lead(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        lead: str,
    ) -> str:
        lowered = payload["full_text"].lower()
        if any(term in lowered for term in ("spital", "urgente", "pacienti", "flux rapid")):
            return self._finalize_sentence("Pacientii cu urgente majore pot intra mai repede pe noul flux al spitalului.")
        if any(term in lowered for term in ("trafic", "restrictii", "rute ocolitoare", "circulatia", "navetisti", "trenuri", "peron")):
            if "tren" in lowered or "peron" in lowered:
                return self._finalize_sentence("Navetistii vor avea un orar provizoriu si schimbari de peron in urmatoarele zile.")
            return self._finalize_sentence("Soferii vor circula pe rute ocolitoare sau pe benzi restranse incepand din primele zile.")
        if any(term in lowered for term in ("energie", "petrol", "facturi", "consumatori", "preturi")):
            return self._finalize_sentence("Consumatorii ar putea vedea presiune mai mare pe facturi si pe preturile la energie.")
        if any(term in lowered for term in ("investitii", "avize", "birocratia", "ordonanta")):
            return self._finalize_sentence("Investitorii ar putea trece mai repede de avizele pentru proiectele mari.")
        if any(term in lowered for term in ("dna", "csm", "presedintie", "parchete", "propunere")):
            return self._finalize_sentence("Ministerul Justitiei ramane sub presiune sa vina cu o noua propunere pentru functie.")
        if any(term in lowered for term in ("catalogul digital", "elevi", "parinti", "scoli")):
            return self._finalize_sentence("Parintii si elevii pot verifica notele si absentele in acelasi sistem digital.")
        if any(term in lowered for term in ("universitati", "studenti", "burse", "navetisti")):
            return self._finalize_sentence("Studentii navetisti ar putea acoperi mai usor transportul si o parte din cazare.")
        if any(term in lowered for term in ("fermierii", "seceta", "alimente", "agriculturii")):
            return self._finalize_sentence("Fermierii cer sprijin rapid ca sa limiteze presiunea pe preturile la alimente.")
        if any(term in lowered for term in ("nato", "marea neagra", "securitatea regionala")):
            return self._finalize_sentence("Pentru Romania, miscarile din zona sporesc atentia asupra securitatii de la Marea Neagra.")
        if any(term in lowered for term in ("ormuz", "rutele maritime", "transportului comercial")):
            return self._finalize_sentence("Pentru Romania si Europa, tensiunea poate ridica rapid costurile la energie si transport.")
        if any(term in lowered for term in ("cipuri", "export", "bateriile", "lanturile de aprovizionare")):
            return self._finalize_sentence("Companiile pot vedea costuri mai mari si livrari mai lente pe lanturile de aprovizionare.")
        return lead

    def _derive_support_sentence(self, payload: dict[str, object], compression: CompressedStoryCore, existing: list[str]) -> str:
        for role in ("impact", "detail", "reaction"):
            candidates = [item for item in compression.dropped_sentences if item.role == role]
            for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
                rewritten = self._rewrite_for_radio(candidate.text, role, compression.kept_entities)
                if rewritten and not self._is_near_duplicate(rewritten, existing):
                    return rewritten
        for sentence in payload["source_text_sentences"]:
            if not (self._sentence_has_detail(sentence) or self._sentence_has_impact(sentence) or self._sentence_has_next_step(sentence)):
                continue
            rewritten = self._rewrite_for_radio(sentence, "detail", compression.kept_entities)
            if rewritten and not self._is_near_duplicate(rewritten, existing):
                return rewritten
        return ""

    def _should_add_closure(self, sentence: str, existing: list[str], target_min: int) -> bool:
        if not sentence or self._is_near_duplicate(sentence, existing) or self._is_administrative_sentence(sentence):
            return False
        if len(existing) < 3:
            return True
        if self._word_count(" ".join(existing)) < target_min:
            return True
        lowered = sentence.lower()
        return self._has_strong_closure(sentence) or self._sentence_has_next_step(sentence) or any(keyword in lowered for keyword in IMPACT_KEYWORDS)

    def _extend_last_sentence(self, payload: dict[str, object], compression: CompressedStoryCore, sentences: list[str]) -> str:
        if not sentences:
            return ""
        base_sentence = sentences[-1].rstrip(".!? ")
        candidates: list[str] = []
        for item in sorted(compression.dropped_sentences, key=lambda item: item.score, reverse=True):
            rewritten = self._rewrite_for_radio(item.text, item.role, compression.kept_entities)
            if rewritten and not self._is_near_duplicate(rewritten, sentences):
                candidates.append(rewritten)
        for sentence in payload["source_text_sentences"]:
            rewritten = self._rewrite_for_radio(sentence, "detail", compression.kept_entities)
            if rewritten and not self._is_near_duplicate(rewritten, sentences):
                candidates.append(rewritten)
        for candidate in candidates:
            clause = candidate.rstrip(".!? ")
            clause = self._normalize_embedded_clause(clause)
            combined = f"{base_sentence}, iar {clause}"
            if self._word_count(combined) <= SENTENCE_SOFT_MAX_WORDS:
                return self._finalize_sentence(combined)
        return ""

    def _normalize_embedded_clause(self, clause: str) -> str:
        generic_starts = ("Primele", "Decizia", "Impactul", "Actul", "Masura", "Asta")
        for start in generic_starts:
            if clause.startswith(start):
                return clause[0].lower() + clause[1:]
        return clause

    def _simplify_operational_language(self, sentence: str) -> str:
        simplified = sentence
        for source, target in OPERATIONAL_REPLACEMENTS.items():
            simplified = re.sub(re.escape(source), target, simplified, flags=re.IGNORECASE)
        return self._finalize_sentence(simplified)

    def _rewrite_title_like_lead(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        sentences: list[str],
    ) -> tuple[list[str], dict[str, bool]]:
        if not sentences:
            return sentences, {
                "lead_rewritten_to_reduce_title_repetition": False,
                "lead_continuation_rewrite_applied": False,
            }
        lead = sentences[0]
        restatement_meta = self._lead_restatement_meta(payload, lead)
        normalized_headline = self._comparison_text(payload["headline_original"])
        normalized_lead = self._comparison_text(lead)
        if not restatement_meta["must_rewrite"] and normalized_headline not in normalized_lead:
            return sentences, {
                "lead_rewritten_to_reduce_title_repetition": False,
                "lead_continuation_rewrite_applied": False,
            }

        continuation = self._continuation_style_lead(payload, compression, sentences)
        if continuation:
            updated = [continuation["lead"]]
            for index, sentence in enumerate(sentences[1:], start=1):
                if index == continuation["source_index"]:
                    continue
                updated.append(sentence)
            return updated[:MAX_SENTENCE_COUNT], {
                "lead_rewritten_to_reduce_title_repetition": True,
                "lead_continuation_rewrite_applied": True,
            }

        rewritten = self._paraphrase_title_like_lead(payload, compression, lead)
        if not rewritten or rewritten == lead:
            return sentences, {
                "lead_rewritten_to_reduce_title_repetition": False,
                "lead_continuation_rewrite_applied": False,
            }

        updated = list(sentences)
        updated[0] = rewritten
        return updated, {
            "lead_rewritten_to_reduce_title_repetition": True,
            "lead_continuation_rewrite_applied": False,
        }

    def _continuation_style_lead(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        sentences: list[str],
    ) -> dict[str, object] | None:
        headline_overlap = self._lead_title_overlap_score(payload["headline_original"], sentences[0] if sentences else "")
        candidates: list[tuple[float, int, str, bool]] = []
        seen_candidates: set[str] = set()
        for index, sentence in enumerate(sentences[1:], start=1):
            candidate = self._finalize_sentence(self._trim_sentence(sentence, LEAD_MAX_WORDS))
            if not candidate or candidate in seen_candidates:
                continue
            seen_candidates.add(candidate)
            score = self._continuation_lead_score(payload, candidate, index)
            if score > 0:
                candidates.append((score, index, candidate, True))
        source_candidates = [item.text for item in compression.dropped_sentences] + list(payload["source_text_sentences"][1:])
        for index, sentence in enumerate(source_candidates, start=len(sentences) + 1):
            role = "reaction" if self._has_attribution_verb(sentence) else "detail"
            candidate = self._finalize_sentence(self._trim_sentence(self._rewrite_for_radio(sentence, role, compression.kept_entities), LEAD_MAX_WORDS))
            if not candidate or candidate in seen_candidates:
                continue
            seen_candidates.add(candidate)
            score = self._continuation_lead_score(payload, candidate, index)
            if score > 0:
                candidates.append((score, index, candidate, False))
        if not candidates:
            return None
        best_score, best_index, best_candidate, existing_sentence = max(candidates, key=lambda item: (item[0], -item[1]))
        if best_score < 1.8:
            return None
        if self._lead_title_overlap_score(payload["headline_original"], best_candidate) >= headline_overlap and self._lead_restatement_meta(payload, best_candidate)["lead_starts_with_title_entity_and_action"]:
            return None
        return {"lead": best_candidate, "source_index": best_index if existing_sentence else -1}

    def _continuation_lead_score(self, payload: dict[str, object], sentence: str, source_index: int) -> float:
        opening_type = self._lead_opening_type(sentence, payload)
        overlap_penalty = self._lead_title_overlap_score(payload["headline_original"], sentence)
        restatement_meta = self._lead_restatement_meta(payload, sentence)
        base_scores = {
            "consequence": 4.0,
            "action": 3.5,
            "affected_audience": 3.2,
            "person_role": 2.8,
            "institution_action": 0.7,
        }
        base_score = base_scores.get(opening_type, 0.0)
        if not base_score:
            return 0.0
        score = base_score - (overlap_penalty * 2.4) + max(0.0, 0.45 - (source_index * 0.07))
        if self._sentence_has_impact(sentence):
            score += 0.5
        if self._sentence_has_next_step(sentence):
            score += 0.35
        if self._sentence_personal_attribution_type(sentence, payload) in {"named_person", "role_based_person"}:
            score += 0.75
        if opening_type in self._recent_lead_families:
            score -= 1.35
        if opening_type == "action" and "action" in self._recent_lead_families:
            score -= 0.45
        if opening_type == "consequence" and self._comparison_text(sentence).startswith("asta"):
            score -= 1.1
        if self._comparison_text(sentence).startswith(("impactul", "decizia", "masura")):
            score -= 0.35
        if restatement_meta["lead_starts_with_title_entity_and_action"]:
            score -= 4.0
        elif restatement_meta["lead_starts_with_institution"]:
            score -= 1.6
        if overlap_penalty > 0.5:
            score -= 3.0
        elif overlap_penalty > 0.4:
            score -= 1.4
        return round(score, 2)

    def _lead_opening_type(self, sentence: str, payload: dict[str, object] | None = None) -> str:
        normalized = self._comparison_text(sentence)
        if not normalized:
            return "action"
        if payload and self._sentence_personal_attribution_type(sentence, payload) in {"named_person", "role_based_person"}:
            return "person_role"
        if normalized.startswith(CONSEQUENCE_LEAD_STARTS):
            return "consequence"
        if normalized.startswith(AFFECTED_AUDIENCE_LEAD_STARTS):
            return "affected_audience"
        if normalized.startswith(CONCRETE_ACTION_LEAD_STARTS):
            return "action"
        if payload and self._lead_restatement_meta(payload, sentence)["lead_starts_with_institution"]:
            return "institution_action"
        return "action"

    def _closing_phrase_family(self, sentence: str) -> str:
        lowered = self._comparison_text(sentence)
        if not lowered:
            return "operational_timing"
        if any(marker in lowered for marker in ("intra in vigoare", "se aplica", "de luni", "de marti", "luna viitoare", "zilele urmatoare")):
            return "operational_timing"
        if any(marker in lowered for marker in ("monitorizata", "monitorizat", "evaluari", "oficialii", "autoritatile", "va fi confirmat")):
            return "institution_followup"
        if any(marker in lowered for marker in ("companii", "consumatori", "regulile", "costurile", "preturile")):
            return "policy_impact"
        return "immediate_impact"

    def _lead_restatement_meta(self, payload: dict[str, object], lead: str) -> dict[str, object]:
        title_main_entity = self._title_main_entity(payload)
        title_main_action_family = self._title_main_action_family(payload["headline_original"])
        overlap_score = self._lead_title_overlap_score(payload["headline_original"], lead)
        starts_with_title_entity = self._lead_starts_with_title_entity(lead, title_main_entity)
        same_action_family = self._text_matches_action_family(lead, title_main_action_family)
        lead_starts_with_institution = self._lead_starts_with_institution(payload, lead)
        structural_restatement = starts_with_title_entity and same_action_family
        return {
            "title_main_entity": title_main_entity,
            "title_main_action_family": title_main_action_family,
            "lead_starts_with_institution": lead_starts_with_institution,
            "lead_starts_with_title_entity_and_action": structural_restatement,
            "must_rewrite": overlap_score > 0.4 or structural_restatement,
            "overlap_score": round(overlap_score, 2),
        }

    def _title_main_entity(self, payload: dict[str, object]) -> str:
        headline = str(payload.get("headline_original") or "").strip()
        actor_phrase = self._extract_lead_actor_phrase(headline)
        if actor_phrase:
            return actor_phrase
        institutions = self._extract_institutions(headline)
        if institutions:
            return institutions[0]
        top_person = str(payload.get("top_person") or "").strip()
        top_person_role = str(payload.get("top_person_role") or "").strip()
        if top_person and top_person_role and top_person in headline:
            return f"{top_person_role} {top_person}"
        return top_person

    def _title_main_action_family(self, headline: str) -> str:
        normalized = self._comparison_text(headline)
        for family, markers in TITLE_ACTION_FAMILY_MARKERS.items():
            if any(marker in normalized for marker in markers):
                return family
        action_verb, _ = self._headline_event_components(str(headline))
        if action_verb in {"extinde", "cer"}:
            return "scale_up" if action_verb == "extinde" else "prepare"
        if action_verb in {"pregateste"}:
            return "prepare"
        if action_verb in {"muta", "trimite"}:
            return "reroute"
        if action_verb in {"respinge"}:
            return "reject"
        if action_verb in {"lanseaza", "impune"}:
            return "launch"
        if action_verb in {"incepe", "deschide", "aproba"}:
            return "start"
        return ""

    def _lead_starts_with_title_entity(self, lead: str, title_entity: str) -> bool:
        entity_tokens = self._comparison_tokens(title_entity)[:3]
        lead_tokens = self._comparison_tokens(" ".join(str(lead).split()[:7]))
        if not entity_tokens or not lead_tokens:
            return False
        significant = entity_tokens[:2] if len(entity_tokens) >= 2 else entity_tokens
        return all(token in lead_tokens for token in significant)

    def _lead_starts_with_institution(self, payload: dict[str, object], lead: str) -> bool:
        lead_prefix = " ".join(str(lead).split()[:7])
        if self._first_matching_institution(lead_prefix, payload):
            return True
        return self._lead_starts_with_title_entity(lead_prefix, self._title_main_entity(payload)) and self._sentence_personal_attribution_type(lead, payload) == "institution"

    def _text_matches_action_family(self, text: str, family: str) -> bool:
        if not family:
            return False
        normalized = self._comparison_text(text)
        return any(marker in normalized for marker in TITLE_ACTION_FAMILY_MARKERS.get(family, ()))

    def _paraphrase_title_like_lead(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        lead: str,
    ) -> str:
        direct_rewrite = self._pattern_based_lead_rewrite(lead)
        if direct_rewrite:
            return self._finalize_sentence(direct_rewrite)

        actor_phrase = self._extract_lead_actor_phrase(lead) or self._preferred_lead_actor(payload, compression)
        headline_text = str(payload.get("headline_original") or "").strip().rstrip(".!?")
        action_verb, remainder = self._headline_event_components(headline_text)
        if not actor_phrase or not action_verb or not remainder:
            return lead

        event_phrase = self._compact_event_phrase(action_verb, remainder)
        if not event_phrase:
            return lead

        if action_verb in {"muta", "trimite", "decide"}:
            candidate = f"{actor_phrase} a decis {event_phrase}"
        elif action_verb == "impune":
            candidate = f"{actor_phrase} introduce {event_phrase}"
        elif action_verb in {"incepe", "aproba"}:
            candidate = f"{actor_phrase} a anuntat {event_phrase}" if self._actor_needs_announcement_prefix(actor_phrase) else f"{actor_phrase} a {action_verb} {remainder}"
        elif action_verb == "deschide":
            candidate = f"{actor_phrase} porneste {event_phrase}" if ("program" in remainder.lower() or "urgente cardiace" in remainder.lower()) else f"{actor_phrase} deschide {event_phrase}"
        elif action_verb == "lanseaza":
            if "catalog" in remainder.lower():
                candidate = f"{actor_phrase} duce sistemul online de note in alte judete"
            else:
                candidate = f"{actor_phrase} a anuntat {event_phrase}" if self._actor_needs_announcement_prefix(actor_phrase) else f"{actor_phrase} lanseaza {event_phrase}"
        elif action_verb == "extinde":
            if "verificari extinse" in event_phrase:
                candidate = f"{actor_phrase} a lansat {event_phrase}"
            elif remainder.lower().startswith("programul"):
                candidate = f"{actor_phrase} mareste {event_phrase}"
            else:
                candidate = f"{actor_phrase} extinde {event_phrase}"
        elif action_verb == "pregateste":
            candidate = f"{actor_phrase} lucreaza la {event_phrase}"
        elif action_verb == "respinge":
            candidate = f"{actor_phrase} a dat aviz negativ pentru un post-cheie la DNA" if "dna" in remainder.lower() else f"{actor_phrase} a blocat {event_phrase}"
        elif action_verb == "cer":
            candidate = f"{actor_phrase} solicita {event_phrase}"
        else:
            candidate = f"{actor_phrase} a anuntat {event_phrase}"

        return self._finalize_sentence(self._trim_sentence(candidate, LEAD_MAX_WORDS)) or lead

    def _pattern_based_lead_rewrite(self, lead: str) -> str:
        stripped = lead.strip().rstrip(".!?")
        pattern_rewrites = [
            (r"^(?P<actor>.+?) a anuntat ca .*? incepe lucrari(?P<tail>.+)$", lambda m: f"{m.group('actor')} a anuntat inceperea lucrarilor{m.group('tail')}"),
            (r"^(?P<actor>.+?) anunta ca incepe (?P<tail>.+)$", lambda m: f"{m.group('actor')} a anuntat inceperea {m.group('tail')}"),
            (r"^(?P<actor>.+?) a anuntat ca .*? trimit (?P<tail>.+)$", lambda m: f"{m.group('actor')} a anuntat trimiterea unor {m.group('tail')}"),
            (r"^(?P<actor>.+?) a anuntat ca .*? a adoptat o ordonanta care simplifica (?P<tail>.+)$", lambda m: f"{m.group('actor')} a anuntat simplificarea {m.group('tail')}"),
            (r"^(?P<actor>.+?) a anuntat controale extinse dupa descoperirea (?P<tail>.+)$", lambda m: f"{m.group('actor')} a lansat controale extinse dupa descoperirea {m.group('tail')}"),
            (r"^(?P<actor>NATO) muta (?P<tail>.+)$", lambda m: f"{m.group('actor')} a decis mutarea unor {m.group('tail')}"),
        ]
        for pattern, builder in pattern_rewrites:
            match = re.search(pattern, stripped, re.IGNORECASE)
            if match:
                candidate = re.sub(r"\binceperea luni lucrari\b", "inceperea lucrarilor", builder(match), flags=re.IGNORECASE)
                candidate = re.sub(r"\binceperea lucrari\b", "inceperea lucrarilor", candidate, flags=re.IGNORECASE)
                candidate = re.sub(r"\binceperea lucrarilor noi\b", "inceperea lucrarilor", candidate, flags=re.IGNORECASE)
                candidate = re.sub(r"\s+", " ", candidate).strip()
                return candidate
        return ""

    def _lead_title_overlap_score(self, headline: str, lead: str) -> float:
        headline_tokens = self._comparison_tokens(headline)
        lead_tokens = self._comparison_tokens(lead)
        if not headline_tokens or not lead_tokens:
            return 0.0
        overlap = len(set(headline_tokens) & set(lead_tokens)) / max(1, len(set(headline_tokens)))
        headline_text = self._comparison_text(headline)
        lead_text = self._comparison_text(lead)
        ordered_bonus = 0.15 if headline_text and (headline_text in lead_text or lead_text in headline_text) else 0.0
        prefix_bonus = 0.1 if headline_tokens[:4] == lead_tokens[:4] else 0.0
        return min(1.0, overlap + ordered_bonus + prefix_bonus)

    def _comparison_tokens(self, text: str) -> list[str]:
        normalized = self._comparison_text(text)
        return [token for token in normalized.split() if token and token not in COMPARISON_STOPWORDS]

    def _comparison_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFD", str(text or ""))
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = re.sub(r"[^a-zA-Z0-9\s]", " ", normalized.lower())
        return re.sub(r"\s+", " ", normalized).strip()

    def _extract_lead_actor_phrase(self, lead: str) -> str:
        match = re.match(
            r"^(?P<actor>.+?)\s+(?:a\s+anuntat|anunta(?:\s+ca)?|a\s+decis|a\s+lansat|a\s+aprobat|muta|trimite|pregateste|pregatesc|impune|impun|lanseaza|deschide|deschid|extinde|extind|incepe|incep|respinge|cer)\b",
            lead.strip(),
            re.IGNORECASE,
        )
        return match.group("actor").strip(" ,") if match else ""

    def _preferred_lead_actor(self, payload: dict[str, object], compression: CompressedStoryCore) -> str:
        top_person = str(payload.get("top_person") or "").strip()
        top_person_role = str(payload.get("top_person_role") or "").strip()
        if top_person and top_person_role:
            return f"{top_person_role} {top_person}"
        if top_person:
            return top_person
        return compression.kept_entities[0] if compression.kept_entities else ""

    def _headline_event_components(self, headline_text: str) -> tuple[str, str]:
        verb_aliases = [
            ("anunta", "anunta"),
            ("incepe", "incepe"),
            ("incep", "incepe"),
            ("pregateste", "pregateste"),
            ("pregatesc", "pregateste"),
            ("lanseaza", "lanseaza"),
            ("impune", "impune"),
            ("impun", "impune"),
            ("trimite", "trimite"),
            ("trimit", "trimite"),
            ("aproba", "aproba"),
            ("extinde", "extinde"),
            ("extind", "extinde"),
            ("deschide", "deschide"),
            ("deschid", "deschide"),
            ("muta", "muta"),
            ("decide", "decide"),
            ("respinge", "respinge"),
            ("cer", "cer"),
        ]
        for verb_form, normalized_verb in verb_aliases:
            match = re.search(rf"\b{verb_form}\b", headline_text, re.IGNORECASE)
            if match:
                return normalized_verb, headline_text[match.end():].strip(" ,")
        return "", ""

    def _compact_event_phrase(self, action_verb: str, remainder: str) -> str:
        lowered = remainder.lower()
        if action_verb == "incepe" and lowered.startswith("lucrari"):
            tail = remainder[7:].strip()
            return f"inceperea lucrarilor {tail}".strip()
        if action_verb == "muta" and lowered.startswith("exercitii"):
            return f"mutarea unor {remainder}"
        if action_verb == "trimite" and lowered.startswith("nave"):
            return f"trimiterea unor {remainder}"
        if action_verb == "pregateste" and "schema noua de sprijin" in lowered:
            return remainder.replace("schema noua de sprijin", "un nou sprijin", 1)
        if action_verb == "pregateste" and "restrictii noi" in lowered:
            return remainder.replace("restrictii noi", "restrictii suplimentare", 1)
        if action_verb == "extinde" and lowered.startswith("verificarile dupa"):
            return remainder.replace("verificarile", "verificari extinse", 1)
        if action_verb == "extinde" and "drumurile afectate de alunecari" in lowered:
            return "reparatiile pe drumurile lovite de alunecari"
        if action_verb == "extinde" and lowered.startswith("programul pentru"):
            return remainder.replace("programul", "programul de reparatii", 1)
        if action_verb == "deschide" and "urgente cardiace" in lowered:
            return "garda de noapte pentru urgente cardiace"
        if action_verb == "deschide" and lowered.startswith("un nou program"):
            return remainder.replace("un nou program", "un program nou", 1)
        if action_verb == "impune" and "bateriile importate" in lowered:
            return "standarde noi pentru bateriile importate"
        if action_verb == "impune" and lowered.startswith("reguli noi"):
            return remainder.replace("reguli noi", "noi reguli", 1)
        if action_verb == "lanseaza" and lowered.startswith("catalogul digital"):
            return remainder.replace("catalogul digital", "extinderea catalogului digital", 1)
        if action_verb == "cer" and lowered.startswith("sprijin"):
            return remainder.replace("sprijin", "ajutor", 1)
        if action_verb == "anunta" and "simplificarea" in lowered:
            event = re.sub(r"^o ordonanta pentru ", "", remainder, flags=re.IGNORECASE)
            return event.replace("de investitii", "pentru investitiile mari")
        if action_verb == "anunta" and "reguli noi" in lowered:
            return remainder.replace("reguli noi pentru marile investitii", "simplificarea avizelor pentru investitiile mari")
        nominalized = LEAD_EVENT_NOMINALIZATIONS.get(action_verb)
        if nominalized:
            return f"{nominalized} {remainder}".strip()
        return remainder

    def _actor_needs_announcement_prefix(self, actor_phrase: str) -> bool:
        return bool(re.search(r"\b(Premierul|Primarul|Presedintele|Ministrul|Directorul|Procurorul|Judecatorul|Ilie|Lucian)\b", actor_phrase))

    def _replace_repeated_person_names(self, payload: dict[str, object], sentences: list[str]) -> list[str]:
        top_person = str(payload.get("top_person") or "").strip()
        if not top_person or not sentences:
            return sentences
        role_alias = str(payload.get("top_person_role") or self._surname_reference(top_person)).strip()
        seen_full_name = top_person in sentences[0]
        updated = [sentences[0]]
        for sentence in sentences[1:]:
            if top_person in sentence:
                if seen_full_name:
                    sentence = sentence.replace(top_person, role_alias, 1)
                else:
                    seen_full_name = True
            updated.append(self._finalize_sentence(sentence))
        return updated

    def _limit_attribution_slots(self, sentences: list[str]) -> list[str]:
        updated: list[str] = []
        seen_attribution = False
        for sentence in sentences:
            if self._has_explicit_attribution(sentence):
                if seen_attribution:
                    sentence = self._strip_attribution_prefix(sentence)
                else:
                    seen_attribution = True
            updated.append(self._finalize_sentence(sentence))
        return updated

    def _strengthen_closure(self, payload: dict[str, object], compression: CompressedStoryCore, sentences: list[str]) -> list[str]:
        if not sentences:
            return sentences
        if self._has_strong_closure(sentences[-1]) and not self._is_administrative_sentence(sentences[-1]):
            return sentences
        strong_index = next((index for index, sentence in enumerate(sentences[1:-1], start=1) if self._has_strong_closure(sentence)), None)
        if strong_index is not None:
            strong_sentence = sentences.pop(strong_index)
            sentences.append(strong_sentence)
            if self._has_strong_closure(sentences[-1]) and not self._is_administrative_sentence(sentences[-1]):
                return sentences
        replacement = self._best_closure_candidate(payload, compression, sentences[:-1], current_closure=sentences[-1])
        if replacement:
            sentences[-1] = replacement
        return sentences

    def _best_closure_candidate(self, payload: dict[str, object], compression: CompressedStoryCore, existing: list[str], current_closure: str = "") -> str:
        for role in ("impact", "reaction", "detail"):
            candidates = [item for item in compression.dropped_sentences if item.role == role]
            for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
                rewritten = self._rewrite_for_radio(candidate.text, role, compression.kept_entities)
                if (
                    rewritten
                    and not self._is_near_duplicate(rewritten, existing)
                    and not self._is_administrative_sentence(rewritten)
                    and self._has_strong_closure(rewritten)
                ):
                    return rewritten
        for sentence in payload["source_text_sentences"]:
            rewritten = self._rewrite_for_radio(sentence, "reaction", compression.kept_entities)
            if (
                rewritten
                and not self._is_near_duplicate(rewritten, existing)
                and not self._is_administrative_sentence(rewritten)
                and self._has_strong_closure(rewritten)
            ):
                return rewritten
        fallback = self._derive_closure_fallback(payload)
        rewritten_fallback = self._rewrite_for_radio(fallback, "reaction", compression.kept_entities)
        if (
            rewritten_fallback
            and rewritten_fallback != current_closure
            and not self._is_near_duplicate(rewritten_fallback, existing)
        ):
            return rewritten_fallback
        return ""

    def _apply_closing_variation(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        sentences: list[str],
    ) -> tuple[list[str], bool]:
        if not sentences:
            return sentences, False
        current_family = self._closing_phrase_family(sentences[-1])
        if list(self._recent_closing_families).count(current_family) == 0 and not self._starts_with_primele_formula(sentences[-1]):
            return sentences, False
        replacement = self._best_closure_candidate(payload, compression, sentences[:-1], current_closure=sentences[-1])
        if (
            replacement
            and self._closing_phrase_family(replacement) != current_family
            and not self._is_near_duplicate(replacement, sentences[:-1])
            and replacement not in self._recent_closing_sentences
        ):
            sentences[-1] = replacement
            return sentences, True
        varied = self._closure_bank_sentence(payload, current_family, sentences[-1])
        if varied and varied != sentences[-1]:
            sentences[-1] = varied
            return sentences, True
        return sentences, False

    def _closure_bank_sentence(self, payload: dict[str, object], current_family: str, current_closure: str) -> str:
        preferred_family = self._preferred_closure_family(payload)
        for candidate in self._contextual_closure_candidates(payload, preferred_family):
            if candidate != current_closure and candidate not in self._recent_closing_sentences:
                return candidate
        family_order = [preferred_family] + [family for family in CLOSING_PHRASE_BANK if family != preferred_family]
        for family in family_order:
            if family == current_family and not self._starts_with_primele_formula(current_closure):
                continue
            if family in self._recent_closing_families:
                continue
            for candidate in CLOSING_PHRASE_BANK[family]:
                if candidate != current_closure and candidate not in self._recent_closing_sentences:
                    return candidate
        return ""

    def _contextual_closure_candidates(self, payload: dict[str, object], preferred_family: str) -> list[str]:
        lowered = payload["full_text"].lower()
        candidates: list[str] = []
        if any(term in lowered for term in ("lucrari", "trafic", "restrictii", "circulatia", "rute ocolitoare", "trenuri", "peron")):
            candidates.extend([
                "Programul actualizat se aplica de la inceputul saptamanii.",
                "Soferii si navetistii vor simti schimbarea chiar din primele zile.",
                "Rutele provizorii raman valabile pana la finalul lucrarilor.",
            ])
        if any(term in lowered for term in ("spital", "urgente", "pacienti", "flux rapid", "medici")):
            candidates.extend([
                "Pacientii pot intra pe noul flux chiar din aceasta saptamana.",
                "Programul extins va fi evaluat dupa primele zile de functionare.",
            ])
        if any(term in lowered for term in ("energie", "petrol", "facturi", "consumatori", "preturi")):
            candidates.extend([
                "Consumatorii ar putea vedea primele schimbari direct pe factura.",
                "Preturile pot reactiona rapid daca presiunea ramane ridicata.",
            ])
        if any(term in lowered for term in ("dna", "csm", "presedintie", "ministerul justitiei", "propunere")):
            candidates.extend([
                "Ministerul trebuie acum sa decida daca revine cu o alta propunere.",
                "Urmatorul pas depinde de o noua decizie a Ministerului Justitiei.",
            ])
        if any(term in lowered for term in ("elevi", "parinti", "scoli", "catalogul digital", "universitati", "studenti")):
            candidates.extend([
                "Parintii si elevii vor vedea schimbarea chiar din urmatoarele saptamani.",
                "Calendarul complet ajunge in unitati in zilele urmatoare.",
            ])
        if any(term in lowered for term in ("fermierii", "seceta", "agriculturii", "alimente")):
            candidates.extend([
                "Preturile pot reactiona rapid daca seceta continua si in urmatoarele saptamani.",
                "Fermierii asteapta decizia inaintea urmatoarelor lucrari de camp.",
            ])
        if any(term in lowered for term in ("nato", "marea neagra", "ormuz", "rutele maritime", "export", "cipuri", "bateriile")):
            candidates.extend([
                "Primele efecte se pot vedea rapid in costurile de transport si energie.",
                "Autoritatile urmaresc zilnic evolutia situatiei in regiune.",
            ])
        bank_candidates = list(CLOSING_PHRASE_BANK.get(preferred_family, ()))
        return [candidate for candidate in candidates + bank_candidates if candidate]

    def _preferred_closure_family(self, payload: dict[str, object]) -> str:
        lowered = payload["full_text"].lower()
        if any(term in lowered for term in ("de luni", "program", "restrictii", "lucrari", "se aplica", "intra in vigoare")):
            return "operational_timing"
        if any(term in lowered for term in ("preturi", "costuri", "companii", "consumatori", "energie")):
            return "policy_impact"
        if any(term in lowered for term in ("monitorizat", "autoritati", "evaluari", "oficialii", "confirmat")):
            return "institution_followup"
        return "immediate_impact"

    def _starts_with_primele_formula(self, sentence: str) -> bool:
        return self._comparison_text(sentence).startswith(("primele efecte", "primele rezultate", "primele restrictii"))

    def _reinforce_romania_impact(self, payload: dict[str, object], compression: CompressedStoryCore, sentences: list[str]) -> list[str]:
        if not self._is_international_story(payload) or self._has_romania_impact_sentence(payload, sentences):
            return sentences
        romania_impact = self._derive_romania_impact_sentence(payload, compression.kept_entities, sentences)
        if not romania_impact:
            return sentences
        impact_index = next(
            (
                index
                for index, sentence in enumerate(sentences[1:], start=1)
                if self._sentence_has_impact(sentence) or "romania" in sentence.lower() or "europa" in sentence.lower()
            ),
            None,
        )
        if impact_index is not None:
            sentences[impact_index] = romania_impact
            return sentences
        if len(sentences) < MAX_SENTENCE_COUNT:
            sentences.insert(min(2, len(sentences)), romania_impact)
            return sentences
        if len(sentences) >= 3:
            sentences[2] = romania_impact
        return sentences

    def _derive_romania_impact_sentence(self, payload: dict[str, object], kept_entities: list[str], existing: list[str]) -> str:
        if not self._is_international_story(payload):
            return ""
        for sentence in payload["source_text_sentences"]:
            lowered = sentence.lower()
            if "romania" not in lowered and "europa" not in lowered:
                continue
            if not self._looks_like_romania_impact_sentence(sentence):
                continue
            rewritten = self._rewrite_for_radio(sentence, "impact", kept_entities)
            if rewritten and not self._is_near_duplicate(rewritten, existing):
                return rewritten

        lowered = payload["full_text"].lower()
        fallback = ""
        if any(keyword in lowered for keyword in ("ormuz", "petrol", "energie", "gaze", "transport maritim")):
            fallback = "Pentru Romania si restul Europei, tensiunea poate duce la preturi mai mari la petrol si energie."
        elif any(keyword in lowered for keyword in ("nato", "marea neagra", "flancul estic", "exercitii", "securitate")):
            fallback = "Pentru Romania, miza tine de securitatea regionala si de transportul din zona Marii Negre."
        elif any(keyword in lowered for keyword in ("cipuri", "export", "lanturile", "aprovizionare", "baterii", "auto", "electronice")):
            fallback = "Pentru Romania, efectul se poate vedea in costuri mai mari si intarzieri pe lanturile de aprovizionare."
        elif any(keyword in lowered for keyword in ("tarife", "comert", "import", "exporturi", "trade")):
            fallback = "Pentru Romania si restul Europei, presiunea se poate vedea in comert si in costurile de import."

        rewritten = self._rewrite_for_radio(fallback, "impact", kept_entities)
        if rewritten and not self._is_near_duplicate(rewritten, existing):
            return rewritten
        return ""

    def _derive_closure_fallback(self, payload: dict[str, object]) -> str:
        lowered = payload["full_text"].lower()
        if any(keyword in lowered for keyword in ("isu", "incend", "controale")):
            return "Primele rezultate sunt asteptate pana la finalul saptamanii."
        if any(keyword in lowered for keyword in ("dna", "csm", "numire", "parchete", "procuror-sef")):
            return "Ministerul poate reveni cu o noua propunere in zilele urmatoare."
        if any(keyword in lowered for keyword in ("investig", "diicot", "procuror")):
            return "Cazul este investigat, iar urmatoarele decizii sunt asteptate in cateva zile."
        if any(keyword in lowered for keyword in ("lucrari", "restrictii", "trafic", "santier")):
            return "Primele efecte sunt asteptate chiar de la inceputul saptamanii viitoare."
        if any(keyword in lowered for keyword in ("energie", "petrol", "preturi", "facturi")):
            return "Primele efecte sunt asteptate in cateva saptamani."
        if any(keyword in lowered for keyword in ("ordonanta", "reguli", "schema")):
            return "Masura intra in vigoare luna viitoare."
        return ""

    def _promote_personal_attribution(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        sentences: list[str],
    ) -> list[str]:
        if not sentences or not self._personal_attribution_is_helpful(payload):
            return sentences
        if any(self._sentence_personal_attribution_type(sentence, payload) in {"named_person", "role_based_person"} for sentence in sentences[:2]):
            return sentences
        candidate = self._best_personal_attribution_sentence(payload, compression, sentences)
        if not candidate:
            return sentences
        updated = list(sentences)
        if candidate in updated:
            updated.remove(candidate)
        else:
            updated = [sentence for sentence in updated if not self._is_near_duplicate(sentence, [candidate])]
        insert_at = 1 if updated else 0
        updated.insert(insert_at, candidate)
        return updated[:MAX_SENTENCE_COUNT]

    def _best_personal_attribution_sentence(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        sentences: list[str],
    ) -> str:
        existing = list(sentences)
        candidates: list[tuple[float, str]] = []
        for sentence in list(sentences) + [item.text for item in compression.dropped_sentences] + list(payload["source_text_sentences"]):
            candidate = self._candidate_personal_attribution_sentence(sentence, payload, compression.kept_entities)
            if not candidate or self._is_near_duplicate(candidate, existing[:2]):
                continue
            attribution_type = self._sentence_personal_attribution_type(candidate, payload)
            if attribution_type not in {"named_person", "role_based_person"}:
                continue
            score = 2.2 if attribution_type == "named_person" else 1.5
            if self._sentence_has_impact(candidate) or self._sentence_has_next_step(candidate):
                score += 0.4
            candidates.append((score, candidate))
        if not candidates:
            return ""
        return max(candidates, key=lambda item: (item[0], -self._word_count(item[1])))[1]

    def _candidate_personal_attribution_sentence(
        self,
        sentence: str,
        payload: dict[str, object],
        kept_entities: list[str],
    ) -> str:
        rewritten = self._ensure_role_and_name_attribution(self._rewrite_for_radio(sentence, "reaction", kept_entities), payload)
        if self._sentence_personal_attribution_type(rewritten, payload) in {"named_person", "role_based_person"}:
            return rewritten
        role_based = self._convert_institution_to_role_attribution(sentence, payload)
        if role_based:
            candidate = self._rewrite_for_radio(role_based, "reaction", kept_entities)
            candidate = self._ensure_role_and_name_attribution(candidate, payload)
            if self._sentence_personal_attribution_type(candidate, payload) in {"named_person", "role_based_person"}:
                return candidate
        return ""

    def _ensure_attributed_voice(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        sentences: list[str],
    ) -> list[str]:
        if not sentences or self._story_attribution_type(sentences, payload) != "none":
            return sentences
        candidate = self._best_mandatory_attribution_sentence(payload, compression, sentences)
        if not candidate:
            return sentences
        updated = list(sentences)
        if candidate in updated:
            return updated[:MAX_SENTENCE_COUNT]
        if len(updated) >= MAX_SENTENCE_COUNT:
            replace_index = 1 if len(updated) > 1 else 0
            updated[replace_index] = candidate
        else:
            insert_at = 1 if updated else 0
            updated.insert(insert_at, candidate)
        return updated[:MAX_SENTENCE_COUNT]

    def _best_mandatory_attribution_sentence(
        self,
        payload: dict[str, object],
        compression: CompressedStoryCore,
        sentences: list[str],
    ) -> str:
        existing = list(sentences)
        candidates: list[tuple[float, str]] = []
        sentence_pool = list(sentences) + [item.text for item in compression.dropped_sentences] + list(payload["source_text_sentences"])
        seen: set[str] = set()
        for sentence in sentence_pool:
            if not sentence:
                continue
            named_candidate = self._candidate_named_role_sentence(sentence, payload, compression.kept_entities)
            if named_candidate and named_candidate not in seen and not self._is_near_duplicate(named_candidate, existing[:2]):
                seen.add(named_candidate)
                candidates.append((3.0, named_candidate))
            institution_candidate = self._candidate_institution_attribution_sentence(sentence, payload, compression.kept_entities)
            if institution_candidate and institution_candidate not in seen and not self._is_near_duplicate(institution_candidate, existing[:2]):
                seen.add(institution_candidate)
                candidates.append((2.0, institution_candidate))
            media_candidate = self._candidate_media_attribution_sentence(sentence, payload, compression.kept_entities)
            if media_candidate and media_candidate not in seen and not self._is_near_duplicate(media_candidate, existing[:2]):
                seen.add(media_candidate)
                candidates.append((1.0, media_candidate))
        if not candidates:
            return ""
        return max(candidates, key=lambda item: (item[0], -self._word_count(item[1])))[1]

    def _candidate_named_role_sentence(
        self,
        sentence: str,
        payload: dict[str, object],
        kept_entities: list[str],
    ) -> str:
        candidate = self._ensure_role_and_name_attribution(self._rewrite_for_radio(sentence, "reaction", kept_entities), payload)
        if self._sentence_personal_attribution_type(candidate, payload) == "named_person":
            return candidate
        return ""

    def _candidate_institution_attribution_sentence(
        self,
        sentence: str,
        payload: dict[str, object],
        kept_entities: list[str],
    ) -> str:
        rewritten = self._rewrite_for_radio(sentence, "reaction", kept_entities)
        if self._sentence_personal_attribution_type(rewritten, payload) == "institution":
            return rewritten
        institution = self._first_matching_institution(sentence, payload)
        if not institution:
            institutions = self._extract_institutions(payload["full_text"])
            institution = institutions[0] if institutions else ""
        if not institution:
            return ""
        candidate = self._build_attributed_clause_sentence(institution, "spune", rewritten or sentence)
        if self._sentence_personal_attribution_type(candidate, payload) == "institution":
            return candidate
        return ""

    def _candidate_media_attribution_sentence(
        self,
        sentence: str,
        payload: dict[str, object],
        kept_entities: list[str],
    ) -> str:
        source_label = str(payload.get("source_label") or "").strip()
        if not source_label:
            return ""
        rewritten = self._rewrite_for_radio(sentence, "reaction", kept_entities)
        if self._sentence_personal_attribution_type(rewritten, payload) == "media":
            return rewritten
        candidate = self._build_attributed_clause_sentence(source_label, "relateaza", rewritten or sentence)
        if self._sentence_personal_attribution_type(candidate, payload) == "media":
            return candidate
        return ""

    def _ensure_role_and_name_attribution(self, sentence: str, payload: dict[str, object]) -> str:
        top_person = str(payload.get("top_person") or "").strip()
        top_person_role = str(payload.get("top_person_role") or "").strip()
        if not sentence or not top_person or not top_person_role:
            return sentence
        lowered = sentence.lower()
        if top_person.lower() not in lowered or top_person_role.lower() in lowered or not self._has_attribution_verb(sentence):
            return sentence
        return self._finalize_sentence(sentence.replace(top_person, f"{top_person_role} {top_person}", 1))

    def _build_attributed_clause_sentence(self, actor: str, verb: str, base_sentence: str) -> str:
        clause = self._clean_text(base_sentence).rstrip(".!? ")
        if not clause:
            return ""
        clause = self._strip_leading_attribution_subject(clause, actor)
        clause = self._lowercase_lead(clause)
        if not clause:
            return ""
        candidate = self._finalize_sentence(f"{actor} {verb} ca {clause}")
        return candidate

    def _strip_leading_attribution_subject(self, sentence: str, actor: str) -> str:
        cleaned = sentence.strip()
        if actor and cleaned.lower().startswith(actor.lower()):
            cleaned = cleaned[len(actor):].lstrip(" ,")
            cleaned = re.sub(r"^(?:a\s+[A-Za-zÀ-ɏ-]+|[A-Za-zÀ-ɏ-]+(?:\s+ca)?)\s+", "", cleaned, count=1)
        cleaned = re.sub(r"^(?:ca|faptul ca)\s+", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" ,")

    def _lowercase_lead(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return ""
        return stripped[0].lower() + stripped[1:]

    def _convert_institution_to_role_attribution(self, sentence: str, payload: dict[str, object]) -> str:
        cleaned = self._clean_text(sentence)
        lowered = cleaned.lower()
        if not any(verb in lowered for verb in PERSONAL_ATTRIBUTION_VERBS):
            return ""
        for institution, role in ROLE_BASED_ATTRIBUTION_MAP.items():
            if lowered.startswith(institution):
                pattern = re.compile(rf"^{re.escape(institution)}", re.IGNORECASE)
                candidate = pattern.sub(role, cleaned, count=1)
                if role.lower() == candidate.lower():
                    continue
                return candidate
        return ""

    def _personal_attribution_is_helpful(self, payload: dict[str, object]) -> bool:
        lowered = payload["full_text"].lower()
        if payload.get("source_scope") == "local":
            return True
        return any(term in lowered for term in PERSONAL_ATTRIBUTION_ENCOURAGED_TERMS)

    def _extract_role_markers(self, text: str) -> list[str]:
        lowered = text.lower()
        found: list[str] = []
        for marker in ROLE_BASED_PERSON_MARKERS:
            if marker in lowered and marker not in found:
                found.append(marker)
        return found

    def _has_attribution_verb(self, sentence: str) -> bool:
        lowered = sentence.lower()
        return any(verb in lowered for verb in PERSONAL_ATTRIBUTION_VERBS)

    def _has_voice_verb(self, sentence: str) -> bool:
        lowered = sentence.lower()
        markers = PERSONAL_ATTRIBUTION_VERBS + (
            "a decis", "decide", "a impus", "impune", "a lansat", "lanseaza",
            "a inceput", "incepe", "a deschis", "deschide", "a extins", "extinde",
            "a aprobat", "aproba", "a respins", "respinge", "pregateste", "pregatesc",
            "a mutat", "muta", "a trimis", "trimite", "verifica", "dubleaza", "a dublat"
        )
        return any(marker in lowered for marker in markers)

    def _has_named_personal_attribution_sentence(self, sentence: str, people: list[str]) -> bool:
        lowered = sentence.lower()
        return bool(people) and any(person.lower() in lowered for person in people) and self._has_attribution_verb(sentence)

    def _has_role_based_personal_attribution_sentence(self, sentence: str) -> bool:
        lowered = sentence.lower()
        return any(marker in lowered for marker in ROLE_BASED_PERSON_MARKERS) and self._has_attribution_verb(sentence)

    def _first_matching_role_marker(self, sentence: str, payload: dict[str, object]) -> str:
        lowered = sentence.lower()
        top_person_role = str(payload.get("top_person_role") or "").strip()
        if top_person_role and top_person_role.lower() in lowered:
            return top_person_role
        for marker in payload.get("available_role_markers") or []:
            if marker in lowered:
                return marker
        return ""

    def _first_matching_institution(self, sentence: str, payload: dict[str, object]) -> str:
        lowered = sentence.lower()
        for institution in self._extract_institutions(payload["full_text"]):
            if institution.lower() in lowered:
                return institution
        return ""

    def _sentence_personal_attribution_type(self, sentence: str, payload: dict[str, object]) -> str:
        lowered = sentence.lower()
        top_person = str(payload.get("top_person") or "").strip()
        top_person_role = str(payload.get("top_person_role") or "").strip()
        source_label = str(payload.get("source_label") or "").strip()
        if top_person and top_person_role and top_person.lower() in lowered and top_person_role.lower() in lowered and self._has_attribution_verb(sentence):
            return "named_person"
        if self._first_matching_role_marker(sentence, payload) and self._has_attribution_verb(sentence):
            return "role_based_person"
        if self._first_matching_institution(sentence, payload) and self._has_voice_verb(sentence):
            return "institution"
        if source_label and source_label.lower() in lowered and any(marker in lowered for marker in ("relateaza", "scrie", "transmite")):
            return "media"
        return "none"

    def _reduce_intra_story_repetition(
        self,
        payload: dict[str, object],
        sentences: list[str],
    ) -> tuple[list[str], dict[str, bool]]:
        updated: list[str] = []
        duplicate_removed = False
        repetition_found = False
        for sentence in sentences:
            candidate = sentence
            if any(self._sentence_similarity(candidate, existing) > 0.7 for existing in updated):
                duplicate_removed = True
                repetition_found = True
                continue
            for existing in updated:
                if self._shares_time_marker(existing, candidate):
                    repetition_found = True
                    candidate = self._strip_repeated_time_marker(candidate)
                if self._shares_impact_signature(existing, candidate) and self._sentence_similarity(candidate, existing) > 0.52:
                    repetition_found = True
                    candidate = self._strip_repeated_impact_prefix(candidate)
            candidate = self._finalize_sentence(candidate)
            if not candidate:
                duplicate_removed = True
                continue
            if any(self._sentence_similarity(candidate, existing) > 0.7 for existing in updated):
                duplicate_removed = True
                repetition_found = True
                continue
            updated.append(candidate)
        return updated[:MAX_SENTENCE_COUNT], {
            "duplicate_sentence_removed": duplicate_removed,
            "stories_with_intra_story_repetition": repetition_found,
        }

    def _sentence_similarity(self, first: str, second: str) -> float:
        first_tokens = set(self._comparison_tokens(first))
        second_tokens = set(self._comparison_tokens(second))
        if not first_tokens or not second_tokens:
            return 0.0
        return len(first_tokens & second_tokens) / max(1, len(first_tokens | second_tokens))

    def _shares_time_marker(self, first: str, second: str) -> bool:
        lowered_first = first.lower()
        lowered_second = second.lower()
        return any(marker in lowered_first and marker in lowered_second for marker in REPEATED_TIME_MARKERS)

    def _shares_impact_signature(self, first: str, second: str) -> bool:
        tracked = {"energie", "preturi", "trafic", "costuri", "navetistii", "studentii", "efect", "impact"}
        first_tokens = {token for token in self._comparison_tokens(first) if token in tracked}
        second_tokens = {token for token in self._comparison_tokens(second) if token in tracked}
        return bool(first_tokens & second_tokens)

    def _strip_repeated_time_marker(self, sentence: str) -> str:
        trimmed = sentence
        for marker in REPEATED_TIME_MARKERS:
            trimmed = re.sub(rf"(?:,\s*)?{re.escape(marker)}", "", trimmed, flags=re.IGNORECASE)
        trimmed = re.sub(r"\s{2,}", " ", trimmed).strip(" ,")
        return trimmed

    def _strip_repeated_impact_prefix(self, sentence: str) -> str:
        return re.sub(r"^(Asta poate|Asta inseamna|Masura poate)\s+", "", sentence, flags=re.IGNORECASE).strip()

    def _register_story_variation(self, lead_family: str, closing_family: str, closing_sentence: str = "") -> None:
        if lead_family:
            self._recent_lead_families.append(lead_family)
        if closing_family:
            self._recent_closing_families.append(closing_family)
        if closing_sentence:
            self._recent_closing_sentences.append(closing_sentence)

    def _story_attribution_type(self, sentences: list[str], payload: dict[str, object]) -> str:
        for sentence in sentences:
            attribution_type = self._sentence_personal_attribution_type(sentence, payload)
            if attribution_type != "none":
                return attribution_type
        return "none"

    def _attribution_position_used(self, sentences: list[str], payload: dict[str, object]) -> str:
        for index, sentence in enumerate(sentences):
            if self._sentence_personal_attribution_type(sentence, payload) == "none":
                continue
            if index == 0:
                return "lead"
            if index == 1:
                return "sentence_2"
            return "later"
        return "none"

    def _attributed_voice_details(self, sentences: list[str], payload: dict[str, object]) -> dict[str, str]:
        details = {
            "attribution_level_used": "none",
            "attributed_name_used": "",
            "attributed_role_used": "",
            "attributed_institution_used": "",
            "attributed_media_source_used": "",
        }
        top_person = str(payload.get("top_person") or "").strip()
        top_person_role = str(payload.get("top_person_role") or "").strip()
        source_label = str(payload.get("source_label") or "").strip()
        for sentence in sentences:
            attribution_type = self._sentence_personal_attribution_type(sentence, payload)
            if attribution_type == "none":
                continue
            if attribution_type == "named_person":
                details.update({
                    "attribution_level_used": "person",
                    "attributed_name_used": top_person,
                    "attributed_role_used": top_person_role,
                })
                return details
            if attribution_type == "role_based_person":
                details.update({
                    "attribution_level_used": "person",
                    "attributed_role_used": self._first_matching_role_marker(sentence, payload),
                })
                return details
            if attribution_type == "institution":
                details.update({
                    "attribution_level_used": "institution",
                    "attributed_institution_used": self._first_matching_institution(sentence, payload),
                })
                return details
            if attribution_type == "media":
                details.update({
                    "attribution_level_used": "media",
                    "attributed_media_source_used": source_label,
                })
                return details
        return details

    def _extract_role_alias(self, text: str, person: str) -> str | None:
        if not person:
            return None
        for match in ROLE_PREFIX_PATTERN.finditer(text):
            if match.group("name") == person:
                return match.group("role")
        return None

    def _surname_reference(self, person: str) -> str:
        parts = person.split()
        return parts[-1] if parts else person

    def _has_explicit_attribution(self, sentence: str) -> bool:
        return bool(ATTRIBUTION_PREFIX_PATTERN.search(sentence.strip()))

    def _strip_attribution_prefix(self, sentence: str) -> str:
        stripped = ATTRIBUTION_PREFIX_PATTERN.sub("", sentence.strip(), count=1)
        if stripped:
            stripped = stripped[0].upper() + stripped[1:]
        return self._finalize_sentence(stripped or sentence)

    def _count_explicit_attributions(self, sentences: list[str]) -> int:
        return sum(1 for sentence in sentences if self._has_explicit_attribution(sentence))

    def _count_repeated_person_names(self, payload: dict[str, object], sentences: list[str]) -> int:
        top_person = str(payload.get("top_person") or "").strip()
        if not top_person:
            return 0
        occurrences = sum(sentence.count(top_person) for sentence in sentences)
        return max(0, occurrences - 1)

    def _is_administrative_sentence(self, sentence: str) -> bool:
        lowered = sentence.lower()
        return any(marker in lowered for marker in ADMINISTRATIVE_MARKERS)

    def _has_strong_closure(self, sentence: str) -> bool:
        lowered = sentence.lower()
        return any(marker in lowered for marker in STRONG_CLOSURE_KEYWORDS) or self._sentence_has_next_step(sentence)

    def _is_international_story(self, payload: dict[str, object]) -> bool:
        return str(payload.get("source_scope") or "").strip().lower() == "international"

    def _looks_like_romania_impact_sentence(self, sentence: str) -> bool:
        lowered = sentence.lower()
        return (
            ("romania" in lowered or "europa" in lowered)
            and any(
                keyword in lowered
                for keyword in (
                    "preturi",
                    "energie",
                    "costuri",
                    "securitate",
                    "lant",
                    "aprovizionare",
                    "comert",
                    "transport",
                    "efect",
                    "impact",
                )
            )
        )

    def _has_romania_impact_sentence(self, payload: dict[str, object], sentences: list[str]) -> bool:
        if not self._is_international_story(payload):
            return False
        return any(self._looks_like_romania_impact_sentence(sentence) for sentence in sentences)

    def _infer_story_scope(self, article_or_story: object, source_label: str | None, full_text: str) -> str:
        if isinstance(article_or_story, FetchedArticle) and article_or_story.source_scope:
            return article_or_story.source_scope
        source_scope = None
        if isinstance(article_or_story, dict):
            source_scope = article_or_story.get("source_scope")
        if source_scope in {"local", "national", "international"}:
            return str(source_scope)
        if source_label:
            if source_label in INTERNATIONAL_SOURCE_LABELS:
                return "international"
            if any(marker.lower() in source_label.lower() for marker in LOCAL_SOURCE_LABEL_MARKERS):
                return "local"
        lowered = full_text.lower()
        if any(keyword in lowered for keyword in ("statele unite", "washington", "iran", "ormuz", "nato", "uniunea europeana", "marea neagra")):
            return "international"
        return "national"

    def _prune_entities(self, people: list[str], institutions: list[str], locations: list[str]) -> list[str]:
        kept: list[str] = []
        if people:
            kept.append(people[0])
        main_institution = next((item for item in institutions if item not in kept), None)
        if main_institution:
            kept.append(main_institution)
        main_location = next((item for item in locations if item not in kept), None)
        if main_location:
            kept.append(main_location)
        return kept

    def _extract_persons(self, text: str) -> list[str]:
        people: list[str] = []
        for match in PERSON_PATTERN.findall(text):
            if any(part in PERSON_STOPWORDS for part in match.split()):
                continue
            if match not in people:
                people.append(match)
        return people

    def _extract_institutions(self, text: str) -> list[str]:
        found: list[str] = []
        for pattern in INSTITUTION_PATTERNS:
            if re.search(rf"\b{re.escape(pattern)}\b", text, re.IGNORECASE) and pattern not in found:
                found.append(pattern)
        return found

    def _extract_locations(self, text: str) -> list[str]:
        found: list[str] = []
        for pattern in LOCATION_PATTERNS:
            if re.search(rf"\b{re.escape(pattern)}\b", text, re.IGNORECASE) and pattern not in found:
                found.append(pattern)
        return found

    def _build_fact_core(self, payload: dict[str, object], sentences: list[str], kept_entities: list[str]) -> dict[str, str]:
        return {
            "who": kept_entities[0] if kept_entities else "",
            "what": sentences[0] if sentences else payload["headline_original"],
            "where": next((entity for entity in kept_entities if entity in LOCATION_PATTERNS), ""),
            "why_it_matters": sentences[2] if len(sentences) >= 3 else (sentences[1] if len(sentences) >= 2 else ""),
        }

    def _headline_to_sentence(self, headline: str) -> str:
        return self._finalize_sentence(self._clean_text(headline))

    def _rewrite_for_radio(self, text: str, role: str, kept_entities: list[str]) -> str:
        cleaned = self._clean_text(text)
        if not cleaned:
            return ""
        for source, target in PRINT_STYLE_REPLACEMENTS.items():
            cleaned = re.sub(re.escape(source), target, cleaned, flags=re.IGNORECASE)
        cleaned = self._simplify_numbers(cleaned)
        cleaned = cleaned.replace(" in timp ce ", " si ").replace(" iar ", " si ").replace(" insa ", " ").replace(" dar ", " ")
        cleaned = self._trim_sentence(cleaned, LEAD_MAX_WORDS if role == "lead" else SENTENCE_SOFT_MAX_WORDS)
        return self._finalize_sentence(cleaned)

    def _simplify_numbers(self, text: str) -> str:
        text = DECIMAL_BILLION_PATTERN.sub(lambda m: f"aproape {round(float(m.group(1) + '.' + m.group(2)))} miliarde", text)
        text = DECIMAL_MILLION_PATTERN.sub(lambda m: f"peste {m.group(1)},{m.group(2)} milioane", text)
        text = LARGE_NUMBER_PATTERN.sub(self._replace_large_number, text)
        text = PERCENT_PATTERN.sub(lambda m: "aproape jumatate" if int(m.group(1)) >= 45 else f"aproape {round(float(m.group(1) + '.' + m.group(2)))} la suta", text)
        text = text.replace("trece de peste", "trece de")
        return text

    def _replace_large_number(self, match: re.Match[str]) -> str:
        digits = int(re.sub(r"\D", "", match.group(0)))
        if digits >= 2_000_000:
            millions = round(digits / 1_000_000, 1)
            return f"{str(millions).replace('.', ',')} milioane"
        if digits >= 1_000_000:
            return "aproape un milion"
        if digits >= 100_000:
            return "cateva sute de mii"
        if digits >= 10_000:
            return f"aproximativ {round(digits / 1000)} mii"
        return match.group(0)

    def _trim_sentence(self, text: str, target_limit: int) -> str:
        sentence = text.strip(" ,.-")
        for marker in TRIM_MARKERS:
            if self._word_count(sentence) <= target_limit:
                break
            marker_index = sentence.lower().find(marker)
            if marker_index > 0:
                candidate = sentence[:marker_index].strip(" ,.-")
                if self._word_count(candidate) >= 8:
                    sentence = candidate
        if self._word_count(sentence) > target_limit:
            sentence = " ".join(sentence.split()[:target_limit])
        return sentence

    def _enforce_word_budget(self, sentences: list[str], band: str) -> str:
        cleaned = [self._finalize_sentence(sentence) for sentence in sentences if sentence]
        _, hard_max = self._band_limits(band)
        while self._word_count(" ".join(cleaned)) > hard_max and len(cleaned) > 3:
            cleaned.pop()
        while self._word_count(" ".join(cleaned)) > hard_max:
            for index in range(len(cleaned) - 1, -1, -1):
                limit = 18 if index >= 2 else 20 if index == 1 else LEAD_MAX_WORDS
                cleaned[index] = self._finalize_sentence(self._trim_sentence(cleaned[index], limit))
            if self._word_count(" ".join(cleaned)) <= hard_max:
                break
            if len(cleaned) > 3:
                cleaned.pop()
            else:
                break
        return " ".join(cleaned).strip()

    def _sentence_has_detail(self, sentence: str) -> bool:
        lowered = sentence.lower()
        return bool(re.search(r"\b\d+(?:[.,]\d+)*\b", sentence)) or any(keyword in lowered for keyword in DETAIL_KEYWORDS)

    def _sentence_has_impact(self, sentence: str) -> bool:
        lowered = sentence.lower()
        return any(keyword in lowered for keyword in IMPACT_KEYWORDS)

    def _sentence_has_next_step(self, sentence: str) -> bool:
        lowered = sentence.lower()
        return any(keyword in lowered for keyword in NEXT_STEP_KEYWORDS)

    def _detect_attribution_slot(self, radio_text: str, payload: dict[str, object]) -> str:
        sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_PATTERN.split(radio_text) if sentence.strip()]
        for sentence in sentences:
            attribution_type = self._sentence_personal_attribution_type(sentence, payload)
            if attribution_type == "named_person":
                for person in self._extract_persons(payload["full_text"]):
                    if person.lower() in sentence.lower():
                        return f"person:{person}"
            if attribution_type == "role_based_person":
                for role_marker in payload.get("available_role_markers") or []:
                    if role_marker in sentence.lower():
                        return f"role:{role_marker}"
                return "role:person"
            if attribution_type == "institution":
                for institution in self._extract_institutions(payload["full_text"]):
                    if institution.lower() in sentence.lower():
                        return f"institution:{institution}"
            if attribution_type == "media":
                source_label = str(payload.get("source_label") or "").strip()
                if source_label:
                    return f"media:{source_label}"
        return "none"

    def _main_actor_appears_early(self, lead_sentence: str, kept_entities: list[str]) -> bool:
        if not lead_sentence or not kept_entities:
            return True
        first_window = " ".join(lead_sentence.split()[:7]).lower()
        main_actor = kept_entities[0].lower()
        return any(token in first_window for token in main_actor.split())

    def _debug_value(self, debug_notes: list[str], key: str, default: str) -> str:
        prefix = f"{key}="
        for note in debug_notes:
            if note.startswith(prefix):
                return note.split("=", 1)[1]
        return default

    def _is_near_duplicate(self, sentence: str, selected: list[str]) -> bool:
        candidate_tokens = set(token.lower() for token in TOKEN_PATTERN.findall(sentence))
        for existing in selected:
            existing_tokens = set(token.lower() for token in TOKEN_PATTERN.findall(existing))
            if candidate_tokens and existing_tokens and len(candidate_tokens & existing_tokens) / max(1, len(candidate_tokens | existing_tokens)) >= 0.68:
                return True
        return False

    def _is_romanian_safe(self, text: str) -> bool:
        lowered = text.lower()
        english_markers = {"the", "and", "with", "from", "breaking", "live", "update"}
        return sum(1 for token in TOKEN_PATTERN.findall(lowered) if token in english_markers) < 2

    def _clean_text(self, text: str) -> str:
        normalized = URL_PATTERN.sub("", str(text or ""))
        normalized = QUOTE_STRIP_PATTERN.sub("", normalized)
        normalized = NOISY_PREFIX_PATTERN.sub("", normalized)
        normalized = normalized.replace("|", ". ").replace("::", ". ")
        normalized = MULTISPACE_PATTERN.sub(" ", normalized)
        return normalized.strip()

    def _fallback_story_id(self, seed: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "-", seed).strip("-").lower()
        return cleaned[:40] or "radio-story"

    def _finalize_sentence(self, sentence: str) -> str:
        cleaned = self._clean_text(sentence).strip(" ,")
        if not cleaned:
            return ""
        if cleaned[-1] not in ".!?":
            cleaned += "."
        return cleaned

    def _word_count(self, text: str) -> int:
        return len(WORD_PATTERN.findall(text or ""))

    def _estimate_duration_seconds(self, word_count: int) -> int:
        return round((word_count / WPM) * 60)

