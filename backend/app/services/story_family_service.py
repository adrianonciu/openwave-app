from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Iterable

from app.models.story_family import StoryFamily
from app.models.story_score import ScoredStoryCluster

STORY_FAMILY_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "story_family_state.json"
TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ɏ][0-9A-Za-zÀ-ɏ\-']{2,}")
STOPWORDS = {
    "alex", "azi", "care", "cele", "cei", "cum", "csm", "din", "dupa", "este", "fara", "fost",
    "guvern", "guvernul", "hotnews", "iccj", "insa", "luni", "mai", "marius", "news", "nou", "noul",
    "pentru", "prin", "psd", "reia", "romania", "romaniei", "romanian", "sau", "sunt", "toti",
    "vot", "votul", "ziua", "zf",
}


class StoryFamilyService:
    def __init__(self) -> None:
        self.state_path = STORY_FAMILY_STATE_PATH

    def attach_story_families(self, scored_clusters: list[ScoredStoryCluster]) -> dict[str, StoryFamily]:
        families = self._load_state()
        family_lookup = {family.id: family for family in families}
        for cluster in scored_clusters:
            family, reason = self._match_or_create_family(cluster, family_lookup)
            cluster.story_family_id = family.id
            cluster.family_attach_reason = reason
            self._update_family(family, cluster)
        self._persist_state(family_lookup.values())
        return dict(sorted(family_lookup.items()))

    def _match_or_create_family(
        self,
        cluster: ScoredStoryCluster,
        family_lookup: dict[str, StoryFamily],
    ) -> tuple[StoryFamily, str]:
        cluster_hints = self._cluster_hints(cluster)
        cluster_keywords = self._cluster_keywords(cluster)
        cluster_topic_hint = self._cluster_topic_hint(cluster, cluster_hints, cluster_keywords)

        hint_matches: list[tuple[int, StoryFamily]] = []
        keyword_matches: list[tuple[int, StoryFamily]] = []
        for family in family_lookup.values():
            hint_overlap = len(cluster_hints & set(family.event_hints or []))
            if hint_overlap:
                hint_matches.append((hint_overlap, family))
                continue
            keyword_overlap = len(cluster_keywords & self._family_keywords(family))
            if keyword_overlap >= 2:
                keyword_matches.append((keyword_overlap, family))

        if hint_matches:
            family = max(
                hint_matches,
                key=lambda item: (item[0], item[1].story_count, item[1].last_seen_timestamp),
            )[1]
            return family, "shared event hints"

        if keyword_matches:
            family = max(
                keyword_matches,
                key=lambda item: (item[0], item[1].story_count, item[1].last_seen_timestamp),
            )[1]
            return family, "shared topic keywords"

        family_id = self._build_family_id(cluster_topic_hint or cluster.cluster.representative_title)
        suffix = 2
        base_family_id = family_id
        while family_id in family_lookup:
            family_id = f"{base_family_id}_{suffix}"
            suffix += 1

        now = cluster.scored_at if cluster.scored_at.tzinfo else cluster.scored_at.replace(tzinfo=UTC)
        family = StoryFamily(
            id=family_id,
            topic_hint=cluster_topic_hint,
            first_seen_timestamp=now,
            last_seen_timestamp=now,
            story_count=0,
            source_count=0,
            event_hints=sorted(cluster_hints),
        )
        family_lookup[family.id] = family
        return family, "new story family"

    def _update_family(self, family: StoryFamily, cluster: ScoredStoryCluster) -> None:
        family.last_seen_timestamp = cluster.scored_at if cluster.scored_at.tzinfo else cluster.scored_at.replace(tzinfo=UTC)
        family.story_count += 1
        family.source_count = max(
            family.source_count,
            len({member.source for member in cluster.cluster.member_articles}),
        )
        merged_hints = set(family.event_hints or [])
        merged_hints.update(self._cluster_hints(cluster))
        family.event_hints = sorted(merged_hints)[:12]
        if not family.topic_hint:
            family.topic_hint = self._cluster_topic_hint(
                cluster,
                self._cluster_hints(cluster),
                self._cluster_keywords(cluster),
            )

    def _cluster_hints(self, cluster: ScoredStoryCluster) -> set[str]:
        hints = set(cluster.cluster_event_family_hints or [])
        for member in cluster.cluster.member_articles:
            hints.update(member.romanian_event_family_hints or [])
        return {hint for hint in hints if hint}

    def _cluster_keywords(self, cluster: ScoredStoryCluster) -> set[str]:
        text_parts = [cluster.cluster.representative_title]
        text_parts.extend(member.title for member in cluster.cluster.member_articles[:4])
        text = " ".join(part for part in text_parts if part)
        return {
            token.lower()
            for token in TOKEN_PATTERN.findall(text)
            if len(token) >= 4 and token.lower() not in STOPWORDS
        }

    def _family_keywords(self, family: StoryFamily) -> set[str]:
        tokens: set[str] = set()
        if family.topic_hint:
            tokens.update(self._tokenize_value(family.topic_hint))
        for hint in family.event_hints or []:
            tokens.update(self._tokenize_value(hint))
        return tokens

    def _cluster_topic_hint(
        self,
        cluster: ScoredStoryCluster,
        cluster_hints: set[str],
        cluster_keywords: set[str],
    ) -> str | None:
        if cluster_hints:
            return sorted(cluster_hints)[0]
        if cluster_keywords:
            return "_".join(sorted(cluster_keywords)[:3])
        return self._build_family_id(cluster.cluster.representative_title)

    def _tokenize_value(self, value: str) -> set[str]:
        return {
            token.lower()
            for token in TOKEN_PATTERN.findall(value.replace("_", " "))
            if len(token) >= 4 and token.lower() not in STOPWORDS
        }

    def _build_family_id(self, value: str | None) -> str:
        raw_value = (value or "story family").strip().lower()
        if raw_value and " " not in raw_value and "_" in raw_value:
            raw_value = raw_value.removeprefix("romanian_")
            tokens = [token for token in raw_value.split("_") if token and token not in STOPWORDS]
            if tokens:
                return "_".join(tokens[:4])
        ordered_tokens: list[str] = []
        for token in TOKEN_PATTERN.findall(raw_value):
            lowered = token.lower()
            if lowered in STOPWORDS or lowered in ordered_tokens:
                continue
            ordered_tokens.append(lowered)
        if not ordered_tokens:
            return "story_family"
        return "_".join(ordered_tokens[:4])

    def _load_state(self) -> list[StoryFamily]:
        if not self.state_path.exists():
            return []
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        families: list[StoryFamily] = []
        for item in payload.get("families", []):
            try:
                families.append(StoryFamily.model_validate(item))
            except Exception:
                continue
        return families

    def _persist_state(self, families: Iterable[StoryFamily]) -> None:
        ordered = sorted(families, key=lambda family: family.last_seen_timestamp, reverse=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(UTC).isoformat(),
            "families": [family.model_dump(mode="json") for family in ordered[:100]],
        }
        self.state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
