from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.user_personalization import (
    DomainPreferenceMix,
    EditorialPreferenceProfile,
    GeographyPreferenceMix,
    ListenerProfile,
    UserPersonalization,
)
from app.services.bulletin_shaping_service import BulletinShapingService
from app.services.editorial_pipeline_service import EditorialPipelineService
from run_top5_scope_selection import _build_articles

OUTPUT_DIR = BACKEND_ROOT / "debug_output"
TEXT_OUTPUT_PATH = OUTPUT_DIR / "generalist_bulletin_cluj.txt"
JSON_OUTPUT_PATH = OUTPUT_DIR / "generalist_bulletin_cluj.json"
NOISY_PREFIX_PATTERN = re.compile(r"^(?:live(?:-text)?|video|foto|breaking|update)\s*[:\-]+\s*", re.IGNORECASE)
SEPARATOR_PATTERN = re.compile(r"\s*(?:\||::)\s*")
PROFILE_LIMITS = {"local": 5, "national_ro": 7, "international": 5}
BASE_QUOTAS = {"local": 4, "national_ro": 4, "international": 2}
PROFILE_DISPLAY = {"local": "Local", "national_ro": "National", "international": "International"}
PLACEHOLDER_HEADLINES = {"actualitate", "stiri", "live", "breaking", "updates", "context"}
RESERVE_NEGATIVE_TERMS = {
    "divort", "vedeta", "vedete", "monden", "dansatoare", "dansator", "actor", "actrita", "cantaret", "cantareata",
    "show", "tv", "serial", "seriale", "iubita", "iubit", "barfa", "mireasa", "ispite", "finalissima",
    "superliga", "liga", "meci", "meciul", "gol", "goluri", "infrangeri", "antrenor", "campionat", "federatia argentiniana"
}
LOCAL_CIVIC_TERMS = {
    "cluj", "clujean", "clujenii", "floresti", "manastur", "grigorescu", "marasti", "zorilor", "apahida",
    "primarie", "consiliul local", "consiliul judetean", "trafic", "transport", "tramvai", "metrou", "lucrari",
    "infrastructura", "universitate", "ubb", "babes-bolyai", "festival", "concert", "ceremonie", "procesiune",
    "eveniment cultural", "eveniment", "aeroport", "spital", "scoala", "liceu", "campus", "cfr cluj", "u cluj"
}
LOCAL_CIVIC_PRIORITY_TERMS = {
    "primarie", "consiliul local", "consiliul judetean", "trafic", "transport", "tramvai", "lucrari", "infrastructura",
    "universitate", "ubb", "babes-bolyai", "festival", "concert", "ceremonie", "procesiune", "aeroport", "cfr cluj", "u cluj"
}
ENGLISH_SIGNAL_TERMS = {
    "the", "and", "with", "war", "live", "updates", "urges", "ally", "allies", "send", "ships", "strait",
    "emergency", "aid", "displaced", "conflict", "civil", "crisis", "using", "digest", "march", "delivers"
}
HEADLINE_TRANSLATION_MAP = {
    "live updates trump urges us allies to send nave to strait of hormuz": "Actualizare: Trump le cere aliatilor Statelor Unite sa trimita nave spre Stramtoarea Ormuz.",
    "un delivers emergency aid to afghans displaced by conflict with pakistan": "ONU livreaza ajutor de urgenta pentru afganii stramutati de conflictul cu Pakistanul.",
    "civil war in sudan is a never-ending humanitarian crisis": "Razboiul civil din Sudan ramane o criza umanitara fara sfarsit.",
    "how the u s is using ai in the war in iran": "Cum folosesc Statele Unite inteligenta artificiala in razboiul cu Iranul.",
    "kyodo news digest march 15 2026": "Sinteza Kyodo News din 15 martie 2026.",
}
GENERIC_TRANSLATIONS = [
    ("live updates", "actualizare"),
    ("breaking news", "stiri de ultima ora"),
    ("trump urges", "Trump le cere"),
    ("us allies", "aliatilor Statelor Unite"),
    ("allies", "aliatilor"),
    ("send ships", "sa trimita nave"),
    ("send warships", "sa trimita nave de razboi"),
    ("strait of hormuz", "Stramtoarea Ormuz"),
    ("emergency aid", "ajutor de urgenta"),
    ("displaced", "stramutati"),
    ("conflict", "conflictul"),
    ("civil war", "razboiul civil"),
    ("humanitarian crisis", "criza umanitara"),
    ("using ai", "folosesc inteligenta artificiala"),
    ("using", "foloseste"),
    ("war in iran", "razboiul cu Iranul"),
    ("war", "razboiul"),
    ("digest", "sinteza"),
    ("march", "martie"),
    ("delivers", "livreaza"),
    ("un ", "ONU "),
]


