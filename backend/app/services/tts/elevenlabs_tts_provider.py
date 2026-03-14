from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from app.config.presenter import PresenterConfig
from app.services.tts.base_tts_provider import BaseTtsProvider
from app.services.tts.tts_provider_error import TtsProviderError


class ElevenLabsTtsProvider(BaseTtsProvider):
    provider_name = 'elevenlabs'
    RADIO_VOICE_SETTINGS = {
        'stability': 0.45,
        'similarity_boost': 0.75,
        'style': 0.40,
        'use_speaker_boost': True,
    }

    def __init__(self, presenter: PresenterConfig) -> None:
        self._presenter = presenter
        self._settings = presenter.elevenlabs

    @property
    def presenter_name(self) -> str:
        return self._presenter.presenter_name

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
            raise TtsProviderError(
                provider=self.provider_name,
                code='provider_not_configured',
                message='ElevenLabs is not configured. Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID.',
            )

        payload = json.dumps(
            {
                'text': text,
                'model_id': self.model,
                'voice_settings': self.RADIO_VOICE_SETTINGS,
            }
        ).encode('utf-8')
        request = urllib.request.Request(
            url=f'https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}?output_format={self.output_format}',
            data=payload,
            headers={
                'Accept': 'audio/mpeg',
                'Content-Type': 'application/json',
                'xi-api-key': self._settings.api_key,
            },
            method='POST',
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                output_path.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            details = exc.read().decode('utf-8', errors='ignore')
            raise TtsProviderError(
                provider=self.provider_name,
                code='provider_request_failed',
                message=f'ElevenLabs request failed with status {exc.code}.',
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise TtsProviderError(
                provider=self.provider_name,
                code='provider_network_error',
                message='ElevenLabs request failed because the provider could not be reached.',
            ) from exc
