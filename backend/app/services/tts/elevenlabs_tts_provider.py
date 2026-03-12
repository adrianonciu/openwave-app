from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from app.config.presenter import PresenterConfig
from app.services.tts.base_tts_provider import BaseTtsProvider


class ElevenLabsTtsProvider(BaseTtsProvider):
    provider_name = "elevenlabs"

    def __init__(self, presenter: PresenterConfig) -> None:
        self._settings = presenter.elevenlabs

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
                "ElevenLabs is not configured. Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID."
            )

        payload = json.dumps(
            {
                "text": text,
                "model_id": self.model,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url=f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}?output_format={self.output_format}",
            data=payload,
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self._settings.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                output_path.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"ElevenLabs request failed: {exc.code} {details}".strip()
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"ElevenLabs request failed: {exc.reason}") from exc
