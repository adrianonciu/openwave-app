from __future__ import annotations

import asyncio
import os
from pathlib import Path

try:
    import edge_tts
except ImportError:  # pragma: no cover - handled via is_configured
    edge_tts = None

from app.config.presenter import PresenterConfig
from app.services.tts.base_tts_provider import BaseTtsProvider
from app.services.tts.tts_provider_error import TtsProviderError


class EdgeTtsProvider(BaseTtsProvider):
    provider_name = 'edge'

    def __init__(self, presenter: PresenterConfig) -> None:
        self._presenter = presenter

    @property
    def presenter_name(self) -> str:
        return self._presenter.presenter_name

    @property
    def voice_id(self) -> str:
        return os.getenv('EDGE_TTS_VOICE', os.getenv('TTS_VOICE_ID', 'ro-RO-EmilNeural')).strip() or 'ro-RO-EmilNeural'

    @property
    def model(self) -> str:
        return 'edge-tts'

    @property
    def output_format(self) -> str:
        return 'mp3'

    def is_configured(self) -> bool:
        return edge_tts is not None and bool(self.voice_id)

    def synthesize(self, text: str, output_path: Path) -> None:
        if edge_tts is None:
            raise TtsProviderError(
                provider=self.provider_name,
                code='provider_not_configured',
                message='Edge TTS is not installed. Add edge-tts to the backend environment.',
            )

        if not self.voice_id:
            raise TtsProviderError(
                provider=self.provider_name,
                code='provider_not_configured',
                message='Edge TTS voice is not configured. Set EDGE_TTS_VOICE or TTS_VOICE_ID.',
            )

        communicate = edge_tts.Communicate(text=text, voice=self.voice_id)
        asyncio.run(communicate.save(str(output_path)))
