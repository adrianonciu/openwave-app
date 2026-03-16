from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from app.models.article_fetch import FetchedArticle
from app.services.romanian_geo_resolver import resolve_county, resolve_macro_region

_COUNTY_DICTIONARY_PATH = Path(__file__).resolve().parents[1] / "config" / "geo_county_dictionary.json"
_REGION_MAP_PATH = Path(__file__).resolve().parents[1] / "config" / "geo_region_map.json"
_WORD_PATTERN = re.compile(r"[a-z0-9]+")

_NATIONAL_SIGNALS = {
    "romania", "romaniei", "roman", "romani", "bucuresti", "guvern", "guvernul", "parlament",
    "parlamentul", "presedintie", "ministerul", "minister", "anaf", "csm", "dna", "diicot",
    "iccj", "ccr", "mapn", "mae", "bnr", "romania-wide",
}

_INTERNATIONAL_SIGNALS = {
    "uniunea europeana", "ue", "eu", "nato", "sua", "statele unite", "usa", "china", "rusia",
    "ucraina", "orientul mijlociu", "middle east", "israel", "iran", "gaza", "bruxelles",
    "brussels", "germania", "franta", "marea britanie", "foreign government",
}

_COUNTY_FALSE_POSITIVE_PHRASES = {
    "Alba": {"casa alba"},
}


