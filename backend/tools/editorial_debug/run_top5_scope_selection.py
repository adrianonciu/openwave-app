from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path
from urllib.parse import urlparse
import json
import re
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.article_fetch import FetchedArticle
from app.models.user_personalization import (
    DomainPreferenceMix,
    EditorialPreferenceProfile,
    GeographyPreferenceMix,
    ListenerProfile,
    UserPersonalization,
)
from app.services.article_fetch_service import ArticleFetchService
from app.services.article_service import ArticleService
from app.services.editorial_pipeline_service import EditorialPipelineService
from app.services.source_watcher_service import SourceWatcherService

OUTPUT_DIR = BACKEND_ROOT / "debug_output"
NATIONAL_JSON_OUTPUT_PATH = OUTPUT_DIR / "top5_national_selection.json"
NATIONAL_TEXT_OUTPUT_PATH = OUTPUT_DIR / "top5_national_selection.txt"
GLOBAL_JSON_OUTPUT_PATH = OUTPUT_DIR / "top5_global_selection.json"
GLOBAL_TEXT_OUTPUT_PATH = OUTPUT_DIR / "top5_global_selection.txt"
STORY_SELECTION_DEBUG_JSON_PATH = OUTPUT_DIR / "story_selection_debug.json"
STORY_SELECTION_DEBUG_TEXT_PATH = OUTPUT_DIR / "story_selection_debug.txt"
INTERNATIONAL_MERGE_DEBUG_JSON_PATH = OUTPUT_DIR / "international_merge_debug.json"
INTERNATIONAL_MERGE_DEBUG_TEXT_PATH = OUTPUT_DIR / "international_merge_debug.txt"
CANDIDATE_POOL_AUDIT_JSON_PATH = OUTPUT_DIR / "candidate_pool_audit.json"
CANDIDATE_POOL_AUDIT_TEXT_PATH = OUTPUT_DIR / "candidate_pool_audit.txt"
INTERNATIONAL_SOURCE_COVERAGE_JSON_PATH = OUTPUT_DIR / "international_source_coverage.json"
INTERNATIONAL_SOURCE_COVERAGE_TEXT_PATH = OUTPUT_DIR / "international_source_coverage.txt"
MAX_INPUT_ARTICLES = 20
MAX_RSS_FALLBACK_ARTICLES = 6
MAX_SOURCE_FETCH_ATTEMPTS = 32
TOKEN_PATTERN = re.compile(r"[0-9A-Za-z\u00C0-\u024F][0-9A-Za-z\u00C0-\u024F\-']*")
NOISY_PREFIX_PATTERN = re.compile(r"^(?:live(?:-text)?|video|foto|breaking|update)\s*[:\-]+\s*", re.IGNORECASE)
SEPARATOR_PATTERN = re.compile(r"\s*(?:\||::| - |  |  )\s*")
LIKELY_EVENT_TERMS = {
    "iran", "golful", "emiratele", "ormuz", "porturi", "marines", "mijlociu", "orientul", "hamas",
    "nato", "eu", "brussels", "sanctions", "atac", "ambasada", "ukraine", "ucraina", "moldova",
}
LOCATION_TERMS = {
    "iran", "emiratele", "golful", "ormuz", "bagdad", "brussels", "romania", "ukraine", "ucraina", "moldova",
    "balkans", "balcani", "black sea", "marea neagra", "germany", "belarus",
}
NATIONAL_PREFERENCE_BUCKET_ORDER = {
    "domestic_hard_news": 0,
    "external_direct_impact": 1,
    "off_target": 2,
}
ROMANIAN_DOMESTIC_HARD_NEWS_TERMS = {
    "guvern", "guvernul", "parlament", "parlamentul", "presedinte", "presedintia", "alegeri", "electoral",
    "partid", "psd", "pnl", "usr", "senat", "senatul", "camera deputatilor", "deputati", "primarie",
    "consiliul", "ministru", "minister", "ministerul", "procuror", "procurorii", "instanta", "justitie",
    "tribunal", "curte", "ccr", "dna", "diicot", "taxe", "impozit", "buget", "inflatie", "bnr",
    "energie", "infrastructura", "autostrada", "spital", "sanatate", "educatie", "scoala", "protest",
    "proteste", "greva", "administratie", "romania", "bucuresti", "cluj", "iasi", "constanta",
}
ROMANIAN_EXTERNAL_DIRECT_IMPACT_TERMS = {
    "uniunea europeana", "ue", "nato", "schengen", "ucraina", "ukraine", "moldova", "transnistria",
    "marea neagra", "black sea", "rusia", "razboi", "war", "gaz", "energie", "border",
    "migratie", "defence", "defense", "securitate", "bruxelles", "brussels", "tarife",
}
ROMANIAN_OFF_TARGET_TERMS = {
    "vedeta", "celebru", "monden", "lifestyle", "sport", "superliga", "liga", "meci", "scor", "gol",
    "whatsapp", "instagram", "facebook", "fenomen", "anorexia financiara", "seriale", "tv", "show",
}

ROMANIAN_INSTITUTION_TERMS = {
    "guvern": 3,
    "guvernul": 3,
    "parlament": 3,
    "parlamentul": 3,
    "senat": 3,
    "senatul": 3,
    "camera deputatilor": 3,
    "presedintie": 3,
    "presedintia": 3,
    "administratia prezidentiala": 3,
    "minister": 3,
    "ministerul": 3,
    "ministerului": 3,
    "anaf": 4,
    "bnr": 4,
    "bvb": 3,
    "bursa de valori bucuresti": 3,
    "ccr": 4,
    "curtea constitutionala": 4,
    "dna": 4,
    "diicot": 4,
    "iccj": 4,
    "inalta curte": 4,
    "instanta": 3,
    "instantei": 3,
    "tribunal": 3,
    "curte de apel": 3,
    "procuror": 3,
    "procurorii": 3,
    "procurorilor": 3,
    "primarie": 3,
    "primarul": 3,
    "consiliul judetean": 3,
    "prefect": 3,
}

ROMANIAN_POLITICAL_ACTOR_TERMS = {
    "premier": 3,
    "prim-ministru": 3,
    "ministru": 3,
    "ministrul": 3,
    "deputat": 2,
    "deputatii": 2,
    "senator": 2,
    "senatorii": 2,
    "primar": 2,
    "consiliul": 2,
    "psd": 3,
    "pnl": 3,
    "usr": 3,
    "udmr": 3,
    "aur": 3,
    "coalitia de guvernare": 3,
}

