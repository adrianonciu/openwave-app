from __future__ import annotations



import json

import os

import re

import urllib.error

import urllib.request

from typing import Any



from app.config.env import load_backend_env

from app.models.article_fetch import FetchedArticle

from app.models.radio_story_draft import RadioStoryDraft



SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")

JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

ROLE_PATTERNS = (

    "primarul", "ministrul", "premierul", "directorul", "managerul", "inspectorul", "purtatorul de cuvant",

    "presedintele", "seful", "prefectul", "medicul", "primaria", "ministerul", "guvernul", "isu",

    "spitalul", "consiliul judetean", "nato", "comisia europeana", "casa alba"

)

PERSON_PATTERN = re.compile(r"\b([A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+){1,2})\b")

AUDIENCE_MARKERS = (

    "soferii", "familiile", "pacientii", "navetistii", "fermierii", "consumatorii", "parintii", "elevii",

    "turistii", "locuitorii", "rezidentii", "pensionarii", "companiile", "firmele", "afacerile"

)

QUOTE_MARKERS = ("a declarat", "a spus", "a precizat", "a explicat", "a avertizat", "a promis", "a anuntat", "a transmis", "spune ca", "relateaza ca")





class ArticleToRadioStoryService:

    def __init__(self) -> None:

        load_backend_env()

        self._api_key = os.getenv('OPENAI_API_KEY', '').strip()

        self._model = os.getenv('OPENWAVE_SUMMARIZATION_MODEL', 'gpt-4.1-mini').strip() or 'gpt-4.1-mini'

        self._timeout_seconds = int(os.getenv('OPENWAVE_SUMMARIZATION_TIMEOUT_SECONDS', '45') or '45')



    def summarize_article(self, article: FetchedArticle) -> tuple[RadioStoryDraft | None, dict[str, Any]]:

        if not article.content_text.strip():

            return None, self._meta('fallback_rules', False, False, False, True, None, 'missing_cleaned_text')

        if not self._api_key:

            return None, self._meta('fallback_rules', False, False, False, True, None, 'llm_not_configured')

        try:

            response_text = self._call_openai(article)

            if response_text.strip() == 'SKIP_NO_ACTOR':

                return None, self._meta('llm', False, False, False, False, 'skip_no_actor', None)

            draft = self._parse_response(response_text, article)

            return draft, self._meta(draft.summarization_method, draft.actor_detected, draft.quote_detected, draft.impact_detected, False, draft.skip_reason, None)

        except Exception as exc:

            fallback_reason = 'invalid_api_key' if 'invalid_api_key' in str(exc).lower() or 'incorrect api key' in str(exc).lower() else 'llm_failure'

            return None, self._meta('fallback_rules', False, False, False, True, None, fallback_reason)



    def summarize_articles(self, articles: list[FetchedArticle]) -> tuple[list[FetchedArticle], dict[str, Any]]:

        updated: list[FetchedArticle] = []

        metrics = {

            'stories_generated_by_llm': 0,

            'stories_skipped_no_actor': 0,

            'stories_failed_llm_parse': 0,

            'stories_using_fallback_rules': 0,

        }

        for article in articles:

            draft, meta = self.summarize_article(article)

            if meta.get('skip_reason') == 'skip_no_actor':

                metrics['stories_skipped_no_actor'] += 1

            if meta.get('summarization_fallback_used'):

                metrics['stories_using_fallback_rules'] += 1

                if meta.get('fallback_reason') == 'llm_parse_failure':

                    metrics['stories_failed_llm_parse'] += 1

            elif draft is not None and meta.get('summarization_method') == 'llm':

                metrics['stories_generated_by_llm'] += 1

            updated.append(article.model_copy(update={

                'radio_story_draft': draft,

                'summarization_method': str(meta.get('summarization_method') or ('llm' if draft else 'fallback_rules')), 

                'summarization_actor_detected': bool(meta.get('actor_detected')),

                'summarization_quote_detected': bool(meta.get('quote_detected')),

                'summarization_impact_detected': bool(meta.get('impact_detected')),

                'summarization_fallback_used': bool(meta.get('summarization_fallback_used')),

                'summarization_skip_reason': meta.get('skip_reason'),

            }))

        metrics['article_count'] = len(updated)

        return updated, metrics



    def _call_openai(self, article: FetchedArticle) -> str:

        prompt = self._build_prompt(article)

        payload = json.dumps({

            'model': self._model,

            'response_format': {'type': 'json_object'},

            'messages': [

                {'role': 'system', 'content': 'You are a Romanian radio news editor. Always answer with strict JSON or exactly SKIP_NO_ACTOR.'},

                {'role': 'user', 'content': prompt},

            ],

            'temperature': 0.2,

        }).encode('utf-8')

        request = urllib.request.Request(

            url='https://api.openai.com/v1/chat/completions',

            data=payload,

            headers={

                'Authorization': f'Bearer {self._api_key}',

                'Content-Type': 'application/json',

            },

            method='POST',

        )

        try:

            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:

                raw = json.loads(response.read().decode('utf-8'))

        except urllib.error.HTTPError as exc:

            details = exc.read().decode('utf-8', errors='ignore')

            raise RuntimeError(details or f'HTTP {exc.code}') from exc

        except urllib.error.URLError as exc:

            raise RuntimeError('network_error') from exc

        message = raw.get('choices', [{}])[0].get('message', {}) if isinstance(raw, dict) else {}

        content = message.get('content', '') if isinstance(message, dict) else ''

        if isinstance(content, list):

            text_parts = [part.get('text', '') for part in content if isinstance(part, dict)]

            return '\n'.join(text_parts).strip()

        return str(content).strip()



    def _build_prompt(self, article: FetchedArticle) -> str:

        geo_bits = [

            f"Geo scope: {article.geo_scope or 'unknown'}",

            f"County detected: {article.county_detected or 'unknown'}",

            f"Region detected: {article.region_detected or 'unknown'}",

        ]

        return (

            'Read the following news article.\n\n'

            'Write a short radio news story in Romanian.\n\n'

            'Return strict JSON with keys: title, summary_sentences, main_actor_name, main_actor_role, attributed_quote, impact_sentence.\n'

            'Rules:\n'

            '1. Title max 10 words and contains main person name + role when available.\n'

            '2. Sentence 1 begins with the main person name + role and describes what they said/did with attributed paraphrase.\n'

            '3. Sentence 2 explains direct impact on a clear audience.\n'

            '4. Sentence 3 gives essential context where/when.\n'

            '5. Sentence 4 optional immediate consequence or next step.\n'

            'Constraints: total length 65-95 words, max 22 words per sentence, avoid repetition, avoid filler phrases, avoid "urmeaza clarificari".\n'

            'If the article contains no identifiable person or role, return exactly SKIP_NO_ACTOR.\n\n'

            f"Source: {article.source}\nURL: {article.url}\nTitle: {article.title}\n{' | '.join(geo_bits)}\n\nArticle:\n{article.content_text[:9000]}"

        )



    def _parse_response(self, response_text: str, article: FetchedArticle) -> RadioStoryDraft:

        cleaned = JSON_FENCE_PATTERN.sub('', response_text.strip())

        payload = json.loads(cleaned)

        sentences = [self._clean_sentence(item) for item in payload.get('summary_sentences', []) if self._clean_sentence(str(item))]

        title = self._clean_sentence(str(payload.get('title') or article.title))

        quote = self._clean_sentence(str(payload.get('attributed_quote') or '')) or None

        impact_sentence = self._clean_sentence(str(payload.get('impact_sentence') or '')) or None

        actor_name = self._clean_actor(str(payload.get('main_actor_name') or ''))

        actor_role = self._clean_actor(str(payload.get('main_actor_role') or ''))

        return RadioStoryDraft(

            title=title or article.title,

            summary_sentences=sentences[:4],

            main_actor_name=actor_name,

            main_actor_role=actor_role,

            attributed_quote=quote,

            impact_sentence=impact_sentence,

            source_name=article.source,

            original_url=article.url,

            summarization_method='llm',

            actor_detected=bool(actor_name or actor_role),

            quote_detected=bool(quote or any(marker in ' '.join(sentences).lower() for marker in QUOTE_MARKERS)),

            impact_detected=bool(impact_sentence or any(marker in ' '.join(sentences).lower() for marker in AUDIENCE_MARKERS)),

            skip_reason=None,

        )



    def _clean_sentence(self, value: str) -> str:

        text = re.sub(r'\s+', ' ', value).strip().strip('"')

        if not text:

            return ''

        if text[-1] not in '.!?':

            text += '.'

        return text



    def _clean_actor(self, value: str) -> str | None:

        text = re.sub(r'\s+', ' ', value).strip(' ,.;:')

        return text or None



    def _meta(self, method: str, actor: bool, quote: bool, impact: bool, fallback_used: bool, skip_reason: str | None, fallback_reason: str | None) -> dict[str, Any]:

        return {

            'summarization_method': method,

            'actor_detected': actor,

            'quote_detected': quote,

            'impact_detected': impact,

            'summarization_fallback_used': fallback_used,

            'skip_reason': skip_reason,

            'fallback_reason': fallback_reason,

        }