class GeoTaggingService:
    def __init__(self) -> None:
        county_payload = json.loads(_COUNTY_DICTIONARY_PATH.read_text(encoding="utf-8"))
        region_payload = json.loads(_REGION_MAP_PATH.read_text(encoding="utf-8"))
        self.county_entries = county_payload.get("counties", [])
        self.region_entries = region_payload.get("regions", [])
        self.region_by_county = {
            county: region_entry["region_name"]
            for region_entry in self.region_entries
            for county in region_entry.get("counties", [])
        }
        self._compiled_counties = [self._compile_county_entry(entry) for entry in self.county_entries]
        self._compiled_regions = [self._compile_region_entry(entry) for entry in self.region_entries]

    def tag_articles(self, articles: list[FetchedArticle]) -> tuple[list[FetchedArticle], dict[str, Any]]:
        tagged_articles = [self.tag_article(article) for article in articles]
        debug = self.build_debug_summary(tagged_articles)
        return tagged_articles, debug

    def tag_article(self, article: FetchedArticle) -> FetchedArticle:
        title_text = self._normalize_text(article.title)
        body_text = self._normalize_text(self._body_excerpt(article.content_text))
        intro_text = self._normalize_text(self._first_sentence(article.content_text))
        title_and_summary = self._join_text(title_text, intro_text)
        source_county = resolve_county(article.source_region) if article.is_local_source else None

        county_scores: dict[str, float] = {}
        county_signals: dict[str, list[str]] = {}
        county_signal_counts: Counter[str] = Counter()

        for entry in self._compiled_counties:
            score = 0.0
            signals: list[str] = []
            county_name = entry["county_name"]

            county_name_score, county_name_signals = self._score_patterns(
                title_and_summary,
                body_text,
                entry["county_patterns"],
                title_weight=1.0,
                body_weight=0.8,
                signal_prefix="county",
                signal_value=county_name,
            )
            score += county_name_score
            signals.extend(county_name_signals)

            seat_score, seat_signals = self._score_patterns(
                title_and_summary,
                body_text,
                entry["seat_patterns"],
                title_weight=0.8,
                body_weight=0.6,
                signal_prefix="seat",
                signal_value=entry["county_seat"],
            )
            score += seat_score
            signals.extend(seat_signals)

            city_score, city_signals = self._score_patterns(
                title_and_summary,
                body_text,
                entry["city_patterns"],
                title_weight=0.6,
                body_weight=0.5,
                signal_prefix="city",
                signal_value=county_name,
            )
            score += min(city_score, 1.2)
            signals.extend(city_signals)

            variant_score, variant_signals = self._score_patterns(
                title_and_summary,
                body_text,
                entry["variant_patterns"],
                title_weight=0.4,
                body_weight=0.3,
                signal_prefix="variant",
                signal_value=county_name,
            )
            score += min(variant_score, 0.8)
            signals.extend(variant_signals)

            if source_county == county_name and score > 0:
                score += 0.25
                signals.append(f"source_county:{county_name}")

            if self._is_false_positive_county_hit(county_name, title_and_summary, body_text, signals):
                continue

            if score > 0:
                county_scores[county_name] = round(score, 2)
                county_signals[county_name] = self._unique(signals)
                county_signal_counts[county_name] = len(county_signals[county_name])

        sorted_counties = sorted(county_scores.items(), key=lambda item: (item[1], county_signal_counts[item[0]], item[0]), reverse=True)
        top_county, top_score = sorted_counties[0] if sorted_counties else (None, 0.0)
        second_score = sorted_counties[1][1] if len(sorted_counties) > 1 else 0.0
        multiple_county_hits = [county for county, score in county_scores.items() if score >= 1.0]

        county_detected: str | None = None
        region_detected: str | None = None
        geo_scope: str | None = None
        confidence = 0.0
        geo_signals: list[str] = []
        national_hit = self._contains_any(title_and_summary, _NATIONAL_SIGNALS) or self._contains_any(body_text, _NATIONAL_SIGNALS)
        international_hit = self._contains_any(title_and_summary, _INTERNATIONAL_SIGNALS) or self._contains_any(body_text, _INTERNATIONAL_SIGNALS)

        if top_county and top_score >= 1.0:
            county_detected = top_county
            confidence = min(1.0, round(top_score / 2.4, 2))
            geo_scope = "county"
            geo_signals.extend(county_signals.get(top_county, []))
        elif source_county and top_county == source_county and top_score >= 0.4 and not international_hit:
            county_detected = source_county
            confidence = max(0.68, min(1.0, round((top_score + 0.35) / 2.0, 2)))
            geo_scope = "county"
            geo_signals.extend(county_signals.get(source_county, []))
            geo_signals.append(f"source_county:{source_county}")

        if county_detected:
            region_detected = self.region_by_county.get(county_detected) or resolve_macro_region(county_detected)
        else:
            region_detected = self._detect_region(title_and_summary, body_text, county_scores)
            if region_detected:
                geo_scope = "regional"
                geo_signals.append(f"region:{region_detected}")

        if geo_scope is None:
            if international_hit and not national_hit and not county_detected and not region_detected:
                geo_scope = "international"
                geo_signals.append("scope:international_signal")
            elif national_hit or article.source_scope == "national":
                geo_scope = "national"
                if national_hit:
                    geo_signals.append("scope:national_signal")
            elif article.source_scope == "international":
                geo_scope = "international"
            elif region_detected:
                geo_scope = "regional"
            else:
                geo_scope = "national"

        if geo_scope == "international" and (county_detected or region_detected or national_hit):
            geo_scope = "national" if national_hit else ("regional" if region_detected else "county")

        if not geo_signals and top_county and top_county in county_signals:
            geo_signals.extend(county_signals[top_county])

        if multiple_county_hits and not county_detected:
            shared_region = self._shared_region(multiple_county_hits)
            if shared_region:
                region_detected = region_detected or shared_region
                geo_scope = "regional"
                geo_signals.append(f"region:{shared_region}")

        tagged_article = article.model_copy(update={
            "geo_scope": geo_scope,
            "county_detected": county_detected,
            "region_detected": region_detected,
            "county_match_confidence": round(confidence, 2) if county_detected else None,
            "geo_signals": self._unique(geo_signals),
            "source_region": county_detected if article.is_local_source and county_detected else article.source_region,
        })
        return tagged_article

    def build_debug_summary(self, articles: list[FetchedArticle]) -> dict[str, Any]:
        scope_counts = Counter(article.geo_scope or "unknown" for article in articles)
        return {
            "story_count": len(articles),
            "geo_tagged_county": scope_counts.get("county", 0),
            "geo_tagged_regional": scope_counts.get("regional", 0),
            "geo_tagged_national": scope_counts.get("national", 0),
            "geo_tagged_international": scope_counts.get("international", 0),
            "stories_with_multiple_county_hits": sum(1 for article in articles if self._story_has_multiple_county_hits(article)),
        }

    def build_preview_payload(self, articles: list[FetchedArticle]) -> dict[str, Any]:
        debug_summary = self.build_debug_summary(articles)
        return {
            "stories": [
                {
                    "title": article.title,
                    "source_name": article.source,
                    "original_url": article.url,
                    "geo_scope": article.geo_scope,
                    "county_detected": article.county_detected,
                    "region_detected": article.region_detected,
                    "county_match_confidence": article.county_match_confidence,
                    "geo_signals": article.geo_signals,
                }
                for article in articles
            ],
            "validation_summary": debug_summary,
        }

    def _is_false_positive_county_hit(self, county_name: str, title_and_summary: str, body_text: str, signals: list[str]) -> bool:
        phrases = _COUNTY_FALSE_POSITIVE_PHRASES.get(county_name, set())
        if not phrases:
            return False
        matched_false_positive = self._contains_any(title_and_summary, phrases) or self._contains_any(body_text, phrases)
        meaningful_signals = [signal for signal in signals if not signal.startswith('variant:')]
        return matched_false_positive and not meaningful_signals

    def _detect_region(self, title_and_summary: str, body_text: str, county_scores: dict[str, float]) -> str | None:
        for region_entry in self._compiled_regions:
            if self._contains_any(title_and_summary, region_entry["patterns"]) or self._contains_any(body_text, region_entry["patterns"]):
                return region_entry["region_name"]

        strong_counties = [county for county, score in county_scores.items() if score >= 0.8]
        return self._shared_region(strong_counties)

    def _shared_region(self, counties: list[str]) -> str | None:
        regions = {self.region_by_county.get(county) for county in counties if self.region_by_county.get(county)}
        return next(iter(regions)) if len(regions) == 1 else None

    def _story_has_multiple_county_hits(self, article: FetchedArticle) -> bool:
        county_signal_hits = [signal for signal in article.geo_signals if signal.startswith(("county:", "city:", "seat:", "variant:"))]
        counties = {signal.split(":", 1)[1] for signal in county_signal_hits}
        return len(counties) > 1

    def _compile_county_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        county_name = str(entry.get("county_name") or "").strip()
        county_seat = str(entry.get("county_seat") or county_name).strip()
        major_cities = [str(value).strip() for value in entry.get("major_cities", []) if str(value).strip()]
        variants = [str(value).strip() for value in entry.get("common_variants", []) if str(value).strip()]
        return {
            "county_name": county_name,
            "county_seat": county_seat,
            "county_patterns": self._build_patterns([county_name, county_name.replace("-", " ")]),
            "seat_patterns": self._build_patterns([county_seat]),
            "city_patterns": self._build_patterns(major_cities),
            "variant_patterns": self._build_patterns(variants),
        }

    def _compile_region_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        region_name = str(entry.get("region_name") or "").strip()
        counties = [str(value).strip() for value in entry.get("counties", []) if str(value).strip()]
        patterns = self._build_patterns([region_name, *counties])
        return {
            "region_name": region_name,
            "patterns": patterns,
        }

    def _score_patterns(
        self,
        title_and_summary: str,
        body_text: str,
        patterns: list[str],
        title_weight: float,
        body_weight: float,
        signal_prefix: str,
        signal_value: str,
    ) -> tuple[float, list[str]]:
        matched_title = any(self._contains_phrase(title_and_summary, pattern) for pattern in patterns)
        matched_body = any(self._contains_phrase(body_text, pattern) for pattern in patterns)
        score = 0.0
        signals: list[str] = []
        if matched_title:
            score += title_weight
            signals.append(f"{signal_prefix}:{signal_value}")
        elif matched_body:
            score += body_weight
            signals.append(f"{signal_prefix}:{signal_value}")
        return score, signals

    def _build_patterns(self, values: list[str]) -> list[str]:
        return self._unique([self._normalize_text(value) for value in values if self._normalize_text(value)])

    def _contains_any(self, normalized_text: str, phrases: set[str] | list[str]) -> bool:
        return any(self._contains_phrase(normalized_text, self._normalize_text(phrase)) for phrase in phrases if phrase)

    def _contains_phrase(self, normalized_text: str, normalized_phrase: str) -> bool:
        if not normalized_text or not normalized_phrase:
            return False
        if normalized_phrase not in normalized_text:
            return False
        if " " not in normalized_phrase:
            return normalized_phrase in set(_WORD_PATTERN.findall(normalized_text))
        escaped = re.escape(normalized_phrase).replace(r"\ ", r"\s+")
        return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", normalized_text) is not None

    def _normalize_text(self, value: str | None) -> str:
        raw = (value or "").strip().lower()
        if not raw:
            return ""
        ascii_value = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
        ascii_value = ascii_value.replace("-", " ")
        ascii_value = re.sub(r"[^a-z0-9\s]", " ", ascii_value)
        return re.sub(r"\s+", " ", ascii_value).strip()

    def _body_excerpt(self, text: str | None, max_sentences: int = 4, max_chars: int = 900) -> str:
        value = (text or '').strip()
        if not value:
            return ''
        sentences = re.split(r'(?<=[.!?])\s+', value)
        excerpt = ' '.join(sentences[:max_sentences]).strip()
        return excerpt[:max_chars]

    def _first_sentence(self, text: str | None) -> str:
        value = (text or "").strip()
        if not value:
            return ""
        return re.split(r"(?<=[.!?])\s+", value, maxsplit=1)[0]

    def _join_text(self, *parts: str) -> str:
        return " ".join(part for part in parts if part).strip()

    def _unique(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            cleaned = str(value).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return result
