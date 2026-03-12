from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path

from app.config.presenter import get_presenter_config
from app.services.tts.speech_pacing_formatter import SpeechPacingFormatter
from app.services.tts.tts_factory import create_tts_provider


class TtsService:
    def __init__(self) -> None:
        self.generated_audio_directory = Path(tempfile.gettempdir()) / "openwave_generated_audio"
        self.generated_audio_directory.mkdir(parents=True, exist_ok=True)
        self._pilot_files = {
            "pilot_01": Path("docs/editorial/testing/pilot_01_briefing_ro.md"),
            "pilot_02": Path("docs/editorial/testing/pilot_02_briefing_ro.md"),
            "pilot_03": Path("docs/editorial/testing/pilot_03_briefing_ro.md"),
        }
        self._pacing_formatter = SpeechPacingFormatter()

    def get_pilot_summaries(self) -> list[dict[str, str]]:
        summaries: list[dict[str, str]] = []
        presenter_name = get_presenter_config().presenter_name
        for pilot_id, relative_path in self._pilot_files.items():
            file_path = self._resolve_project_path(relative_path)
            title = self._extract_title(file_path.read_text(encoding="utf-8-sig"))
            summaries.append(
                {
                    "pilot_id": pilot_id,
                    "title": title,
                    "presenter_name": presenter_name,
                }
            )
        return summaries

    def generate_pilot_audio(self, pilot_id: str, presenter_name: str | None = None) -> dict[str, str]:
        normalized_pilot_id = pilot_id.strip().lower()
        if normalized_pilot_id not in self._pilot_files:
            raise FileNotFoundError(f"Unknown pilot id: {pilot_id}")

        file_path = self._resolve_project_path(self._pilot_files[normalized_pilot_id])
        raw_markdown = file_path.read_text(encoding="utf-8-sig")
        title = self._extract_title(raw_markdown)
        audio_blocks = self.extract_audio_blocks_from_markdown(raw_markdown)
        briefing_text = self._pacing_formatter.format_text_for_tts(audio_blocks)
        audio = self.generate_audio(
            briefing_text=briefing_text,
            presenter_name=presenter_name,
            file_stem=normalized_pilot_id,
        )
        return {
            "pilot_id": normalized_pilot_id,
            "title": title,
            "briefing_text": briefing_text,
            **audio,
        }

    def generate_audio(
        self,
        briefing_text: str,
        presenter_name: str | None = None,
        file_stem: str | None = None,
    ) -> dict[str, str]:
        cleaned_text = self._clean_briefing_text(briefing_text)
        if not cleaned_text:
            raise ValueError("briefing_text must not be empty.")

        presenter = get_presenter_config(presenter_name)
        provider = create_tts_provider(presenter)
        safe_stem = self._safe_stem(file_stem or presenter.presenter_name)
        fingerprint = hashlib.md5(
            f"{presenter.presenter_name}|{provider.provider_name}|{provider.voice_id}|{provider.model}|{cleaned_text}".encode(
                "utf-8"
            )
        ).hexdigest()[:10]
        file_name = f"{safe_stem}_{presenter.presenter_name.casefold()}_{fingerprint}.{provider.output_extension}"
        output_path = self.generated_audio_directory / file_name

        if not output_path.exists() or output_path.stat().st_size == 0:
            provider.synthesize(cleaned_text, output_path)

        return {
            "audio_url": f"/audio/generated/{file_name}",
            "presenter_name": presenter.presenter_name,
            "tts_provider": provider.provider_name,
            "tts_voice_id": provider.voice_id,
        }

    def extract_audio_blocks_from_markdown(self, markdown: str) -> list[str]:
        lines = markdown.splitlines()
        blocks: list[str] = []
        capture = False
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped == "- Text citit în audio:":
                if current_lines:
                    blocks.append(" ".join(current_lines).strip())
                    current_lines = []
                capture = True
                continue

            if capture:
                if not stripped or stripped.startswith("- ") or stripped.startswith("##") or stripped.startswith("###"):
                    if current_lines:
                        blocks.append(" ".join(current_lines).strip())
                        current_lines = []
                    capture = False
                    if not stripped:
                        continue

                if capture:
                    current_lines.append(stripped)
                    continue

        if current_lines:
            blocks.append(" ".join(current_lines).strip())

        if not blocks:
            raise ValueError("No audio narration blocks found in markdown.")

        return blocks

    def _resolve_project_path(self, relative_path: Path) -> Path:
        project_root = Path(__file__).resolve().parents[3]
        return project_root / relative_path

    def _extract_title(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped.removeprefix("# ").strip()
        return "OpenWave Pilot"

    def _clean_briefing_text(self, briefing_text: str) -> str:
        normalized = briefing_text.replace("\r\n", "\n")
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        normalized = re.sub(r"[ \t]+", " ", normalized)
        return normalized.strip()

    def _safe_stem(self, file_stem: str) -> str:
        normalized = file_stem.strip().lower() or "briefing"
        return re.sub(r"[^a-z0-9_-]+", "_", normalized)
