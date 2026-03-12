from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from app.config.presenter import PresenterConfig
from app.services.tts.base_tts_provider import BaseTtsProvider


class OpenAITtsProvider(BaseTtsProvider):
    provider_name = 'openai'

    def __init__(self, presenter: PresenterConfig) -> None:
        self._settings = presenter.openai

    @property
    def voice_id(self) -> str:
        return self._settings.voice_id

    @property
    def model(self) -> str:
        return self._settings.model

    @property
    def output_format(self) -> str:
        return self._settings.output_format

    def is_configured(self) -> bool:
        return bool(self._settings.api_key.strip() and self._settings.voice_id.strip())

    def synthesize(self, text: str, output_path: Path) -> None:
        if not self.is_configured():
            raise RuntimeError(
                'OpenAI TTS is not configured. Set OPENAI_API_KEY and OPENAI_TTS_VOICE.'
            )

        payload = json.dumps(
            {
                'model': self.model,
                'voice': self.voice_id,
                'input': text,
                'response_format': self.output_format,
                'speed': self._settings.tuning.speed,
            }
        ).encode('utf-8')
        request = urllib.request.Request(
            url='https://api.openai.com/v1/audio/speech',
            data=payload,
            headers={
                'Authorization': f'Bearer {self._settings.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                output_path.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            details = exc.read().decode('utf-8', errors='ignore')
            raise RuntimeError(
                f'OpenAI TTS request failed: {exc.code} {details}'.strip()
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f'OpenAI TTS request failed: {exc.reason}') from exc
