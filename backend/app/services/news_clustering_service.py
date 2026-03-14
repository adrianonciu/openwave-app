from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from html import unescape
import hashlib
import re
import unicodedata

from app.models.article_fetch import FetchedArticle
from app.models.news_cluster import (
    ClusterDecision,
    ClusterMemberArticle,
    NewsClusteringArticle,
    StoryCluster,
)

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z\u00C0-\u024F][0-9A-Za-z\u00C0-\u024F\-']{2,}")
ENTITY_PATTERN = re.compile(
    r"\b(?:[A-Z\u00C0-\u024F][a-z\u00DF-\u024F]+(?:\s+[A-Z\u00C0-\u024F][a-z\u00DF-\u024F]+){0,3}|[A-Z\u00C0-\u024F]{2,}(?:\s+[A-Z\u00C0-\u024F]{2,}){0,2})\b"
)
STOPWORDS = {
    "about", "after", "amid", "also", "and", "another", "around", "because", "before",
    "behind", "between", "brief", "commentary", "could", "early", "from", "have", "into",
    "more", "news", "over", "says", "say", "that", "their", "there", "these", "they",
    "this", "today", "under", "update", "what", "when", "where", "which", "while", "with",
    "would", "your", "romania", "romanian", "world",
}
ROMANIAN_STOPWORDS = {
    "acest", "aceste", "aceasta", "acum", "al", "ale", "care", "catre", "cu", "de", "din",
    "dupa", "este", "fara", "fi", "fost", "insa", "intr", "la", "mai", "mult", "nou", "noi",
    "pentru", "pe", "prin", "sau", "se", "si", "sub", "sunt", "un",
}
SOURCE_CANONICAL_MAP = {
    "ap": "AP",
    "ap news": "AP",
    "associated press": "AP",
    "bbc": "BBC",
    "bbc news": "BBC",
    "bbc world": "BBC",
    "deutsche welle": "DW",
    "dw": "DW",
    "dw world": "DW",
    "euronews romania": "Euronews Romania",
    "euronews ro stiri de ultima ora breaking news allviews": "Euronews Romania",
    "news ro": "News.ro",
    "news.ro": "News.ro",
    "reuters": "Reuters",
    "reuters world": "Reuters",
    "stiri pe surse": "Stiripesurse",
    "stiripesurse": "Stiripesurse",
}
EVENT_NORMALIZATION_MAP = {
    "associated press": "ap",
    "ap news": "ap",
    "bbc world": "bbc",
    "bbc news": "bbc",
    "deutsche welle": "dw",
    "middle east": "orientul mijlociu",
    "united arab emirates": "emiratele",
    "uae": "emiratele",
    "gulf": "golful",
    "ports": "porturi",
    "port": "porturi",
    "threatens": "ameninta",
    "threaten": "ameninta",
    "steps down": "demisie",
    "step down": "demisie",
    "receives": "primeste",
    "prize": "premiu",
    "school": "scoala",
    "attack": "atac",
    "attacks": "atac",
    "explosion": "explozie",
    "missiles": "rachete",
    "missile": "racheta",
    "warships": "nave",
    "warship": "nava",
    "markets": "piete",
    "market": "piete",
}
SPORT_TERMS = {
    "atletism", "championship", "cupa", "football", "goal", "gol", "league", "liga", "match",
    "meci", "nba", "olympic", "pariuri", "soccer", "sport", "tennis", "wbc",
}
SPORT_STRONG_TERMS = {
    "atletism", "championship", "cupa", "football", "goal", "gol", "league", "liga", "match",
    "meci", "nba", "olympic", "pariuri", "play-off", "play-out", "soccer", "sport", "tennis", "wbc",
}
HARD_NEWS_TERMS = {
    "ambasada", "atac", "bagdad", "china", "conflict", "crisis", "criza", "emiratele", "explozie", "golful",
    "government", "hamas", "iran", "israel", "marines", "minister", "mijlociu", "nava",
    "nave", "orientul", "ormuz", "pensionari", "porturi", "president", "putin", "racheta",
    "protest", "proteste", "protesters", "prison", "rusia", "scoala", "securitate", "trump", "ucraina", "ukraine",
    "death", "deaths", "dies",
}
ENTERTAINMENT_TERMS = {
    "award", "awards", "beauty", "celebrity", "fashion", "film", "music", "nails",
    "oval office", "piercings", "premiu", "premiile", "show", "style", "tmz",
}
HUMAN_INTEREST_TERMS = {
    "treasure", "hunter", "philosopher", "classic", "style", "fashion", "beauty", "nails", "award",
}
GENERALIST_SOURCES = {"AP", "BBC", "DW", "Euronews Romania", "Reuters"}
REGIONAL_ESCALATION_TERMS = {
    "iran", "golful", "emiratele", "ormuz", "orientul", "mijlociu", "porturi", "nave", "marines", "hamas", "atac",
}
EVENT_FAMILY_KEYWORDS = {
    "regional_conflict": {"war", "conflict", "escalation", "tensions", "strike", "strikes", "attack", "atac", "hamas", "iran", "israel"},
    "military_movement": {"troops", "marines", "warships", "naval", "deployment", "nave", "military"},
    "energy_shipping_disruption": {"ports", "porturi", "shipping", "strait", "ormuz", "oil", "gas", "route", "routes"},
    "political_crisis": {"protest", "protests", "protesters", "uprising", "coup", "government", "crisis", "criza"},
    "attack_or_strike": {"attack", "atac", "strike", "strikes", "explosion", "explozie", "racheta", "missile"},
    "economic_shock": {"oil", "gas", "inflation", "markets", "piete", "supply", "shipping"},
}
EVENT_FAMILY_MERGEABLE = {"regional_conflict", "military_movement", "energy_shipping_disruption"}
REGIONAL_LOCATION_BUCKETS = {
    "gulf_escalation": {"iran", "golful", "emiratele", "ormuz", "orientul", "mijlociu", "porturi", "gaza", "hamas", "israel"},
    "black_sea_security": {"romania", "marea", "neagra", "ucraina", "ukraine", "moldova", "rusia"},
    "eu_security": {"eu", "brussels", "nato", "romania", "moldova", "balkans", "balcani"},
}
GEOPOLITICAL_EVENT_ANCHORS = {
    "bagdad", "belarus", "china", "cuba", "emiratele", "gaza", "golful", "hamas",
    "iran", "israel", "kharg", "mijlociu", "ormuz", "rusia", "sua", "trump",
    "ucraina", "uae",
}
MOJIBAKE_MARKERS = (chr(0x00C3), chr(0x00C4), chr(0x00C5), chr(0x00C8), chr(0x00E2) + chr(0x20AC))


@dataclass
class _ArticleSignals:
    article: NewsClusteringArticle
    normalized_title: str
    normalized_source: str
    title_tokens: set[str]
    salient_keywords: set[str]
    body_keywords: set[str]
    entities: set[str]
    event_terms: set[str]
    event_families: set[str]
    regional_buckets: set[str]


class NewsClusteringService:
    def __init__(self, recency_window_hours: int = 24) -> None:
        self.recency_window_hours = recency_window_hours

    def cluster_articles(self, articles: list[FetchedArticle]) -> list[StoryCluster]:
        clustering_articles = [
            NewsClusteringArticle.from_fetched_article(article) for article in articles
        ]
        return self.cluster_clustering_articles(clustering_articles)

    def cluster_clustering_articles(
        self,
        articles: list[NewsClusteringArticle],
    ) -> list[StoryCluster]:
        signals = [self._build_signals(article) for article in articles]
        signals.sort(key=lambda item: item.article.published_at)

        grouped: list[list[_ArticleSignals]] = []
        for candidate in signals:
            best_cluster_index: int | None = None
            best_score = -1.0

            for index, cluster in enumerate(grouped):
                decision = self._cluster_match_decision(candidate, cluster)
                if decision.status == "merged":
                    score = self._decision_score(decision)
                    if score > best_score:
                        best_score = score
                        best_cluster_index = index

            if best_cluster_index is None:
                grouped.append([candidate])
            else:
                grouped[best_cluster_index].append(candidate)

        return [self._build_cluster(cluster) for cluster in grouped]

    def explain_pair(
        self,
        left: FetchedArticle | NewsClusteringArticle,
        right: FetchedArticle | NewsClusteringArticle,
    ) -> ClusterDecision:
        left_article = self._normalize_article(left)
        right_article = self._normalize_article(right)
        left_signals = self._build_signals(left_article)
        right_signals = self._build_signals(right_article)
        return self._pair_decision(left_signals, right_signals)

    def _normalize_article(
        self,
        article: FetchedArticle | NewsClusteringArticle,
    ) -> NewsClusteringArticle:
        if isinstance(article, NewsClusteringArticle):
            return article
        return NewsClusteringArticle.from_fetched_article(article)

    def _build_signals(self, article: NewsClusteringArticle) -> _ArticleSignals:
        normalized_article = self._normalize_article_metadata(article)
        title_tokens = self._tokenize(normalized_article.title)
        salient_keywords = self._salient_keywords(normalized_article.title, limit=10)
        body_keywords = self._salient_keywords(normalized_article.content_text[:4000], limit=16)
        entities = self._extract_entities(
            f"{normalized_article.title}. {normalized_article.content_text[:1200]}"
        )
        event_terms = self._event_terms(
            f"{normalized_article.title}. {normalized_article.content_text[:1600]}"
        )
        event_families = self._event_families(event_terms)
        regional_buckets = self._regional_buckets(event_terms)
        return _ArticleSignals(
            article=normalized_article,
            normalized_title=self._normalize_text(normalized_article.title),
            normalized_source=self._normalize_source_identity(normalized_article.source),
            title_tokens=title_tokens,
            salient_keywords=salient_keywords,
            body_keywords=body_keywords,
            entities=entities,
            event_terms=event_terms,
            event_families=event_families,
            regional_buckets=regional_buckets,
        )

    def _cluster_match_decision(
        self,
        candidate: _ArticleSignals,
        cluster: list[_ArticleSignals],
    ) -> ClusterDecision:
        decisions = [self._pair_decision(candidate, member) for member in cluster]
        merged_decisions = [decision for decision in decisions if decision.status == "merged"]
        if not merged_decisions:
            best = max(decisions, key=self._decision_score)
            return ClusterDecision(
                status="separate",
                reason=best.reason,
                title_similarity=best.title_similarity,
                keyword_overlap=best.keyword_overlap,
                body_overlap=best.body_overlap,
                shared_entities=best.shared_entities,
                hours_apart=best.hours_apart,
            )

        best = max(merged_decisions, key=self._decision_score)
        return best

    def _pair_decision(
        self,
        left: _ArticleSignals,
        right: _ArticleSignals,
    ) -> ClusterDecision:
        hours_apart = abs(
            (left.article.published_at - right.article.published_at).total_seconds()
        ) / 3600.0
        if hours_apart > self.recency_window_hours:
            return ClusterDecision(
                status="separate",
                reason="outside_recency_window",
                title_similarity=0.0,
                keyword_overlap=0.0,
                body_overlap=0.0,
                shared_entities=[],
                hours_apart=hours_apart,
            )

        title_similarity = self._overlap_ratio(left.title_tokens, right.title_tokens)
        normalized_title_similarity = self._normalized_title_similarity(
            left.normalized_title,
            right.normalized_title,
        )
        keyword_overlap = self._overlap_ratio(
            left.salient_keywords | left.body_keywords,
            right.salient_keywords | right.body_keywords,
        )
        body_overlap = self._overlap_ratio(left.body_keywords, right.body_keywords)
        event_overlap = self._overlap_ratio(left.event_terms, right.event_terms)
        shared_entities = sorted(left.entities & right.entities)
        cross_source = left.normalized_source != right.normalized_source

        strong_signal_count = 0
        if title_similarity >= 0.72:
            strong_signal_count += 1
        if normalized_title_similarity >= 0.68:
            strong_signal_count += 1
        if keyword_overlap >= 0.52:
            strong_signal_count += 1
        if body_overlap >= 0.32:
            strong_signal_count += 1
        if event_overlap >= 0.48:
            strong_signal_count += 1
        if len(shared_entities) >= 2:
            strong_signal_count += 1

        if normalized_title_similarity >= 0.8 and event_overlap >= 0.32:
            return ClusterDecision(
                status="merged",
                reason="normalized_titles_and_event_terms_aligned",
                title_similarity=max(title_similarity, normalized_title_similarity),
                keyword_overlap=max(keyword_overlap, event_overlap),
                body_overlap=body_overlap,
                shared_entities=shared_entities,
                hours_apart=hours_apart,
            )

        if title_similarity >= 0.84 and (keyword_overlap >= 0.45 or len(shared_entities) >= 1):
            return ClusterDecision(
                status="merged",
                reason="near_duplicate_titles_with_supporting_overlap",
                title_similarity=title_similarity,
                keyword_overlap=keyword_overlap,
                body_overlap=body_overlap,
                shared_entities=shared_entities,
                hours_apart=hours_apart,
            )

        if strong_signal_count >= 3 and (title_similarity >= 0.38 or normalized_title_similarity >= 0.5):
            return ClusterDecision(
                status="merged",
                reason="multiple_strong_similarity_signals",
                title_similarity=max(title_similarity, normalized_title_similarity),
                keyword_overlap=max(keyword_overlap, event_overlap),
                body_overlap=body_overlap,
                shared_entities=shared_entities,
                hours_apart=hours_apart,
            )

        if (
            len(shared_entities) >= 2
            and event_overlap >= 0.42
            and body_overlap >= 0.2
            and cross_source
        ):
            return ClusterDecision(
                status="merged",
                reason="shared_entities_and_event_alignment_across_sources",
                title_similarity=max(title_similarity, normalized_title_similarity),
                keyword_overlap=max(keyword_overlap, event_overlap),
                body_overlap=body_overlap,
                shared_entities=shared_entities,
                hours_apart=hours_apart,
            )

        if self._is_geopolitical_event_bundle(
            left,
            right,
            shared_entities,
            cross_source,
            event_overlap,
            keyword_overlap,
            hours_apart,
        ):
            return ClusterDecision(
                status="merged",
                reason="cross_source_geopolitical_event_bundle",
                title_similarity=max(title_similarity, normalized_title_similarity),
                keyword_overlap=max(keyword_overlap, event_overlap),
                body_overlap=body_overlap,
                shared_entities=shared_entities,
                hours_apart=hours_apart,
            )

        if self._is_regional_escalation_bundle(left, right, cross_source, event_overlap, keyword_overlap, hours_apart):
            return ClusterDecision(
                status="merged",
                reason="regional_escalation_bundle",
                title_similarity=max(title_similarity, normalized_title_similarity),
                keyword_overlap=max(keyword_overlap, event_overlap),
                body_overlap=body_overlap,
                shared_entities=shared_entities,
                hours_apart=hours_apart,
            )

        if self._is_event_family_hard_news_match(
            left,
            right,
            shared_entities,
            cross_source,
            normalized_title_similarity,
            event_overlap,
            keyword_overlap,
            hours_apart,
        ):
            return ClusterDecision(
                status="merged",
                reason="event_family_regional_hard_news_match",
                title_similarity=max(title_similarity, normalized_title_similarity),
                keyword_overlap=max(keyword_overlap, event_overlap),
                body_overlap=body_overlap,
                shared_entities=shared_entities,
                hours_apart=hours_apart,
            )

        return ClusterDecision(
            status="separate",
            reason="similarity_below_conservative_threshold",
            title_similarity=max(title_similarity, normalized_title_similarity),
            keyword_overlap=max(keyword_overlap, event_overlap),
            body_overlap=body_overlap,
            shared_entities=shared_entities,
            hours_apart=hours_apart,
        )

    def _build_cluster(self, cluster_signals: list[_ArticleSignals]) -> StoryCluster:
        representative = self._choose_representative(cluster_signals)
        member_articles = [
            ClusterMemberArticle(
                url=item.article.url,
                title=item.article.title,
                source=item.article.source,
                published_at=item.article.published_at,
                ingestion_kind=item.article.ingestion_kind,
                editorial_priority=item.article.editorial_priority,
                source_scope=item.article.source_scope,
                source_category=item.article.source_category,
                is_local_source=item.article.is_local_source,
            )
            for item in sorted(cluster_signals, key=lambda value: value.article.published_at)
        ]
        created_at = min(item.article.published_at for item in cluster_signals)
        latest_published_at = max(item.article.published_at for item in cluster_signals)
        cluster_id = self._build_cluster_id(member_articles)
        return StoryCluster(
            cluster_id=cluster_id,
            representative_title=representative.article.title,
            member_articles=member_articles,
            created_at=created_at,
            latest_published_at=latest_published_at,
        )

    def _choose_representative(self, cluster_signals: list[_ArticleSignals]) -> _ArticleSignals:
        def rank_key(item: _ArticleSignals) -> tuple[float, float, str]:
            timestamp_score = item.article.published_at.timestamp()
            title_quality = -self._title_quality_score(item.article.title)
            source_key = item.article.source.lower()
            return (timestamp_score, title_quality, source_key)

        return min(cluster_signals, key=rank_key)

    def _build_cluster_id(self, members: list[ClusterMemberArticle]) -> str:
        seed = "|".join(member.url for member in members)
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
        return f"cluster-{digest}"

    def _tokenize(self, text: str) -> set[str]:
        normalized = self._normalize_text(text)
        return {
            token.lower()
            for token in TOKEN_PATTERN.findall(normalized)
            if token.lower() not in STOPWORDS
            and token.lower() not in ROMANIAN_STOPWORDS
            and len(token) >= 3
        }

    def _salient_keywords(self, text: str, limit: int) -> set[str]:
        normalized = self._normalize_text(text)
        counter = Counter(
            token.lower()
            for token in TOKEN_PATTERN.findall(normalized)
            if token.lower() not in STOPWORDS
            and token.lower() not in ROMANIAN_STOPWORDS
            and len(token) >= 4
        )
        return {token for token, _ in counter.most_common(limit)}

    def _extract_entities(self, text: str) -> set[str]:
        entities: set[str] = set()
        normalized_text = self._normalize_text(text, fold_case=False)
        for match in ENTITY_PATTERN.findall(normalized_text):
            entity = " ".join(match.split()).strip()
            if len(entity) < 4:
                continue
            if entity.lower() in STOPWORDS or entity.lower() in ROMANIAN_STOPWORDS:
                continue
            entities.add(entity)
        return entities

    def _event_terms(self, text: str) -> set[str]:
        normalized = self._normalize_text(text)
        return {
            token.lower()
            for token in TOKEN_PATTERN.findall(normalized)
            if token.lower() not in STOPWORDS
            and token.lower() not in ROMANIAN_STOPWORDS
            and len(token) >= 4
        }

    def _normalize_article_metadata(self, article: NewsClusteringArticle) -> NewsClusteringArticle:
        normalized_title = self._normalize_title(article.title)
        normalized_content = self._normalize_text(article.content_text, fold_case=False)
        normalized_source = self._normalize_source_identity(article.source)
        normalized_category = self._normalize_category(
            article.source_category,
            normalized_source,
            normalized_title,
            normalized_content,
        )
        return article.model_copy(
            update={
                "title": normalized_title,
                "content_text": normalized_content,
                "source": normalized_source,
                "source_category": normalized_category,
            }
        )

    def _normalize_title(self, title: str) -> str:
        normalized = self._normalize_text(title, fold_case=False)
        normalized = re.sub(
            r"^(?:live(?:[ -]text)?|video|foto|breaking|update)\s*[:\-]+\s*",
            "",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"\s*(?:\||::| - )\s*", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip(" -:;,")
        return normalized

    def _normalize_text(self, text: str, fold_case: bool = True) -> str:
        if not text:
            return ""
        normalized = self._fix_mojibake(unescape(text))
        for source, target in sorted(
            EVENT_NORMALIZATION_MAP.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            normalized = re.sub(
                rf"\b{re.escape(source)}\b",
                target,
                normalized,
                flags=re.IGNORECASE,
            )
        normalized = normalized.replace("?", "'").replace("`", "'")
        normalized = unicodedata.normalize("NFKD", normalized)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = re.sub(r"[^0-9A-Za-z\u00C0-\u024F'\-\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized.lower() if fold_case else normalized

    def _fix_mojibake(self, text: str) -> str:
        if not any(marker in text for marker in MOJIBAKE_MARKERS):
            return text
        try:
            repaired = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            return repaired or text
        except UnicodeError:
            return text

    def _normalize_source_identity(self, source: str) -> str:
        normalized = self._normalize_text(source)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return SOURCE_CANONICAL_MAP.get(normalized, source)

    def _is_geopolitical_event_bundle(
        self,
        left: _ArticleSignals,
        right: _ArticleSignals,
        shared_entities: list[str],
        cross_source: bool,
        event_overlap: float,
        keyword_overlap: float,
        hours_apart: float,
    ) -> bool:
        if not cross_source or hours_apart > min(self.recency_window_hours, 18):
            return False
        shared_event_terms = left.event_terms & right.event_terms
        anchor_overlap = shared_event_terms & GEOPOLITICAL_EVENT_ANCHORS
        if len(anchor_overlap) >= 2 and len(shared_event_terms) >= 3 and event_overlap >= 0.28:
            return True
        if anchor_overlap and len(shared_event_terms) >= 4 and keyword_overlap >= 0.22:
            return True
        lowered_entities = {entity.lower() for entity in shared_entities}
        if anchor_overlap and lowered_entities & GEOPOLITICAL_EVENT_ANCHORS and len(shared_event_terms) >= 2 and event_overlap >= 0.2:
            return True
        return False

    def _is_regional_escalation_bundle(
        self,
        left: _ArticleSignals,
        right: _ArticleSignals,
        cross_source: bool,
        event_overlap: float,
        keyword_overlap: float,
        hours_apart: float,
    ) -> bool:
        if not cross_source or hours_apart > 18:
            return False
        left_terms = left.event_terms & REGIONAL_ESCALATION_TERMS
        right_terms = right.event_terms & REGIONAL_ESCALATION_TERMS
        combined_terms = left_terms | right_terms
        if "iran" not in combined_terms:
            return False
        gulf_side = {"golful", "emiratele", "ormuz", "porturi"}
        security_side = {"orientul", "mijlociu", "nave", "marines", "hamas", "atac"}
        has_cross_signal = (
            (left_terms & gulf_side and right_terms & security_side)
            or (right_terms & gulf_side and left_terms & security_side)
        )
        if has_cross_signal and (event_overlap >= 0.12 or keyword_overlap >= 0.18):
            return True
        shared_event_terms = left.event_terms & right.event_terms
        escalation_overlap = shared_event_terms & REGIONAL_ESCALATION_TERMS
        if "iran" in escalation_overlap and len(escalation_overlap) >= 2 and (event_overlap >= 0.16 or keyword_overlap >= 0.22):
            return True
        return False

    def _event_families(self, event_terms: set[str]) -> set[str]:
        families = {
            family
            for family, keywords in EVENT_FAMILY_KEYWORDS.items()
            if event_terms & keywords
        }
        return families

    def _regional_buckets(self, event_terms: set[str]) -> set[str]:
        return {
            bucket
            for bucket, keywords in REGIONAL_LOCATION_BUCKETS.items()
            if event_terms & keywords
        }

    def _is_event_family_hard_news_match(
        self,
        left: _ArticleSignals,
        right: _ArticleSignals,
        shared_entities: list[str],
        cross_source: bool,
        normalized_title_similarity: float,
        event_overlap: float,
        keyword_overlap: float,
        hours_apart: float,
    ) -> bool:
        if not cross_source or hours_apart > min(self.recency_window_hours, 18):
            return False
        if left.article.source_category in {"sport", "entertainment", "lifestyle"}:
            return False
        if right.article.source_category in {"sport", "entertainment", "lifestyle"}:
            return False
        shared_families = (left.event_families & right.event_families) & EVENT_FAMILY_MERGEABLE
        if not shared_families:
            return False
        if len(shared_entities) < 1:
            return False
        if not (left.regional_buckets & right.regional_buckets):
            return False
        if max(normalized_title_similarity, event_overlap, keyword_overlap) < 0.1:
            return False
        return True

    def _normalize_category(
        self,
        category: str | None,
        normalized_source: str,
        normalized_title: str,
        normalized_content: str,
    ) -> str | None:
        base_category = category or "general"
        text = f"{normalized_title} {normalized_content}".lower()
        sport_hits = sum(1 for term in SPORT_TERMS if term in text)
        sport_strong_hits = sum(1 for term in SPORT_STRONG_TERMS if term in text)
        hard_news_hits = sum(1 for term in HARD_NEWS_TERMS if term in text)
        entertainment_hits = sum(1 for term in ENTERTAINMENT_TERMS if term in text)
        human_interest_hits = sum(1 for term in HUMAN_INTEREST_TERMS if term in text)
        source_is_generalist = normalized_source in GENERALIST_SOURCES

        if base_category == "sport" and human_interest_hits >= 2 and hard_news_hits <= 1:
            return "entertainment"
        if base_category == "sport" and (hard_news_hits >= max(sport_hits, 1) or sport_strong_hits == 0):
            return "general"
        if base_category == "sport" and source_is_generalist and sport_strong_hits < 2:
            return "general"
        if base_category in {"entertainment", "lifestyle"} and hard_news_hits >= max(entertainment_hits + 2, 3):
            return "general"
        if base_category == "general" and sport_strong_hits >= 3 and hard_news_hits == 0:
            return "sport"
        if base_category == "general" and entertainment_hits >= 2 and hard_news_hits <= 1:
            return "entertainment"
        if base_category == "general" and human_interest_hits >= 2 and hard_news_hits <= 1:
            return "entertainment"
        return base_category

    def _normalized_title_similarity(self, left: str, right: str) -> float:
        left_tokens = {token.lower() for token in TOKEN_PATTERN.findall(left) if len(token) >= 3}
        right_tokens = {token.lower() for token in TOKEN_PATTERN.findall(right) if len(token) >= 3}
        return self._overlap_ratio(left_tokens, right_tokens)

    def _overlap_ratio(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        intersection = left & right
        denominator = min(len(left), len(right))
        if denominator == 0:
            return 0.0
        return len(intersection) / denominator

    def _decision_score(self, decision: ClusterDecision) -> float:
        entity_weight = min(len(decision.shared_entities), 4) * 0.08
        return (
            decision.title_similarity * 0.34
            + decision.keyword_overlap * 0.24
            + decision.body_overlap * 0.16
            + entity_weight
            - min(decision.hours_apart / max(self.recency_window_hours, 1), 1.0) * 0.1
        )

    def _title_quality_score(self, title: str) -> float:
        tokens = list(self._tokenize(title))
        informative_length = min(len(title), 140) / 140
        token_count_score = min(len(tokens), 12) / 12
        return informative_length + token_count_score
