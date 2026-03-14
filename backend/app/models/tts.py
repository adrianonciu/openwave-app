from pydantic import BaseModel, Field


class TtsGenerationRequest(BaseModel):
    briefing_text: str = Field(..., min_length=1)
    presenter_name: str = 'Corina'
    file_stem: str | None = None


class TtsPilotGenerationRequest(BaseModel):
    pilot_id: str = Field(..., min_length=1)
    presenter_name: str = 'Corina'


class TtsProviderErrorResponse(BaseModel):
    provider: str
    code: str
    message: str
    status_code: int | None = None


class TtsGenerationResponse(BaseModel):
    audio_url: str
    presenter_name: str
    tts_provider: str
    tts_voice_id: str


class TtsPilotSummary(BaseModel):
    pilot_id: str
    title: str
    presenter_name: str = 'Corina'


class TtsPilotAudioResponse(BaseModel):
    pilot_id: str
    title: str
    presenter_name: str
    tts_provider: str
    tts_voice_id: str
    segments: list[str]