ROMANIAN_PUBLIC_IMPACT_TERMS = {
    "alegeri": 2,
    "electoral": 2,
    "buget": 3,
    "deficit": 3,
    "taxe": 3,
    "impozit": 3,
    "impozite": 3,
    "fiscal": 3,
    "inflatie": 3,
    "salariu minim": 3,
    "pensii": 3,
    "energie": 2,
    "gaze": 2,
    "electricitate": 2,
    "infrastructura": 2,
    "autostrada": 2,
    "autostrazi": 2,
    "cale ferata": 2,
    "metrou": 2,
    "spital": 2,
    "spitale": 2,
    "educatie": 2,
    "scoala": 2,
    "scoli": 2,
    "munca": 2,
    "somaj": 2,
    "salarii": 2,
    "preturi": 2,
    "facturi": 2,
    "subventii": 2,
    "fonduri": 2,
    "licitatie": 2,
    "trafic rutier": 2,
}

ROMANIAN_PUBLIC_ECONOMY_TERMS = {
    "hidroelectrica": 3,
    "romgaz": 3,
    "transgaz": 3,
    "transelectrica": 3,
    "nuclearelectrica": 3,
    "metrorex": 3,
    "cfr": 3,
    "tarom": 3,
    "compania nationala": 2,
}

ROMANIAN_ADMINISTRATIVE_AREAS = {
    "romania",
    "romaniei",
    "bucuresti",
    "bucurestiului",
    "cluj",
    "iasi",
    "constanta",
    "timis",
    "timisoara",
    "sibiu",
    "brasov",
    "dolj",
    "craiova",
    "prahova",
    "ploiesti",
    "ilfov",
    "arad",
    "oradea",
    "bacau",
    "galati",
    "suceava",
    "mures",
}

ROMANIAN_GOVERNANCE_CONTEXT_TERMS = {
    "primarie",
    "consiliul",
    "consiliu",
    "prefect",
    "prefectura",
    "ministru",
    "minister",
    "ministerul",
    "guvern",
    "guvernul",
    "buget",
    "taxe",
    "impozit",
    "investitie",
    "investitii",
    "infrastructura",
    "trafic",
    "proiect",
    "licitatie",
    "spital",
    "scoala",
}

ROMANIAN_LIFESTYLE_NEGATIVE_TERMS = {
    "lifestyle": 4,
    "wellness": 4,
    "sanatate personala": 4,
    "dieta": 4,
    "nutritie": 4,
    "slabire": 4,
    "psiholog": 3,
    "psihologii": 3,
    "relatii": 3,
    "frumusete": 4,
    "moda": 4,
    "vacanta": 3,
    "vedeta": 4,
    "monden": 4,
    "show": 3,
}

ROMANIAN_PERSONAL_FINANCE_NEGATIVE_TERMS = {
    "economisire": 4,
    "economisirea": 4,
    "cheltui": 4,
    "cheltuieli personale": 4,
    "bani": 3,
    "card": 3,
    "credit": 3,
    "rate": 3,
    "finante personale": 4,
    "sfaturi": 4,
}

ROMANIAN_SOFT_FEATURE_NEGATIVE_TERMS = {
    "fenomen": 3,
    "trend": 3,
    "poveste": 3,
    "cum sa": 4,
    "top": 3,
    "cele mai": 3,
    "explicatii": 2,
    "de ce": 2,
}

ROMANIAN_GENERIC_CORPORATE_NEGATIVE_TERMS = {
    "compania": 3,
    "companie": 3,
    "corporatie": 3,
    "ceo": 4,
    "facebook": 3,
    "instagram": 3,
    "whatsapp": 3,
    "meta": 3,
    "google": 3,
    "amazon": 3,
    "apple": 3,
    "tesla": 3,
    "microsoft": 3,
    "openai": 3,
    "angajati": 2,
    "forta de munca": 2,
    "inteligenta artificiala": 2,
    "nasdaq": 2,
    "reuters": 1,
}


def _article_classifier_text(article: FetchedArticle) -> str:
    return f"{article.title} {article.content_text}".lower()


def _article_classifier_tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def _text_contains_term(text: str, term: str) -> bool:
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    pattern = rf"(?<![0-9A-Za-z\u00C0-\u024F]){escaped}(?![0-9A-Za-z\u00C0-\u024F])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _matched_terms(text: str, weighted_terms: dict[str, int]) -> list[tuple[str, int]]:
    return [(term, weight) for term, weight in weighted_terms.items() if _text_contains_term(text, term)]


def _signal_labels(prefix: str, matches: list[tuple[str, int]]) -> list[str]:
    return [f"{prefix}:{term}" for term, _ in sorted(matches, key=lambda item: (-item[1], item[0]))]


def _has_governance_location_signal(text: str) -> tuple[bool, list[str]]:
    locations = sorted(term for term in ROMANIAN_ADMINISTRATIVE_AREAS if _text_contains_term(text, term))
    context = sorted(term for term in ROMANIAN_GOVERNANCE_CONTEXT_TERMS if _text_contains_term(text, term))
    if locations and context:
        return True, [f"governance_location:{locations[0]}", f"governance_context:{context[0]}"]
    return False, []


