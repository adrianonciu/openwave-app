from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from app.config.presenter import PresenterConfig
from app.services.tts.base_tts_provider import BaseTtsProvider
from app.services.tts.tts_provider_error import TtsProviderError


class OpenAITtsProvider(BaseTtsProvider):
    provider_name = 'openai'
    _DEFAULT_VOICE = 'alloy'
    _INSTRUCTION_BY_PRESENTER = {
        'ana': 'Esti Ana, prezentatoare de stiri radio. Citeste clar, natural, in limba romana, pe ton de jurnal de stiri.',
        'paul': 'Esti Paul, prezentator de stiri radio. Citeste clar, natural, in limba romana, pe ton de jurnal de stiri.',
    }
    _DEFAULT_INSTRUCTION = 'Citeste clar, natural, in limba romana, pe ton de jurnal de stiri.'

    def __init__(self, presenter: PresenterConfig) -> None:
        self._presenter = presenter
        self._settings = presenter.openai

    @property
    def presenter_name(self) -> str:
        return self._presenter.presenter_name

    @property
    def voice_id(self) -> str:
        configured_voice = self._settings.voice_id.strip().lower()
        return configured_voice or self._DEFAULT_VOICE

    @property
    def model(self) -> str:
        return self._settings.model

    @property
    def output_format(self) -> str:
        return self._settings.output_format

    def is_configured(self) -> bool:
        return bool(self._settings.api_key.strip())

    def synthesize(self, text: str, output_path: Path) -> None:
        if not self.is_configured():
            raise TtsProviderError(
                provider=self.provider_name,
                code='provider_not_configured',
                message='OpenAI TTS is not configured. Set OPENAI_API_KEY.',
            )

        payload = json.dumps(
            {
                'model': self.model,
                'voice': self.voice_id,
                'input': text,
                'instructions': self._instructions(),
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
            message = self._message_for_status(exc.code)
            if details:
                parsed = self._extract_error_message(details)
                if parsed:
                    message = f'{message} {parsed}'.strip()
            raise TtsProviderError(
                provider=self.provider_name,
                code='provider_request_failed',
                message=message,
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise TtsProviderError(
                provider=self.provider_name,
                code='provider_network_error',
                message='OpenAI TTS request failed because the provider could not be reached.',
            ) from exc

    def _instructions(self) -> str:
        return self._INSTRUCTION_BY_PRESENTER.get(
            self.presenter_name.casefold(),
            self._DEFAULT_INSTRUCTION,
        )

    def _message_for_status(self, status_code: int) -> str:
        return f'OpenAI TTS request failed with status {status_code}.'

    def _extract_error_message(self, details: str) -> str | None:
        try:
            payload = json.loads(details)
        except json.JSONDecodeError:
            return None

        error = payload.get('error') if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return None
        message = error.get('message')
        if not isinstance(message, str):
            return None
        return message.strip()
