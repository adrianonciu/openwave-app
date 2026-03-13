from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re

from app.models.article_fetch import FetchedArticle
from app.models.news_cluster import (
    ClusterDecision,
    ClusterMemberArticle,
    NewsClusteringArticle,
    StoryCluster,
)

TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")
ENTITY_PATTERN = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|[A-Z]{2,}(?:\s+[A-Z]{2,}){0,2})\b")
STOPWORDS = {
    "about",
    "after",
    "amid",
    "also",
    "and",
    "another",
    "around",
    "because",
    "before",
    "behind",
    "between",
    "brief",
    "commentary",
    "could",
    "early",
    "from",
    "have",
    "into",
    "more",
    "news",
    "over",
    "says",
    "say",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "today",
    "under",
    "update",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
    "romania",
    "romanian",
    "world",
}


@dataclass
class _ArticleSignals:
    article: NewsClusteringArticle
    title_tokens: set[str]
    salient_keywords: set[str]
    body_keywords: set[str]
    entities: set[str]


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
        title_tokens = self._tokenize(article.title)
        salient_keywords = self._salient_keywords(article.title, limit=8)
        body_keywords = self._salient_keywords(article.content_text[:4000], limit=12)
        entities = self._extract_entities(f"{article.title}. {article.content_text[:1200]}")
        return _ArticleSignals(
            article=article,
            title_tokens=title_tokens,
            salient_keywords=salient_keywords,
            body_keywords=body_keywords,
            entities=entities,
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
        keyword_overlap = self._overlap_ratio(
            left.salient_keywords | left.body_keywords,
            right.salient_keywords | right.body_keywords,
        )
        body_overlap = self._overlap_ratio(left.body_keywords, right.body_keywords)
        shared_entities = sorted(left.entities & right.entities)

        strong_signal_count = 0
        if title_similarity >= 0.72:
            strong_signal_count += 1
        if keyword_overlap >= 0.58:
            strong_signal_count += 1
        if body_overlap >= 0.38:
            strong_signal_count += 1
        if len(shared_entities) >= 2:
            strong_signal_count += 1

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

        if strong_signal_count >= 2 and title_similarity >= 0.48:
            return ClusterDecision(
                status="merged",
                reason="multiple_strong_similarity_signals",
                title_similarity=title_similarity,
                keyword_overlap=keyword_overlap,
                body_overlap=body_overlap,
                shared_entities=shared_entities,
                hours_apart=hours_apart,
            )

        if (
            len(shared_entities) >= 3
            and keyword_overlap >= 0.55
            and body_overlap >= 0.28
            and title_similarity >= 0.34
        ):
            return ClusterDecision(
                status="merged",
                reason="shared_entities_and_keyword_alignment",
                title_similarity=title_similarity,
                keyword_overlap=keyword_overlap,
                body_overlap=body_overlap,
                shared_entities=shared_entities,
                hours_apart=hours_apart,
            )

        return ClusterDecision(
            status="separate",
            reason="similarity_below_conservative_threshold",
            title_similarity=title_similarity,
            keyword_overlap=keyword_overlap,
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
        return {
            token.lower()
            for token in TOKEN_PATTERN.findall(text)
            if token.lower() not in STOPWORDS and len(token) >= 3
        }

    def _salient_keywords(self, text: str, limit: int) -> set[str]:
        counter = Counter(
            token.lower()
            for token in TOKEN_PATTERN.findall(text)
            if token.lower() not in STOPWORDS and len(token) >= 4
        )
        return {token for token, _ in counter.most_common(limit)}

    def _extract_entities(self, text: str) -> set[str]:
        entities: set[str] = set()
        for match in ENTITY_PATTERN.findall(text):
            normalized = " ".join(match.split()).strip()
            if len(normalized) < 4:
                continue
            if normalized.lower() in STOPWORDS:
                continue
            entities.add(normalized)
        return entities

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
            decision.title_similarity * 0.4
            + decision.keyword_overlap * 0.25
            + decision.body_overlap * 0.2
            + entity_weight
            - min(decision.hours_apart / max(self.recency_window_hours, 1), 1.0) * 0.1
        )

    def _title_quality_score(self, title: str) -> float:
        tokens = list(self._tokenize(title))
        informative_length = min(len(title), 140) / 140
        token_count_score = min(len(tokens), 12) / 12
        return informative_length + token_count_score