def _classify_romanian_national_preference(article: FetchedArticle, source_meta: dict[str, object]) -> tuple[str, str]:
    title_text = (article.title or "").lower()
    text = _article_classifier_text(article)
    tokens = _article_classifier_tokens(text)
    token_count = max(len(tokens), 1)
    category = str(source_meta.get("category") or article.source_category or "general").lower()
    if category in {"sport", "entertainment", "lifestyle", "culture", "tv"}:
        article.domestic_hard_news_positive_signals = []
        article.domestic_hard_news_negative_signals = [f"source_category:{category}"]
        article.classifier_decision_reason = f"off_target: source category '{category}' is outside national hard-news priority"
        return "off_target", article.classifier_decision_reason

    institution_matches = _matched_terms(text, ROMANIAN_INSTITUTION_TERMS)
    actor_matches = _matched_terms(text, ROMANIAN_POLITICAL_ACTOR_TERMS)
    public_impact_matches = _matched_terms(text, ROMANIAN_PUBLIC_IMPACT_TERMS)
    public_economy_matches = _matched_terms(text, ROMANIAN_PUBLIC_ECONOMY_TERMS)
    domestic_legacy_matches = [(term, 1) for term in ROMANIAN_DOMESTIC_HARD_NEWS_TERMS if _text_contains_term(text, term)]
    external_matches = [term for term in ROMANIAN_EXTERNAL_DIRECT_IMPACT_TERMS if _text_contains_term(text, term)]
    off_target_matches = [term for term in ROMANIAN_OFF_TARGET_TERMS if _text_contains_term(text, term)]
    lifestyle_negative_matches = _matched_terms(text, ROMANIAN_LIFESTYLE_NEGATIVE_TERMS)
    finance_negative_matches = _matched_terms(text, ROMANIAN_PERSONAL_FINANCE_NEGATIVE_TERMS)
    feature_negative_matches = _matched_terms(text, ROMANIAN_SOFT_FEATURE_NEGATIVE_TERMS)
    corporate_negative_matches = _matched_terms(text, ROMANIAN_GENERIC_CORPORATE_NEGATIVE_TERMS)
    governance_location_hit, governance_location_signals = _has_governance_location_signal(text)
    title_institution_matches = _matched_terms(title_text, ROMANIAN_INSTITUTION_TERMS)
    title_actor_matches = _matched_terms(title_text, ROMANIAN_POLITICAL_ACTOR_TERMS)
    title_public_impact_matches = _matched_terms(title_text, ROMANIAN_PUBLIC_IMPACT_TERMS)
    title_public_economy_matches = _matched_terms(title_text, ROMANIAN_PUBLIC_ECONOMY_TERMS)
    title_external_matches = [term for term in ROMANIAN_EXTERNAL_DIRECT_IMPACT_TERMS if _text_contains_term(title_text, term)]
    title_governance_location_hit, _ = _has_governance_location_signal(title_text)

    positive_signals = [
        *_signal_labels("institution", institution_matches),
        *_signal_labels("actor", actor_matches),
        *_signal_labels("public_impact", public_impact_matches),
        *_signal_labels("public_economy", public_economy_matches),
        *governance_location_signals,
    ]
    negative_signals = [
        *_signal_labels("lifestyle", lifestyle_negative_matches),
        *_signal_labels("personal_finance", finance_negative_matches),
        *_signal_labels("soft_feature", feature_negative_matches),
        *_signal_labels("generic_corporate", corporate_negative_matches),
        *[f"off_target:{term}" for term in sorted(off_target_matches)],
    ]

    positive_score = sum(weight for _, weight in institution_matches)
    positive_score += sum(weight for _, weight in actor_matches)
    positive_score += sum(weight for _, weight in public_impact_matches)
    positive_score += sum(weight for _, weight in public_economy_matches)
    if governance_location_hit:
        positive_score += 3

    romania_reference_count = sum(1 for term in ROMANIAN_ADMINISTRATIVE_AREAS if _text_contains_term(text, term))
    specific_institution_anchor_count = sum(
        1
        for term, _ in institution_matches
        if term in {"anaf", "bnr", "bvb", "bursa de valori bucuresti", "ccr", "curtea constitutionala", "dna", "diicot", "iccj", "inalta curte", "camera deputatilor", "administratia prezidentiala", "consiliul judetean", "primarie", "prefect"}
    )
    specific_actor_anchor_count = sum(
        1
        for term, _ in actor_matches
        if term in {"psd", "pnl", "usr", "udmr", "aur", "coalitia de guvernare", "premier", "prim-ministru"}
    )
    domestic_anchor_count = specific_institution_anchor_count + specific_actor_anchor_count + (1 if governance_location_hit else 0)
    if romania_reference_count and (institution_matches or actor_matches or public_impact_matches or public_economy_matches):
        domestic_anchor_count += 1
        positive_signals.append(f"romania_reference_count:{romania_reference_count}")
    if domestic_legacy_matches and romania_reference_count:
        positive_score += min(2, len(domestic_legacy_matches))

    negative_score = sum(weight for _, weight in lifestyle_negative_matches)
    negative_score += sum(weight for _, weight in finance_negative_matches)
    negative_score += sum(weight for _, weight in feature_negative_matches)
    negative_score += sum(weight for _, weight in corporate_negative_matches)
    negative_score += len(off_target_matches)

    institution_density = round(((len(institution_matches) + len(actor_matches) + (1 if governance_location_hit else 0)) / token_count) * 100, 2)
    public_interest_density = round(((len(public_impact_matches) + len(public_economy_matches) + len(institution_matches) + len(actor_matches) + (1 if governance_location_hit else 0)) / token_count) * 100, 2)
    strong_domestic_core = bool(institution_matches or actor_matches or governance_location_hit)
    strong_public_interest = bool(public_impact_matches or public_economy_matches)
    has_romanian_anchor = domestic_anchor_count > 0
    headline_public_interest = bool(title_public_impact_matches or title_public_economy_matches)
    headline_domestic_anchor = bool(title_institution_matches or title_actor_matches or title_governance_location_hit)
    headline_supports_domestic = headline_domestic_anchor or (headline_public_interest and romania_reference_count > 0)
    strong_negative_profile = negative_score >= 6 and positive_score < 8
    corporate_without_romania_impact = bool(corporate_negative_matches) and not has_romanian_anchor and not strong_public_interest

    article.domestic_hard_news_positive_signals = positive_signals
    article.domestic_hard_news_negative_signals = negative_signals

    if strong_negative_profile or corporate_without_romania_impact:
        reason = (
            f"off_target: negative profile outweighed Romanian public-interest signals "
            f"(positive_score={positive_score}, negative_score={negative_score}, "
            f"institution_density={institution_density}, public_interest_density={public_interest_density})"
        )
        article.classifier_decision_reason = reason
        return "off_target", reason

    if (
        positive_score >= 6
        and has_romanian_anchor
        and strong_domestic_core
        and strong_public_interest
        and headline_supports_domestic
        and (institution_density >= 0.6 or public_interest_density >= 0.8)
        and negative_score <= max(4, positive_score - 1)
    ):
        reason = (
            f"domestic_hard_news: Romanian public-interest density cleared threshold "
            f"(positive_score={positive_score}, negative_score={negative_score}, "
            f"institution_density={institution_density}, public_interest_density={public_interest_density})"
        )
        article.classifier_decision_reason = reason
        return "domestic_hard_news", reason

    if external_matches and title_external_matches:
        reason = (
            f"external_direct_impact: headline carried external-impact terms without enough Romanian public-interest density "
            f"(external_hits={', '.join(external_matches[:4])}, title_external_hits={', '.join(title_external_matches[:4])}, "
            f"positive_score={positive_score}, institution_density={institution_density}, "
            f"public_interest_density={public_interest_density}, headline_supports_domestic={headline_supports_domestic})"
        )
        article.classifier_decision_reason = reason
        return "external_direct_impact", reason

    reason = (
        f"off_target: insufficient Romanian public-interest density "
        f"(positive_score={positive_score}, negative_score={negative_score}, "
        f"institution_density={institution_density}, public_interest_density={public_interest_density}, "
        f"headline_supports_domestic={headline_supports_domestic})"
    )
    article.classifier_decision_reason = reason
    return "off_target", reason


