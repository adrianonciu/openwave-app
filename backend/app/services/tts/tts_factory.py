from __future__ import annotations

from app.config.presenter import PresenterConfig
from app.services.tts.base_tts_provider import BaseTtsProvider
from app.services.tts.edge_tts_provider import EdgeTtsProvider
from app.services.tts.elevenlabs_tts_provider import ElevenLabsTtsProvider
from app.services.tts.openai_tts_provider import OpenAITtsProvider


def create_tts_provider(presenter: PresenterConfig) -> BaseTtsProvider:
    preferred_name = presenter.preferred_tts_provider.strip().lower() or 'elevenlabs'
    fallback_name = presenter.fallback_tts_provider.strip().lower() or 'openai'

    providers = {
        'edge': EdgeTtsProvider(presenter),
        'elevenlabs': ElevenLabsTtsProvider(presenter),
        'openai': OpenAITtsProvider(presenter),
    }

    preferred_provider = providers.get(preferred_name)
    fallback_provider = providers.get(fallback_name)

    if preferred_provider is not None and preferred_provider.is_configured():
        return preferred_provider

    if fallback_provider is not None and fallback_provider.is_configured():
        return fallback_provider

    if preferred_provider is None:
        raise RuntimeError(f'Unsupported TTS provider: {presenter.preferred_tts_provider}')

    raise RuntimeError(
        'No TTS provider is configured. Set TTS_PROVIDER=edge for development testing or configure ElevenLabs/OpenAI credentials.'
    )
