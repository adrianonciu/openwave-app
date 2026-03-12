from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TtsProviderSettings:
    api_key: str
    voice_id: str
    model: str
    output_format: str


@dataclass(frozen=True)
class PresenterConfig:
    presenter_name: str
    preferred_tts_provider: str
    fallback_tts_provider: str
    elevenlabs: TtsProviderSettings
    openai: TtsProviderSettings


_GENERIC_PROVIDER = os.getenv("TTS_PROVIDER", os.getenv("OPENWAVE_TTS_PROVIDER", "elevenlabs"))
_GENERIC_VOICE = os.getenv("TTS_VOICE_ID", "")
_GENERIC_MODEL = os.getenv("TTS_MODEL", "")
_GENERIC_OUTPUT_FORMAT = os.getenv("TTS_OUTPUT_FORMAT", "")

_DEFAULT_PRESENTER = PresenterConfig(
    presenter_name="Corina",
    preferred_tts_provider=_GENERIC_PROVIDER,
    fallback_tts_provider=os.getenv("TTS_FALLBACK_PROVIDER", "openai"),
    elevenlabs=TtsProviderSettings(
        api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        voice_id=os.getenv("ELEVENLABS_VOICE_ID", _GENERIC_VOICE),
        model=os.getenv("ELEVENLABS_MODEL_ID", _GENERIC_MODEL or "eleven_multilingual_v2"),
        output_format=os.getenv(
            "ELEVENLABS_OUTPUT_FORMAT",
            _GENERIC_OUTPUT_FORMAT or "mp3_44100_128",
        ),
    ),
    openai=TtsProviderSettings(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        voice_id=os.getenv("OPENAI_TTS_VOICE", _GENERIC_VOICE or "shimmer"),
        model=os.getenv("OPENAI_TTS_MODEL", _GENERIC_MODEL or "gpt-4o-mini-tts"),
        output_format=os.getenv("OPENAI_TTS_OUTPUT_FORMAT", _GENERIC_OUTPUT_FORMAT or "mp3"),
    ),
)

_PRESENTERS = {
    _DEFAULT_PRESENTER.presenter_name.casefold(): _DEFAULT_PRESENTER,
}


def get_presenter_config(presenter_name: str | None = None) -> PresenterConfig:
    if not presenter_name:
        return _DEFAULT_PRESENTER

    normalized_name = presenter_name.strip().casefold()
    return _PRESENTERS.get(normalized_name, _DEFAULT_PRESENTER)