def _effective_priority_for_romanian_candidate(base_priority: int, bucket: str) -> int:
    if bucket == "domestic_hard_news":
        return max(1, base_priority - 1)
    if bucket == "off_target":
        return min(5, base_priority + 1)
    return base_priority


def _candidate_choice_key(article: FetchedArticle) -> tuple[int, int, int, float]:
    bucket_rank = NATIONAL_PREFERENCE_BUCKET_ORDER.get(article.national_preference_bucket or "off_target", 2)
    fetch_rank = 0 if article.ingestion_kind == "full_fetch" else 1
    effective_priority = article.editorial_priority
    published_at = article.published_at.timestamp() if article.published_at else 0.0
    return (bucket_rank, fetch_rank, effective_priority, -published_at)


def _build_source_candidate_from_rss(rss_article, mapped_meta: dict[str, object]) -> FetchedArticle:
    return FetchedArticle(
        url=rss_article.url,
        title=rss_article.title,
        published_at=rss_article.published_at,
        source=rss_article.source,
        content_text=rss_article.summary,
        ingestion_kind="rss_fallback",
        editorial_priority=mapped_meta.get("editorial_priority", 3),
        source_scope=mapped_meta.get("scope"),
        source_category=mapped_meta.get("category"),
        is_local_source=mapped_meta.get("scope") == "local",
    )


def _apply_romanian_national_preference(article: FetchedArticle, mapped_meta: dict[str, object]) -> FetchedArticle:
    bucket, reason = _classify_romanian_national_preference(article, mapped_meta)
    return article.model_copy(update={
        "national_preference_bucket": bucket,
        "national_preference_reason": reason,
        "domestic_hard_news_positive_signals": article.domestic_hard_news_positive_signals,
        "domestic_hard_news_negative_signals": article.domestic_hard_news_negative_signals,
        "classifier_decision_reason": article.classifier_decision_reason,
        "editorial_priority": _effective_priority_for_romanian_candidate(article.editorial_priority, bucket),
    })


def _normalize_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _build_general_personalization() -> UserPersonalization:
    return UserPersonalization(
        listener_profile=ListenerProfile(
            first_name=None,
            country=None,
            region=None,
            city=None,
        ),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=0, national=50, international=50),
            domains=DomainPreferenceMix(
                politics=28,
                economy=20,
                sport=4,
                entertainment=4,
                education=14,
                health=14,
                tech=16,
            ),
        ),
    )