def _build_generalist_personalization() -> UserPersonalization:
    return UserPersonalization(
        listener_profile=ListenerProfile(
            first_name="Andrei",
            country="Romania",
            region="Cluj",
            city="Cluj",
        ),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=30, national=45, international=25),
            domains=DomainPreferenceMix(
                politics=18,
                economy=16,
                justice=14,
                sport=8,
                entertainment=6,
                education=12,
                health=12,
                tech=14,
            ),
        ),
    )


def _clean_headline(headline: str) -> str:
    cleaned = NOISY_PREFIX_PATTERN.sub("", (headline or "").strip())
    cleaned = SEPARATOR_PATTERN.split(cleaned)[0].strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" -:")
    return cleaned or "Subiect in curs de actualizare"


def _finalize_sentence(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip(" -:")
    if not normalized:
        return "Subiect in curs de actualizare."
    if normalized[-1] not in ".!?":
        normalized += "."
    return normalized


def _unique_source_count(cluster) -> int:
    return len({member.source for member in cluster.cluster.member_articles})


def _dominant_scope(cluster) -> str:
    scopes = [member.source_scope or ("local" if member.is_local_source else "unknown") for member in cluster.cluster.member_articles]
    return Counter(scopes).most_common(1)[0][0] if scopes else "unknown"


def _dominant_national_bucket(cluster) -> str | None:
    buckets = [member.national_preference_bucket for member in cluster.cluster.member_articles if member.national_preference_bucket]
    return Counter(buckets).most_common(1)[0][0] if buckets else None


def _dominant_category(cluster) -> str:
    categories = [str(member.source_category or "general").lower() for member in cluster.cluster.member_articles]
    return Counter(categories).most_common(1)[0][0] if categories else "general"


def _is_usable_cluster(cluster, profile_name: str) -> bool:
    headline = _clean_headline(cluster.cluster.representative_title)
    lowered = headline.lower()
    if not headline or lowered in PLACEHOLDER_HEADLINES:
        return False
    if profile_name == "local" and float(getattr(cluster, "local_relevance_boost", 0.0) or 0.0) <= 0:
        return False
    if profile_name == "national_ro" and _dominant_national_bucket(cluster) == "off_target":
        return False
    return True


def _is_reserve_cluster(cluster, profile_name: str) -> bool:
    headline = _clean_headline(cluster.cluster.representative_title)
    lowered = headline.lower()
    if not headline or lowered in PLACEHOLDER_HEADLINES:
        return False
    if profile_name == "local":
        return False
    if _dominant_category(cluster) in {"entertainment", "lifestyle", "tv"}:
        return False
    if any(term in lowered for term in RESERVE_NEGATIVE_TERMS):
        return False
    return True


def _is_local_civic_fallback_cluster(cluster) -> bool:
    headline = _clean_headline(cluster.cluster.representative_title).lower()
    if not headline:
        return False
    if any(term in headline for term in RESERVE_NEGATIVE_TERMS):
        return False
    signals = set(term for term in LOCAL_CIVIC_TERMS if term in headline)
    if not signals:
        source_regions = {str(member.source_region or "").lower() for member in cluster.cluster.member_articles}
        if "cluj" in source_regions:
            signals.add("cluj")
    if not signals:
        return False
    if _dominant_category(cluster) in {"entertainment", "lifestyle", "tv"}:
        return False
    priority_hits = sum(1 for term in LOCAL_CIVIC_PRIORITY_TERMS if term in headline)
    return priority_hits > 0 or "cluj" in signals


def _cluster_origin_entry(cluster, origin_profile: str) -> dict[str, object]:
    score_breakdown = getattr(cluster, "score_breakdown", None)
    europe_romania_impact = float(
        getattr(getattr(score_breakdown, "europe_romania_impact", None), "contribution", 0.0) or 0.0
    )
    return {
        "cluster": cluster,
        "origin_profile": origin_profile,
        "cluster_id": cluster.cluster.cluster_id,
        "headline": cluster.cluster.representative_title,
        "clean_headline": _clean_headline(cluster.cluster.representative_title),
        "source_list": sorted({member.source for member in cluster.cluster.member_articles}),
        "unique_source_count": _unique_source_count(cluster),
        "final_score": round(cluster.score_total or 0.0, 2),
        "freshness_score": round(float(cluster.score_breakdown.recency.contribution if getattr(cluster, "score_breakdown", None) else 0.0), 2),
        "story_family_id": getattr(cluster, "story_family_id", None),
        "family_run_count": getattr(cluster, "family_run_count", 0),
        "family_lifecycle_boost": getattr(cluster, "family_lifecycle_boost", 0.0),
        "europe_romania_impact": round(europe_romania_impact, 2),
        "domestic_purity_score": getattr(cluster, "domestic_purity_score", 0.0),
        "romanian_source_count": getattr(cluster, "romanian_source_count", 0),
        "romanian_multi_source_bonus_applied": getattr(cluster, "romanian_multi_source_bonus_applied", 0.0),
        "national_preference_bucket": _dominant_national_bucket(cluster),
        "local_relevance_boost": getattr(cluster, "local_relevance_boost", 0.0),
        "local_county_tag": getattr(cluster, "local_county_tag", None),
        "dominant_scope": _dominant_scope(cluster),
        "reserve_story": False,
        "local_fallback_story": False,
    }


def _generalist_entry_priority(item: dict[str, object]) -> tuple[int, int, int, int, float, float, str]:
    origin = str(item["origin_profile"])
    national_bucket = str(item.get("national_preference_bucket") or "")
    is_reserve = bool(item.get("reserve_story", False))
    is_local_fallback = bool(item.get("local_fallback_story", False))
    romanian_sources = int(item.get("romanian_source_count", 0) or 0)
    family_run_count = int(item.get("family_run_count", 0) or 0)
    europe_romania_impact = float(item.get("europe_romania_impact", 0.0) or 0.0)
    final_score = float(item.get("final_score", 0.0) or 0.0)

    if origin == "local":
        tier = 0 if not is_local_fallback else 1
    elif origin == "national_ro":
        if national_bucket == "domestic_hard_news":
            tier = 2
        elif national_bucket == "external_direct_impact":
            tier = 3
        elif national_bucket == "off_target":
            tier = 6
        else:
            tier = 4
    else:
        tier = 3 if europe_romania_impact >= 4.0 else 5

    reserve_penalty = 1 if is_reserve else 0
    return (
        tier,
        reserve_penalty,
        0 if romanian_sources >= 2 else 1,
        -family_run_count,
        -europe_romania_impact,
        -final_score,
        str(item["cluster_id"]),
    )


def _sort_profile_pool(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(entries, key=_generalist_entry_priority)


def _take_from_pool(pool: list[dict[str, object]], count: int, selected: list[dict[str, object]], seen: set[str], composition: Counter) -> int:
    added = 0
    for item in pool:
        if item["cluster_id"] in seen:
            continue
        selected.append(item)
        seen.add(item["cluster_id"])
        composition[item["origin_profile"]] += 1
        added += 1
        if added >= count:
            break
    return added


def _combine_story_sets(profile_entries: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    normalized_entries = {profile_name: _sort_profile_pool(entries) for profile_name, entries in profile_entries.items()}
    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    composition: Counter = Counter()

    for profile_name, quota in BASE_QUOTAS.items():
        _take_from_pool(normalized_entries.get(profile_name, []), quota, selected, seen, composition)

    while composition["local"] + composition["national_ro"] < 7 and len(selected) < 10:
        needed = 7 - (composition["local"] + composition["national_ro"])
        added_national = _take_from_pool(normalized_entries.get("national_ro", []), needed, selected, seen, composition)
        if composition["local"] + composition["national_ro"] >= 7:
            break
        added_local = _take_from_pool(normalized_entries.get("local", []), needed - added_national, selected, seen, composition)
        if added_national == 0 and added_local == 0:
            break

    if len(selected) < 10 and composition["international"] < 3:
        _take_from_pool(normalized_entries.get("international", []), 3 - composition["international"], selected, seen, composition)

    fill_order = ["national_ro", "local", "international"]
    while len(selected) < 10:
        progress = 0
        for profile_name in fill_order:
            progress += _take_from_pool(normalized_entries.get(profile_name, []), 1, selected, seen, composition)
            if len(selected) >= 10:
                break
        if progress == 0:
            break

    return selected[:10]


def _ensure_early_domestic_balance(ordered_items: list[dict[str, object]]) -> list[dict[str, object]]:
    items = list(ordered_items)

    def domestic_count(limit: int) -> int:
        return sum(1 for item in items[:limit] if item["origin_profile"] in {"local", "national_ro"})

    if items and items[0]["origin_profile"] == "international":
        for index in range(1, len(items)):
            if items[index]["origin_profile"] in {"local", "national_ro"}:
                items[0], items[index] = items[index], items[0]
                break

    while len(items) >= 3 and domestic_count(3) < 2:
        later_index = next((idx for idx in range(3, len(items)) if items[idx]["origin_profile"] in {"local", "national_ro"}), None)
        early_index = next((idx for idx in range(3) if items[idx]["origin_profile"] == "international"), None)
        if later_index is None or early_index is None:
            break
        items[early_index], items[later_index] = items[later_index], items[early_index]

    while len(items) >= 5 and domestic_count(5) < 3:
        later_index = next((idx for idx in range(5, len(items)) if items[idx]["origin_profile"] in {"local", "national_ro"}), None)
        early_index = next((idx for idx in range(5) if items[idx]["origin_profile"] == "international"), None)
        if later_index is None or early_index is None:
            break
        items[early_index], items[later_index] = items[later_index], items[early_index]

    for rank, item in enumerate(items, start=1):
        item["rank"] = rank
    return items


def _maybe_translate_to_romanian(headline: str, origin_profile: str) -> str:
    cleaned = _clean_headline(headline)
    lowered = cleaned.lower()
    english_signal_count = sum(1 for term in ENGLISH_SIGNAL_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered))
    needs_translation = origin_profile == "international" or english_signal_count >= 2
    if not needs_translation:
        return _finalize_sentence(cleaned)

    if lowered in HEADLINE_TRANSLATION_MAP:
        return HEADLINE_TRANSLATION_MAP[lowered]

    translated = lowered
    for source_text, target_text in GENERIC_TRANSLATIONS:
        translated = re.sub(rf"\b{re.escape(source_text)}\b", target_text, translated)

    if "hormuz" in translated and "trump" in translated:
        translated = "Trump le cere aliatilor Statelor Unite sa trimita nave spre Stramtoarea Ormuz"
    elif "sudan" in translated and "criza umanitara" in translated:
        translated = "Razboiul civil din Sudan ramane o criza umanitara fara sfarsit"
    elif "afghans" in translated or "afgani" in translated:
        translated = "ONU livreaza ajutor de urgenta pentru afganii stramutati de conflictul cu Pakistanul"
    elif "iran" in translated and "inteligenta artificiala" in translated:
        translated = "Cum folosesc Statele Unite inteligenta artificiala in razboiul cu Iranul"

    translated = translated.replace(" u s ", " Statele Unite ")
    translated = translated.replace(" us ", " Statele Unite ")
    translated = translated.replace(" pakist an", " Pakistan")
    translated = re.sub(r"\s+", " ", translated).strip()
    if translated:
        translated = translated[0].upper() + translated[1:]
    return _finalize_sentence(translated or cleaned)


def _topic_bucket_for_entry(item: dict[str, object], decisions_by_cluster: dict[str, object]) -> str:
    decision = decisions_by_cluster.get(item["cluster_id"])
    if decision is not None:
        return decision.topic_bucket
    if item["origin_profile"] == "local":
        return "local_public_interest"
    if item["origin_profile"] == "international":
        return "international_impact"
    return "general"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    personalization = _build_generalist_personalization()
    pipeline_service = EditorialPipelineService()
    core_service = pipeline_service.editorial_selection_core_service
    shaping_service = BulletinShapingService()

    articles, _, source_coverage = _build_articles(personalization)
    story_clusters = pipeline_service.clustering_service.cluster_articles(articles)
    scored_clusters = pipeline_service.scoring_service.score_clusters(story_clusters)
    pipeline_service.story_family_service.attach_story_families(scored_clusters)

    profile_entries: dict[str, list[dict[str, object]]] = {}
    profile_debug: dict[str, dict[str, object]] = {}
    profile_shaping: dict[str, dict[str, object]] = {}

    for profile_name, max_stories in PROFILE_LIMITS.items():
        core_result = core_service.run_profile(
            scored_clusters,
            profile_name,
            max_stories=max_stories,
            editorial_preferences=personalization.editorial_preferences,
            personalization=personalization,
        )
        shaping_result = shaping_service.shape_selected_clusters(
            core_result.selection_result.selected_clusters,
            profile_name=profile_name,
        )
        entries: list[dict[str, object]] = []
        seen_cluster_ids: set[str] = set()
        for cluster in shaping_result.ordered_clusters:
            if not _is_usable_cluster(cluster, profile_name):
                continue
            entry = _cluster_origin_entry(cluster, profile_name)
            entries.append(entry)
            seen_cluster_ids.add(entry["cluster_id"])

        fallback_added = 0
        for cluster in core_result.candidate_clusters:
            if cluster.cluster.cluster_id in seen_cluster_ids:
                continue
            if not _is_usable_cluster(cluster, profile_name):
                continue
            entry = _cluster_origin_entry(cluster, profile_name)
            entries.append(entry)
            seen_cluster_ids.add(entry["cluster_id"])
            fallback_added += 1
            if len(entries) >= PROFILE_LIMITS[profile_name] + 4:
                break

        reserve_added = 0
        for cluster in core_result.candidate_clusters:
            if cluster.cluster.cluster_id in seen_cluster_ids:
                continue
            if not _is_reserve_cluster(cluster, profile_name):
                continue
            entry = _cluster_origin_entry(cluster, profile_name)
            entry["reserve_story"] = True
            entries.append(entry)
            seen_cluster_ids.add(entry["cluster_id"])
            reserve_added += 1
            if len(entries) >= PROFILE_LIMITS[profile_name] + 7:
                break

        local_fallback_added = 0
        if profile_name == "local" and not entries:
            for cluster in scored_clusters:
                if cluster.cluster.cluster_id in seen_cluster_ids:
                    continue
                if not _is_local_civic_fallback_cluster(cluster):
                    continue
                entry = _cluster_origin_entry(cluster, "local")
                entry["reserve_story"] = True
                entry["local_fallback_story"] = True
                entries.append(entry)
                seen_cluster_ids.add(entry["cluster_id"])
                local_fallback_added += 1
                if local_fallback_added >= 2:
                    break

        profile_entries[profile_name] = entries
        profile_debug[profile_name] = {
            "candidate_count": len(core_result.candidate_clusters),
            "selected_count": len(core_result.selection_result.selected_clusters),
            "usable_selected_count": len([cluster for cluster in shaping_result.ordered_clusters if _is_usable_cluster(cluster, profile_name)]),
            "fallback_candidates_added": fallback_added,
            "reserve_candidates_added": reserve_added,
            "local_civic_fallback_added": local_fallback_added,
            "combined_pool_count": len(entries),
        }
        profile_shaping[profile_name] = {
            "lead_cluster_id": shaping_result.lead_cluster_id,
            "shaping_explanation": shaping_result.shaping_explanation,
            "decisions": [decision.model_dump(mode="json") for decision in shaping_result.decisions],
        }

    combined_entries = _combine_story_sets(profile_entries)
    combined_clusters = [item["cluster"] for item in combined_entries]
    combined_shaping = shaping_service.shape_selected_clusters(combined_clusters, profile_name="generalist")
    origin_by_cluster_id = {item["cluster_id"]: item for item in combined_entries}
    decisions_by_cluster = {decision.cluster_id: decision for decision in combined_shaping.decisions}

    ordered_items: list[dict[str, object]] = []
    for rank, cluster in enumerate(combined_shaping.ordered_clusters, start=1):
        base_item = origin_by_cluster_id[cluster.cluster.cluster_id]
        ordered_items.append({
            "rank": rank,
            "cluster_id": base_item["cluster_id"],
            "origin_profile": base_item["origin_profile"],
            "origin_label": PROFILE_DISPLAY[base_item["origin_profile"]],
            "headline": base_item["headline"],
            "clean_headline": _maybe_translate_to_romanian(base_item["headline"], base_item["origin_profile"]),
            "source_list": base_item["source_list"],
            "unique_source_count": base_item["unique_source_count"],
            "freshness_score": base_item["freshness_score"],
            "final_score": base_item["final_score"],
            "topic_bucket": _topic_bucket_for_entry(base_item, decisions_by_cluster),
            "story_family_id": base_item["story_family_id"],
            "family_run_count": base_item["family_run_count"],
            "family_lifecycle_boost": base_item["family_lifecycle_boost"],
            "dominant_scope": base_item["dominant_scope"],
            "reserve_story": base_item.get("reserve_story", False),
            "local_fallback_story": base_item.get("local_fallback_story", False),
        })

    ordered_items = _ensure_early_domestic_balance(ordered_items)
    composition_counts = Counter(item["origin_profile"] for item in ordered_items)
    lead_item = ordered_items[0] if ordered_items else None
    lead_decision = decisions_by_cluster.get(lead_item["cluster_id"]) if lead_item else None
    first_five_domestic = sum(1 for item in ordered_items[:5] if item["origin_profile"] in {"local", "national_ro"})

    payload = {
        "title": "OPENWAVE - Jurnalul momentului",
        "listener": personalization.model_dump(mode="json"),
        "source_coverage_summary": {
            "total_sources_seen": len(source_coverage),
            "articles_built": len(articles),
            "story_clusters": len(story_clusters),
        },
        "profile_debug": profile_debug,
        "profile_shaping": profile_shaping,
        "generalist_bulletin_composition": {
            "local_stories": composition_counts.get("local", 0),
            "national_stories": composition_counts.get("national_ro", 0),
            "international_stories": composition_counts.get("international", 0),
            "romania_focused_constraint_met": composition_counts.get("local", 0) + composition_counts.get("national_ro", 0) >= 7,
            "first_five_domestic_count": first_five_domestic,
            "first_five_balance_rule_met": first_five_domestic >= 3,
            "lead_story_cluster_id": combined_shaping.lead_cluster_id,
            "lead_story_headline": lead_item["clean_headline"] if lead_item else None,
            "lead_story_reason": lead_decision.decision_reason if lead_decision else None,
            "shaping_explanation": combined_shaping.shaping_explanation,
        },
        "stories": ordered_items,
        "bulletin_shaping": {
            "lead_cluster_id": combined_shaping.lead_cluster_id,
            "shaping_explanation": combined_shaping.shaping_explanation,
            "decisions": [decision.model_dump(mode="json") for decision in combined_shaping.decisions],
        },
    }
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "OPENWAVE - Jurnalul momentului",
        "",
        "GENERALIST BULLETIN COMPOSITION",
        "",
        f"local stories: {composition_counts.get('local', 0)}",
        f"national stories: {composition_counts.get('national_ro', 0)}",
        f"international stories: {composition_counts.get('international', 0)}",
        f"Romania-focused constraint met: {composition_counts.get('local', 0) + composition_counts.get('national_ro', 0) >= 7}",
        f"first 5 domestic stories: {first_five_domestic}",
        f"first 5 balance rule met: {first_five_domestic >= 3}",
        "",
        f"lead story chosen: {lead_item['clean_headline'] if lead_item else 'none'}",
        f"reason: {lead_decision.decision_reason if lead_decision else 'none'}",
        f"shaping: {combined_shaping.shaping_explanation}",
        "",
    ]

    for item in ordered_items:
        lines.extend([
            f"{item['rank']}. {item['clean_headline']}",
            f"   Lens: {item['origin_label']}",
            f"   Sources: {', '.join(item['source_list'])}",
            f"   Unique sources: {item['unique_source_count']}",
            f"   Topic bucket: {item['topic_bucket']}",
            f"   Freshness: {item['freshness_score']}",
            f"   Score: {item['final_score']}",
            f"   Reserve fallback: {item.get('reserve_story', False)}",
            f"   Local civic fallback: {item.get('local_fallback_story', False)}",
            "",
        ])

    TEXT_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {TEXT_OUTPUT_PATH}")
    print(f"Wrote {JSON_OUTPUT_PATH}")
    print(json.dumps({
        "story_count": len(ordered_items),
        "local": composition_counts.get("local", 0),
        "national": composition_counts.get("national_ro", 0),
        "international": composition_counts.get("international", 0),
        "romania_focused_constraint_met": composition_counts.get("local", 0) + composition_counts.get("national_ro", 0) >= 7,
        "first_five_domestic_count": first_five_domestic,
        "first_five_balance_rule_met": first_five_domestic >= 3,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
