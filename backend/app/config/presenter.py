from __future__ import annotations

import os
from dataclasses import replace
from dataclasses import dataclass

from app.config.env import load_backend_env


load_backend_env()


@dataclass(frozen=True)
class VoiceTuningSettings:
    stability: float
    similarity_boost: float
    style: float
    use_speaker_boost: bool
    speed: float


@dataclass(frozen=True)
class TtsProviderSettings:
    api_key: str
    voice_id: str
    model: str
    output_format: str
    tuning: VoiceTuningSettings


@dataclass(frozen=True)
class PresenterConfig:
    presenter_name: str
    preferred_tts_provider: str
    fallback_tts_provider: str
    elevenlabs: TtsProviderSettings
    openai: TtsProviderSettings


def _normalize_elevenlabs_output_format(raw_format: str) -> str:
    normalized = raw_format.strip().lower()
    if not normalized or normalized == 'mp3':
        return 'mp3_44100_128'
    if normalized == 'wav':
        return 'wav_44100'
    return normalized


def _read_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    return raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}


_GENERIC_PROVIDER = os.getenv('TTS_PROVIDER', os.getenv('OPENWAVE_TTS_PROVIDER', 'elevenlabs'))
_GENERIC_VOICE = os.getenv('TTS_VOICE_ID', '')
_GENERIC_MODEL = os.getenv('TTS_MODEL', '')
_GENERIC_OUTPUT_FORMAT = os.getenv('TTS_OUTPUT_FORMAT', '')
_GENERIC_SPEED = _read_float('TTS_SPEED', 1.0)
_OPENAI_DEFAULT_VOICE = (os.getenv('OPENAI_TTS_VOICE', _GENERIC_VOICE or 'alloy').strip().lower() or 'alloy')
_OPENAI_ANA_VOICE = (os.getenv('OPENAI_TTS_VOICE_ANA', 'marin').strip().lower() or 'marin')
_OPENAI_PAUL_VOICE = (os.getenv('OPENAI_TTS_VOICE_PAUL', 'cedar').strip().lower() or 'cedar')


def _build_provider_settings() -> tuple[TtsProviderSettings, TtsProviderSettings]:
    elevenlabs = TtsProviderSettings(
        api_key=os.getenv('ELEVENLABS_API_KEY', ''),
        voice_id=os.getenv('ELEVENLABS_VOICE_ID', _GENERIC_VOICE),
        model=os.getenv('ELEVENLABS_MODEL_ID', _GENERIC_MODEL or 'eleven_multilingual_v2'),
        output_format=_normalize_elevenlabs_output_format(
            os.getenv('ELEVENLABS_OUTPUT_FORMAT', _GENERIC_OUTPUT_FORMAT)
        ),
        tuning=VoiceTuningSettings(
            stability=_read_float('ELEVENLABS_STABILITY', 0.35),
            similarity_boost=_read_float('ELEVENLABS_SIMILARITY_BOOST', 0.8),
            style=_read_float('ELEVENLABS_STYLE', 0.45),
            use_speaker_boost=_read_bool('ELEVENLABS_USE_SPEAKER_BOOST', True),
            speed=_read_float('ELEVENLABS_SPEED', _GENERIC_SPEED),
        ),
    )
    openai = TtsProviderSettings(
        api_key=os.getenv('OPENAI_API_KEY', ''),
        voice_id=_OPENAI_DEFAULT_VOICE,
        model=os.getenv('OPENAI_TTS_MODEL', _GENERIC_MODEL or 'gpt-4o-mini-tts'),
        output_format=(os.getenv('OPENAI_TTS_OUTPUT_FORMAT', _GENERIC_OUTPUT_FORMAT or 'mp3').strip().lower() or 'mp3'),
        tuning=VoiceTuningSettings(
            stability=_read_float('OPENAI_TTS_STABILITY', 0.0),
            similarity_boost=_read_float('OPENAI_TTS_SIMILARITY_BOOST', 0.0),
            style=_read_float('OPENAI_TTS_STYLE', 0.0),
            use_speaker_boost=_read_bool('OPENAI_TTS_USE_SPEAKER_BOOST', False),
            speed=_read_float('OPENAI_TTS_SPEED', 1.05),
        ),
    )
    return elevenlabs, openai


def _build_presenter(presenter_name: str, *, openai_voice_id: str | None = None) -> PresenterConfig:
    elevenlabs, openai = _build_provider_settings()
    if openai_voice_id is not None:
        openai = replace(openai, voice_id=openai_voice_id)
    return PresenterConfig(
        presenter_name=presenter_name,
        preferred_tts_provider=_GENERIC_PROVIDER,
        fallback_tts_provider=os.getenv('TTS_FALLBACK_PROVIDER', 'openai'),
        elevenlabs=elevenlabs,
        openai=openai,
    )


_DEFAULT_PRESENTER = _build_presenter('Corina')

_PRESENTERS = {
    _DEFAULT_PRESENTER.presenter_name.casefold(): _DEFAULT_PRESENTER,
    'ana': _build_presenter('Ana', openai_voice_id=_OPENAI_ANA_VOICE),
    'paul': _build_presenter('Paul', openai_voice_id=_OPENAI_PAUL_VOICE),
}


def get_presenter_config(presenter_name: str | None = None) -> PresenterConfig:
    if not presenter_name:
        return _DEFAULT_PRESENTER

    normalized_name = presenter_name.strip().casefold()
    presenter = _PRESENTERS.get(normalized_name)
    if presenter is not None:
        return presenter

    resolved_name = presenter_name.strip()
    if not resolved_name:
        return _DEFAULT_PRESENTER

    return replace(_DEFAULT_PRESENTER, presenter_name=resolved_name)