def _build_articles(personalization: UserPersonalization) -> tuple[list[FetchedArticle], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    watcher_service = SourceWatcherService()
    fetch_service = ArticleFetchService()
    article_service = ArticleService()

    base_source_configs, _ = watcher_service.resolve_monitored_source_configs(personalization)
    source_by_domain: dict[str, dict[str, object]] = {}
    latest_items: list[tuple[object, object]] = []
    source_coverage: dict[str, dict[str, object]] = {}

    for source_config in base_source_configs:
        source_by_domain[_normalize_domain(source_config.source_url)] = {
            "source_id": source_config.source_id,
            "source_name": source_config.source_name,
            "source_type": source_config.source_type,
            "scope": source_config.scope,
            "category": source_config.category,
            "editorial_priority": source_config.editorial_priority,
            "region": source_config.region,
            "country": source_config.country,
        }
        source_coverage[source_config.source_id] = {
            "source_id": source_config.source_id,
            "source_name": source_config.source_name,
            "source_scope": source_config.scope,
            "source_category": source_config.category,
            "editorial_priority": source_config.editorial_priority,
            "articles_discovered": 0,
            "articles_fetched_successfully": 0,
            "candidate_articles_produced": 0,
            "clusters_contributed_to": 0,
            "multi_source_clusters_contributed_to": 0,
            "selected_national_preference_bucket": None,
            "selected_national_preference_reason": None,
        }
        try:
            latest = watcher_service.get_latest_content(source_config)
            latest_items.append((source_config, latest))
            source_coverage[source_config.source_id]["articles_discovered"] += 1
        except Exception:
            continue

    latest_items.sort(key=lambda item: item[1].published_at, reverse=True)

    provenance_by_url: dict[str, dict[str, object]] = {}
    seen_urls: set[str] = set()
    candidates_by_source: dict[str, list[FetchedArticle]] = {config.source_id: [] for config in base_source_configs}

    source_attempts = 0
    for source_config, latest in latest_items:
        if source_attempts >= MAX_SOURCE_FETCH_ATTEMPTS:
            break
        source_attempts += 1
        if latest.url in seen_urls:
            continue
        seen_urls.add(latest.url)
        fetch_result = fetch_service.fetch_article(latest)
        if fetch_result.status != "success" or fetch_result.article is None:
            continue
        article = fetch_result.article.model_copy(
            update={
                "ingestion_kind": "full_fetch",
                "editorial_priority": source_config.editorial_priority,
                "source_scope": source_config.scope,
                "source_category": source_config.category,
                "is_local_source": source_config.scope == "local",
            }
        )
        source_coverage[source_config.source_id]["articles_fetched_successfully"] += 1
        source_coverage[source_config.source_id]["candidate_articles_produced"] += 1
        mapped_meta = source_by_domain.get(_normalize_domain(source_config.source_url), {})
        if source_config.scope == "national" and source_config.country == "Romania":
            article = _apply_romanian_national_preference(article, mapped_meta)
        candidates_by_source[source_config.source_id].append(article)

    rss_articles_added = 0
    for rss_article in article_service.get_articles():
        if rss_articles_added >= MAX_RSS_FALLBACK_ARTICLES:
            break
        if rss_article.url in seen_urls or not rss_article.summary.strip():
            continue
        mapped_meta = source_by_domain.get(_normalize_domain(rss_article.url))
        if not mapped_meta:
            continue
        source_id = mapped_meta.get("source_id")
        if source_id not in candidates_by_source:
            continue
        article = _build_source_candidate_from_rss(rss_article, mapped_meta)
        if mapped_meta.get("scope") == "national" and mapped_meta.get("country") == "Romania":
            article = _apply_romanian_national_preference(article, mapped_meta)
        candidates_by_source[source_id].append(article)
        source_coverage[source_id]["candidate_articles_produced"] += 1
        rss_articles_added += 1

    chosen_articles: list[FetchedArticle] = []
    prioritized_national: list[FetchedArticle] = []
    other_articles: list[FetchedArticle] = []

    config_by_id = {config.source_id: config for config in base_source_configs}
    for source_id, source_candidates in candidates_by_source.items():
        if not source_candidates:
            continue
        source_config = config_by_id[source_id]
        if source_config.scope == "national" and source_config.country == "Romania":
            chosen = sorted(source_candidates, key=_candidate_choice_key)[0]
            source_coverage[source_id]["selected_national_preference_bucket"] = chosen.national_preference_bucket
            source_coverage[source_id]["selected_national_preference_reason"] = chosen.national_preference_reason
            prioritized_national.append(chosen)
        else:
            full_fetch_candidates = [candidate for candidate in source_candidates if candidate.ingestion_kind == "full_fetch"]
            chosen = full_fetch_candidates[0] if full_fetch_candidates else sorted(
                source_candidates,
                key=lambda candidate: -(candidate.published_at.timestamp() if candidate.published_at else 0.0),
            )[0]
            other_articles.append(chosen)

    prioritized_national.sort(key=lambda article: (
        NATIONAL_PREFERENCE_BUCKET_ORDER.get(article.national_preference_bucket or "off_target", 2),
        -(article.published_at.timestamp() if article.published_at else 0.0),
    ))
    other_articles.sort(key=lambda article: -(article.published_at.timestamp() if article.published_at else 0.0))

    for article in [*prioritized_national, *other_articles]:
        if len(chosen_articles) >= MAX_INPUT_ARTICLES:
            break
        chosen_articles.append(article)
        provenance_by_url[article.url] = {
            "ingestion_kind": article.ingestion_kind,
            "scope": article.source_scope,
            "category": article.source_category,
            "editorial_priority": article.editorial_priority,
            "is_local_source": article.is_local_source,
            "national_preference_bucket": article.national_preference_bucket,
            "national_preference_reason": article.national_preference_reason,
        }

    return chosen_articles, provenance_by_url, source_coverage


def _dominant_scope(scored_cluster) -> str:
    scopes = [member.source_scope or ("local" if member.is_local_source else "unknown") for member in scored_cluster.cluster.member_articles]
    return Counter(scopes).most_common(1)[0][0] if scopes else "unknown"


def _dominant_category(scored_cluster) -> str:
    categories = [member.source_category or "general" for member in scored_cluster.cluster.member_articles]
    return Counter(categories).most_common(1)[0][0] if categories else "general"


def _normalize_headline(title: str) -> str:
    cleaned = NOISY_PREFIX_PATTERN.sub("", title or "")
    cleaned = SEPARATOR_PATTERN.split(cleaned, maxsplit=1)[0]
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:;,")
    tokens = TOKEN_PATTERN.findall(cleaned)
    if len(tokens) > 12:
        cleaned = " ".join(tokens[:12])
    return cleaned


def _serialize_candidate(scored_cluster, selection_status: str = "selected") -> dict[str, object]:
    breakdown = scored_cluster.score_breakdown
    source_list = sorted({member.source for member in scored_cluster.cluster.member_articles})
    priorities = sorted({member.editorial_priority for member in scored_cluster.cluster.member_articles})
    return {
        "selection_status": selection_status,
        "cluster_id": scored_cluster.cluster.cluster_id,
        "top_headline": scored_cluster.cluster.representative_title,
        "normalized_headline": _normalize_headline(scored_cluster.cluster.representative_title),
        "cluster_size": len(scored_cluster.cluster.member_articles),
        "unique_source_count": len(source_list),
        "source_list": source_list,
        "source_scope": _dominant_scope(scored_cluster),
        "source_category": _dominant_category(scored_cluster),
        "editorial_priority_summary": {
            "best": min(priorities) if priorities else 5,
            "all": priorities,
        },
        "freshness_score": breakdown.recency.contribution,
        "europe_romania_impact_score": breakdown.europe_romania_impact.contribution,
        "europe_romania_impact_explanation": breakdown.europe_romania_impact.explanation,
        "editorial_fit_score": breakdown.editorial_fit.contribution,
        "final_score": scored_cluster.score_total,
    }


def _cluster_signals(scored_cluster, article_by_url: dict[str, FetchedArticle], clustering_service) -> dict[str, object]:
    representative_article = _representative_article(scored_cluster, article_by_url)
    if representative_article is None:
        return {
            "event_families": [],
            "regional_buckets": [],
            "normalized_headline": _normalize_headline(scored_cluster.cluster.representative_title),
            "normalized_source": None,
        }
    normalized_article = clustering_service._normalize_article(representative_article)
    signals = clustering_service._build_signals(normalized_article)
    return {
        "event_families": sorted(signals.event_families),
        "regional_buckets": sorted(signals.regional_buckets),
        "normalized_headline": signals.normalized_title or _normalize_headline(scored_cluster.cluster.representative_title),
        "normalized_source": signals.normalized_source,
    }


def _write_scope_outputs(label: str, selected_clusters: list, candidate_clusters: list, json_path: Path, txt_path: Path) -> dict[str, object]:
    selected_payload = [_serialize_candidate(cluster, selection_status="selected") for cluster in selected_clusters[:5]]
    if len(selected_payload) < 5:
        selected_ids = {item["cluster_id"] for item in selected_payload}
        fallback_clusters = [cluster for cluster in candidate_clusters if cluster.cluster.cluster_id not in selected_ids]
        for cluster in fallback_clusters[: 5 - len(selected_payload)]:
            selected_payload.append(_serialize_candidate(cluster, selection_status="debug_rank_fallback"))
    candidate_payload = [_serialize_candidate(cluster, selection_status="candidate") for cluster in candidate_clusters]
    payload = {
        "scope": label,
        "candidate_cluster_count": len(candidate_clusters),
        "selected_count": len(selected_clusters[:5]),
        "debug_fallback_count": sum(1 for item in selected_payload if item["selection_status"] == "debug_rank_fallback"),
        "selected_with_unique_source_count_gte_2": sum(1 for item in selected_payload if item["unique_source_count"] >= 2),
        "selected_with_unique_source_count_gte_3": sum(1 for item in selected_payload if item["unique_source_count"] >= 3),
        "top5": selected_payload,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [f"TOP 5 {label.upper()} SELECTION", "", f"Candidate clusters: {len(candidate_clusters)}", ""]
    for index, item in enumerate(selected_payload, start=1):
        lines.extend([
            f"{index}. {item['normalized_headline'] or item['top_headline']}",
            f"   selection_status: {item['selection_status']}",
            f"   cluster_id: {item['cluster_id']}",
            f"   top_headline: {item['top_headline']}",
            f"   normalized_headline: {item['normalized_headline']}",
            f"   unique_source_count: {item['unique_source_count']}",
            f"   source_list: {', '.join(item['source_list'])}",
            f"   source_scope: {item['source_scope']}",
            f"   source_category: {item['source_category']}",
            f"   editorial_priority: best={item['editorial_priority_summary']['best']} all={item['editorial_priority_summary']['all']}",
            f"   freshness_score: {item['freshness_score']}",
            f"   europe_romania_impact_score: {item['europe_romania_impact_score']}",
            f"   editorial_fit_score: {item['editorial_fit_score']}",
            f"   final_score: {item['final_score']}",
            "",
        ])
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return payload


def _representative_article(cluster, article_by_url: dict[str, FetchedArticle]) -> FetchedArticle | None:
    for member in cluster.cluster.member_articles:
        article = article_by_url.get(member.url)
        if article is not None:
            return article
    return None


def _write_international_merge_debug(global_candidates: list, article_by_url: dict[str, FetchedArticle], clustering_service) -> None:
    top_candidates = global_candidates[:10]
    representative_articles = []
    for candidate in top_candidates:
        article = _representative_article(candidate, article_by_url)
        if article is not None:
            representative_articles.append((candidate, article))

    pair_payload = []
    for (left_cluster, left_article), (right_cluster, right_article) in combinations(representative_articles, 2):
        left_signal = clustering_service._build_signals(clustering_service._normalize_article(left_article))
        right_signal = clustering_service._build_signals(clustering_service._normalize_article(right_article))
        shared_entities = sorted(left_signal.entities & right_signal.entities)
        shared_event_keywords = sorted(left_signal.event_terms & right_signal.event_terms)
        shared_locations = sorted({term for term in shared_event_keywords if term in LOCATION_TERMS})
        likely_pair = bool(
            shared_entities
            or (set(shared_event_keywords) & LIKELY_EVENT_TERMS)
            or left_signal.normalized_source != right_signal.normalized_source and (
                "iran" in (left_signal.event_terms | right_signal.event_terms)
                and ({"golful", "emiratele", "ormuz", "porturi", "mijlociu", "marines", "hamas"} & (left_signal.event_terms | right_signal.event_terms))
            )
        )
        if not likely_pair:
            continue

        decision = clustering_service.explain_pair(left_article, right_article)
        pair_payload.append({
            "candidate_a_cluster_id": left_cluster.cluster.cluster_id,
            "candidate_b_cluster_id": right_cluster.cluster.cluster_id,
            "candidate_a_headline": left_cluster.cluster.representative_title,
            "candidate_b_headline": right_cluster.cluster.representative_title,
            "normalized_headline_a": left_signal.normalized_title,
            "normalized_headline_b": right_signal.normalized_title,
            "normalized_source_a": left_signal.normalized_source,
            "normalized_source_b": right_signal.normalized_source,
            "event_families_a": sorted(left_signal.event_families),
            "event_families_b": sorted(right_signal.event_families),
            "regional_buckets_a": sorted(left_signal.regional_buckets),
            "regional_buckets_b": sorted(right_signal.regional_buckets),
            "shared_entities": shared_entities,
            "shared_locations": shared_locations,
            "shared_event_keywords": shared_event_keywords,
            "hours_apart": round(decision.hours_apart, 2),
            "merge_decision": decision.status == "merged",
            "decision_status": decision.status,
            "decision_reason": decision.reason,
            "title_similarity": decision.title_similarity,
            "keyword_overlap": decision.keyword_overlap,
            "body_overlap": decision.body_overlap,
        })

    payload = {
        "candidate_count_considered": len(representative_articles),
        "pair_count_reported": len(pair_payload),
        "pairs": pair_payload,
    }
    INTERNATIONAL_MERGE_DEBUG_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "INTERNATIONAL MERGE DEBUG",
        "",
        f"candidate_count_considered: {payload['candidate_count_considered']}",
        f"pair_count_reported: {payload['pair_count_reported']}",
        "",
    ]
    for index, item in enumerate(pair_payload, start=1):
        lines.extend([
            f"{index}. {item['candidate_a_headline']}  <->  {item['candidate_b_headline']}",
            f"   normalized_headline_a: {item['normalized_headline_a']}",
            f"   normalized_headline_b: {item['normalized_headline_b']}",
            f"   normalized_source_a: {item['normalized_source_a']}",
            f"   normalized_source_b: {item['normalized_source_b']}",
            f"   event_families_a: {', '.join(item['event_families_a']) or 'none'}",
            f"   event_families_b: {', '.join(item['event_families_b']) or 'none'}",
            f"   regional_buckets_a: {', '.join(item['regional_buckets_a']) or 'none'}",
            f"   regional_buckets_b: {', '.join(item['regional_buckets_b']) or 'none'}",
            f"   shared_entities: {', '.join(item['shared_entities']) or 'none'}",
            f"   shared_locations: {', '.join(item['shared_locations']) or 'none'}",
            f"   shared_event_keywords: {', '.join(item['shared_event_keywords']) or 'none'}",
            f"   hours_apart: {item['hours_apart']}",
            f"   merge_decision: {item['merge_decision']}",
            f"   decision_reason: {item['decision_reason']}",
            f"   title_similarity: {item['title_similarity']}",
            f"   keyword_overlap: {item['keyword_overlap']}",
            f"   body_overlap: {item['body_overlap']}",
            "",
        ])
    INTERNATIONAL_MERGE_DEBUG_TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_story_selection_debug(scored_clusters: list, selected_cluster_ids: set[str]) -> None:
    candidate_payload = []
    for cluster in scored_clusters:
        serialized = _serialize_candidate(
            cluster,
            selection_status="selected" if cluster.cluster.cluster_id in selected_cluster_ids else "candidate",
        )
        candidate_payload.append(serialized)

    payload = {
        "candidate_cluster_count": len(candidate_payload),
        "clusters_with_unique_source_count_gte_2": sum(1 for item in candidate_payload if item["unique_source_count"] >= 2),
        "clusters_with_unique_source_count_gte_3": sum(1 for item in candidate_payload if item["unique_source_count"] >= 3),
        "top_candidate_clusters": candidate_payload[:10],
        "selected_stories": [item for item in candidate_payload if item["selection_status"] == "selected"],
    }
    STORY_SELECTION_DEBUG_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "STORY SELECTION DEBUG",
        "",
        f"candidate_cluster_count: {payload['candidate_cluster_count']}",
        f"clusters_with_unique_source_count_gte_2: {payload['clusters_with_unique_source_count_gte_2']}",
        f"clusters_with_unique_source_count_gte_3: {payload['clusters_with_unique_source_count_gte_3']}",
        "",
    ]
    for index, item in enumerate(payload["top_candidate_clusters"], start=1):
        lines.extend([
            f"{index}. {item['normalized_headline'] or item['top_headline']}",
            f"   selection_status: {item['selection_status']}",
            f"   cluster_id: {item['cluster_id']}",
            f"   unique_source_count: {item['unique_source_count']}",
            f"   source_list: {', '.join(item['source_list'])}",
            f"   source_scope: {item['source_scope']}",
            f"   source_category: {item['source_category']}",
            f"   editorial_priority: {item['editorial_priority_summary']['best']}",
            f"   freshness_score: {item['freshness_score']}",
            f"   europe_romania_impact_score: {item['europe_romania_impact_score']}",
            f"   editorial_fit_score: {item['editorial_fit_score']}",
            f"   final_score: {item['final_score']}",
            "",
        ])
    STORY_SELECTION_DEBUG_TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_international_source_coverage(
    source_coverage: dict[str, dict[str, object]],
    scored_clusters: list,
    clustering_service,
) -> None:
    coverage_by_normalized_source = {
        clustering_service._normalize_source_identity(coverage["source_name"]): coverage
        for coverage in source_coverage.values()
    }

    for cluster in scored_clusters:
        source_ids_in_cluster: set[str] = set()
        for member in cluster.cluster.member_articles:
            normalized_member_source = clustering_service._normalize_source_identity(member.source)
            coverage = coverage_by_normalized_source.get(normalized_member_source)
            if coverage is not None:
                source_ids_in_cluster.add(coverage["source_id"])
        for source_id in source_ids_in_cluster:
            source_coverage[source_id]["clusters_contributed_to"] += 1
            if len({member.source for member in cluster.cluster.member_articles}) >= 2:
                source_coverage[source_id]["multi_source_clusters_contributed_to"] += 1

    international_sources = [
        coverage
        for coverage in source_coverage.values()
        if coverage["source_scope"] == "international"
    ]
    international_sources.sort(
        key=lambda item: (
            -item["candidate_articles_produced"],
            -item["articles_fetched_successfully"],
            -item["clusters_contributed_to"],
            item["source_name"].lower(),
        )
    )

    payload = {
        "international_source_count": len(international_sources),
        "sources": international_sources,
    }
    INTERNATIONAL_SOURCE_COVERAGE_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "INTERNATIONAL SOURCE COVERAGE",
        "",
        f"international_source_count: {payload['international_source_count']}",
        "",
    ]
    for index, item in enumerate(international_sources, start=1):
        lines.extend([
            f"{index}. {item['source_name']}",
            f"   source_category: {item['source_category']}",
            f"   editorial_priority: {item['editorial_priority']}",
            f"   articles_discovered: {item['articles_discovered']}",
            f"   articles_fetched_successfully: {item['articles_fetched_successfully']}",
            f"   candidate_articles_produced: {item['candidate_articles_produced']}",
            f"   clusters_contributed_to: {item['clusters_contributed_to']}",
            f"   multi_source_clusters_contributed_to: {item['multi_source_clusters_contributed_to']}",
            "",
        ])
    INTERNATIONAL_SOURCE_COVERAGE_TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_candidate_pool_audit(scored_clusters: list, article_by_url: dict[str, FetchedArticle], clustering_service) -> None:
    top_candidates = scored_clusters[:10]
    top_payload = []
    event_family_distribution: Counter[str] = Counter()
    regional_bucket_distribution: Counter[str] = Counter()
    scope_distribution: Counter[str] = Counter()

    for cluster in scored_clusters:
        serialized = _serialize_candidate(cluster, selection_status="candidate")
        signals = _cluster_signals(cluster, article_by_url, clustering_service)
        scope_distribution[serialized["source_scope"]] += 1

        families = signals["event_families"] or ["none"]
        for family in families:
            event_family_distribution[family] += 1

        buckets = signals["regional_buckets"] or ["none"]
        for bucket in buckets:
            regional_bucket_distribution[bucket] += 1

        if len(top_payload) < 10:
            top_payload.append({
                **serialized,
                "normalized_headline": signals["normalized_headline"],
                "normalized_source": signals["normalized_source"],
                "event_family": signals["event_families"],
                "regional_bucket": signals["regional_buckets"],
            })

    payload = {
        "candidate_pool_size": {
            "total_clusters": len(scored_clusters),
            "international_clusters": scope_distribution.get("international", 0),
            "national_clusters": scope_distribution.get("national", 0),
        },
        "multi_source_cluster_stats": {
            "clusters_unique_sources_gte_2": sum(
                1 for cluster in scored_clusters if len({member.source for member in cluster.cluster.member_articles}) >= 2
            ),
            "clusters_unique_sources_gte_3": sum(
                1 for cluster in scored_clusters if len({member.source for member in cluster.cluster.member_articles}) >= 3
            ),
            "clusters_unique_sources_gte_4": sum(
                1 for cluster in scored_clusters if len({member.source for member in cluster.cluster.member_articles}) >= 4
            ),
        },
        "event_family_distribution": dict(sorted(event_family_distribution.items())),
        "regional_bucket_distribution": dict(sorted(regional_bucket_distribution.items())),
        "top_candidate_clusters": top_payload,
    }
    CANDIDATE_POOL_AUDIT_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "CANDIDATE POOL AUDIT",
        "",
        f"total_clusters: {payload['candidate_pool_size']['total_clusters']}",
        f"international_clusters: {payload['candidate_pool_size']['international_clusters']}",
        f"national_clusters: {payload['candidate_pool_size']['national_clusters']}",
        "",
        "MULTI-SOURCE CLUSTER STATS",
        f"clusters_unique_sources_gte_2: {payload['multi_source_cluster_stats']['clusters_unique_sources_gte_2']}",
        f"clusters_unique_sources_gte_3: {payload['multi_source_cluster_stats']['clusters_unique_sources_gte_3']}",
        f"clusters_unique_sources_gte_4: {payload['multi_source_cluster_stats']['clusters_unique_sources_gte_4']}",
        "",
        "EVENT FAMILY DISTRIBUTION",
    ]
    for family, count in payload["event_family_distribution"].items():
        lines.append(f"{family}: {count}")
    lines.extend(["", "REGIONAL BUCKET DISTRIBUTION"])
    for bucket, count in payload["regional_bucket_distribution"].items():
        lines.append(f"{bucket}: {count}")
    lines.extend(["", "TOP 10 CANDIDATE CLUSTERS", ""])

    for index, item in enumerate(top_payload, start=1):
        lines.extend([
            f"{index}. {item['normalized_headline'] or item['top_headline']}",
            f"   cluster_id: {item['cluster_id']}",
            f"   top_headline: {item['top_headline']}",
            f"   normalized_headline: {item['normalized_headline']}",
            f"   normalized_source: {item['normalized_source'] or 'unknown'}",
            f"   source_list: {', '.join(item['source_list'])}",
            f"   unique_source_count: {item['unique_source_count']}",
            f"   event_family: {', '.join(item['event_family']) or 'none'}",
            f"   regional_bucket: {', '.join(item['regional_bucket']) or 'none'}",
            f"   category: {item['source_category']}",
            f"   freshness_score: {item['freshness_score']}",
            f"   editorial_fit_score: {item['editorial_fit_score']}",
            f"   final_score: {item['final_score']}",
            "",
        ])
    CANDIDATE_POOL_AUDIT_TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    personalization = _build_general_personalization()
    pipeline_service = EditorialPipelineService()

    articles, _, source_coverage = _build_articles(personalization)
    article_by_url = {article.url: article for article in articles}
    story_clusters = pipeline_service.clustering_service.cluster_articles(articles)
    scored_clusters = pipeline_service.scoring_service.score_clusters(story_clusters)

    national_candidates = [cluster for cluster in scored_clusters if _dominant_scope(cluster) == "national"]
    global_candidates = [cluster for cluster in scored_clusters if _dominant_scope(cluster) == "international"]

    national_selection = pipeline_service.selection_service.select_stories(
        national_candidates,
        max_stories=5,
        editorial_preferences=personalization.editorial_preferences,
        personalization=personalization,
    )
    global_selection = pipeline_service.selection_service.select_stories(
        global_candidates,
        max_stories=5,
        editorial_preferences=personalization.editorial_preferences,
        personalization=personalization,
    )

    national_payload = _write_scope_outputs(
        "national",
        national_selection.selected_clusters,
        national_candidates,
        NATIONAL_JSON_OUTPUT_PATH,
        NATIONAL_TEXT_OUTPUT_PATH,
    )
    global_payload = _write_scope_outputs(
        "global",
        global_selection.selected_clusters,
        global_candidates,
        GLOBAL_JSON_OUTPUT_PATH,
        GLOBAL_TEXT_OUTPUT_PATH,
    )

    selected_cluster_ids = {cluster.cluster.cluster_id for cluster in national_selection.selected_clusters + global_selection.selected_clusters}
    _write_story_selection_debug(scored_clusters, selected_cluster_ids)
    _write_international_merge_debug(global_candidates, article_by_url, pipeline_service.clustering_service)
    _write_candidate_pool_audit(scored_clusters, article_by_url, pipeline_service.clustering_service)
    _write_international_source_coverage(source_coverage, scored_clusters, pipeline_service.clustering_service)

    print(f"Wrote {NATIONAL_JSON_OUTPUT_PATH}")
    print(f"Wrote {NATIONAL_TEXT_OUTPUT_PATH}")
    print(f"Wrote {GLOBAL_JSON_OUTPUT_PATH}")
    print(f"Wrote {GLOBAL_TEXT_OUTPUT_PATH}")
    print(f"Wrote {STORY_SELECTION_DEBUG_JSON_PATH}")
    print(f"Wrote {STORY_SELECTION_DEBUG_TEXT_PATH}")
    print(f"Wrote {INTERNATIONAL_MERGE_DEBUG_JSON_PATH}")
    print(f"Wrote {INTERNATIONAL_MERGE_DEBUG_TEXT_PATH}")
    print(f"Wrote {CANDIDATE_POOL_AUDIT_JSON_PATH}")
    print(f"Wrote {CANDIDATE_POOL_AUDIT_TEXT_PATH}")
    print(f"Wrote {INTERNATIONAL_SOURCE_COVERAGE_JSON_PATH}")
    print(f"Wrote {INTERNATIONAL_SOURCE_COVERAGE_TEXT_PATH}")
    print(json.dumps({
        "national_candidate_clusters": national_payload["candidate_cluster_count"],
        "global_candidate_clusters": global_payload["candidate_cluster_count"],
        "national_selected": national_payload["selected_count"],
        "global_selected": global_payload["selected_count"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
