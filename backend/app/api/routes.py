from fastapi import APIRouter, HTTPException

from app.models.article import Article
from app.models.briefing import DailyBriefing
from app.models.end_to_end_bulletin_result import (
    EndToEndBulletinGenerationRequest,
    EndToEndBulletinResult,
)
from app.models.source_watcher import SourceCheckSummary
from app.models.tts import (
    TtsGenerationRequest,
    TtsGenerationResponse,
    TtsPilotAudioResponse,
    TtsPilotGenerationRequest,
    TtsPilotSummary,
)
from app.services.article_service import ArticleService
from app.services.briefing_service import BriefingService
from app.services.end_to_end_bulletin_service import EndToEndBulletinService
from app.services.source_watcher_service import SourceWatcherService
from app.services.tts.tts_provider_error import TtsProviderError
from app.services.tts_service import TtsService

router = APIRouter()

article_service = ArticleService()
briefing_service = BriefingService(article_service=article_service)
source_watcher_service = SourceWatcherService()
tts_service = TtsService()
end_to_end_bulletin_service = EndToEndBulletinService()


@router.get("/articles", response_model=list[Article])
def get_articles() -> list[Article]:
    return article_service.get_articles()


@router.get("/briefing/today", response_model=DailyBriefing)
def get_today_briefing() -> DailyBriefing:
    return briefing_service.get_today_briefing()


@router.get("/sources/watch/check", response_model=SourceCheckSummary)
def check_all_sources() -> SourceCheckSummary:
    return source_watcher_service.check_all_sources()


@router.get("/api/tts/pilots", response_model=list[TtsPilotSummary])
def get_tts_pilots() -> list[TtsPilotSummary]:
    return [TtsPilotSummary(**pilot) for pilot in tts_service.get_pilot_summaries()]


@router.post("/api/tts/generate", response_model=TtsGenerationResponse)
def generate_tts_audio(payload: TtsGenerationRequest) -> TtsGenerationResponse:
    try:
        result = tts_service.generate_audio(
            briefing_text=payload.briefing_text,
            presenter_name=payload.presenter_name,
            file_stem=payload.file_stem,
        )
    except TtsProviderError as exc:
        raise HTTPException(status_code=400, detail=exc.info.__dict__) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TtsGenerationResponse(**result)


@router.post("/api/tts/generate-from-pilot", response_model=TtsPilotAudioResponse)
def generate_tts_audio_from_pilot(
    payload: TtsPilotGenerationRequest,
) -> TtsPilotAudioResponse:
    try:
        result = tts_service.generate_pilot_audio(
            pilot_id=payload.pilot_id,
            presenter_name=payload.presenter_name,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TtsProviderError as exc:
        raise HTTPException(status_code=400, detail=exc.info.__dict__) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TtsPilotAudioResponse(**result)


@router.post("/api/bulletins/generate-end-to-end", response_model=EndToEndBulletinResult)
def generate_end_to_end_bulletin(
    payload: EndToEndBulletinGenerationRequest,
) -> EndToEndBulletinResult:
    result = end_to_end_bulletin_service.run_end_to_end_bulletin_generation(
        articles=payload.articles,
        bulletin_id=payload.bulletin_id,
        presenter_name=payload.presenter_name,
        personalization=payload.personalization,
        editorial_preferences=payload.editorial_preferences,
    )
    return result
