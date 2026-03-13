from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.config.presenter import get_presenter_config
from app.services.tts.editorial_entity_formatter import (
    apply_romanian_editorial_lexicon,
    apply_romanian_editorial_lexicon_to_text,
)
from app.services.tts.romanian_numbers_normalizer import normalize_romanian_numbers_for_tts
from app.services.tts.romanian_tts_normalizer import normalize_for_romanian_tts
from app.services.tts.speech_pacing_formatter import SpeechPacingFormatter
from app.services.tts.tts_factory import create_tts_provider


class TtsService:
    def __init__(self) -> None:
        self.generated_audio_directory = self._resolve_project_path(
            Path('backend/generated_audio')
        )
        self.generated_audio_directory.mkdir(parents=True, exist_ok=True)
        self._pilot_files = {
            'pilot_01': Path('docs/editorial/testing/pilot_01_briefing_ro.md'),
            'pilot_02': Path('docs/editorial/testing/pilot_02_briefing_ro.md'),
            'pilot_03': Path('docs/editorial/testing/pilot_03_briefing_ro.md'),
        }
        self._pacing_formatter = SpeechPacingFormatter()

    def get_pilot_summaries(self) -> list[dict[str, str]]:
        summaries: list[dict[str, str]] = []
        presenter_name = get_presenter_config().presenter_name
        for pilot_id, relative_path in self._pilot_files.items():
            file_path = self._resolve_project_path(relative_path)
            title = self._extract_title(file_path.read_text(encoding='utf-8-sig'))
            summaries.append(
                {
                    'pilot_id': pilot_id,
                    'title': title,
                    'presenter_name': presenter_name,
                }
            )
        return summaries

    def generate_pilot_audio(self, pilot_id: str, presenter_name: str | None = None) -> dict[str, str | list[str]]:
        normalized_pilot_id = pilot_id.strip().lower()
        if normalized_pilot_id not in self._pilot_files:
            raise FileNotFoundError(f'Unknown pilot id: {pilot_id}')

        file_path = self._resolve_project_path(self._pilot_files[normalized_pilot_id])
        raw_markdown = file_path.read_text(encoding='utf-8-sig')
        title = self._extract_title(raw_markdown)
        segment_blocks = self.extract_named_audio_segments_from_markdown(raw_markdown)
        segment_result = self.generate_audio_segments(
            segment_blocks=segment_blocks,
            presenter_name=presenter_name,
            file_stem=normalized_pilot_id,
        )
        return {
            'pilot_id': normalized_pilot_id,
            'title': title,
            **segment_result,
        }

    def generate_audio(
        self,
        briefing_text: str,
        presenter_name: str | None = None,
        file_stem: str | None = None,
    ) -> dict[str, str]:
        cleaned_text = self._clean_briefing_text(briefing_text)
        if not cleaned_text:
            raise ValueError('briefing_text must not be empty.')

        cleaned_text = normalize_romanian_numbers_for_tts(cleaned_text)
        cleaned_text = apply_romanian_editorial_lexicon_to_text(cleaned_text)
        cleaned_text = normalize_for_romanian_tts(cleaned_text)

        presenter = get_presenter_config(presenter_name)
        provider = create_tts_provider(presenter)
        safe_stem = self._safe_stem(file_stem or presenter.presenter_name)
        fingerprint = hashlib.md5(
            (
                f'{presenter.presenter_name}|{provider.provider_name}|{provider.voice_id}|{provider.model}|{provider.output_format}|'
                f'{self._provider_tuning_signature(presenter, provider.provider_name)}|{cleaned_text}'
            ).encode('utf-8')
        ).hexdigest()[:10]
        file_name = f'{safe_stem}_{presenter.presenter_name.casefold()}_{fingerprint}.{provider.output_extension}'
        output_path = self.generated_audio_directory / file_name

        if not output_path.exists() or output_path.stat().st_size == 0:
            provider.synthesize(cleaned_text, output_path)

        return {
            'audio_url': f'/audio/generated/{file_name}',
            'presenter_name': presenter.presenter_name,
            'tts_provider': provider.provider_name,
            'tts_voice_id': provider.voice_id,
        }

    def generate_audio_segments(
        self,
        segment_blocks: list[dict[str, str]],
        presenter_name: str | None = None,
        file_stem: str | None = None,
    ) -> dict[str, str | list[str]]:
        if not segment_blocks:
            raise ValueError('segment_blocks must not be empty.')

        presenter = get_presenter_config(presenter_name)
        provider = create_tts_provider(presenter)
        safe_stem = self._safe_stem(file_stem or presenter.presenter_name)
        segment_urls: list[str] = []
        editorial_blocks = apply_romanian_editorial_lexicon([segment['text'] for segment in segment_blocks])

        for segment, editorial_text in zip(segment_blocks, editorial_blocks):
            cleaned_text = self._clean_briefing_text(
                self._pacing_formatter.format_text_for_tts([editorial_text])
            )
            if not cleaned_text:
                continue

            cleaned_text = normalize_romanian_numbers_for_tts(cleaned_text)
            cleaned_text = normalize_for_romanian_tts(cleaned_text)

            segment_name = self._safe_stem(segment['segment_name'])
            file_name = f'{safe_stem}_{segment_name}.{provider.output_extension}'
            output_path = self.generated_audio_directory / file_name

            if not output_path.exists() or output_path.stat().st_size == 0:
                provider.synthesize(cleaned_text, output_path)

            segment_urls.append(f'/audio/generated/{file_name}')

        if not segment_urls:
            raise ValueError('No audio segments were generated.')

        return {
            'segments': segment_urls,
            'presenter_name': presenter.presenter_name,
            'tts_provider': provider.provider_name,
            'tts_voice_id': provider.voice_id,
        }

    def extract_audio_blocks_from_markdown(self, markdown: str) -> list[str]:
        return [segment['text'] for segment in self.extract_named_audio_segments_from_markdown(markdown)]

    def extract_named_audio_segments_from_markdown(self, markdown: str) -> list[dict[str, str]]:
        lines = markdown.splitlines()
        segments: list[dict[str, str]] = []
        capture = False
        current_lines: list[str] = []
        current_section: str | None = None
        current_segment_name: str | None = None

        def flush_segment() -> None:
            nonlocal current_lines, current_segment_name
            if current_segment_name and current_lines:
                segments.append(
                    {
                        'segment_name': current_segment_name,
                        'text': ' '.join(current_lines).strip(),
                    }
                )
            current_lines = []
            current_segment_name = None

        for line in lines:
            stripped = line.strip()

            if stripped.startswith('## '):
                if capture:
                    flush_segment()
                    capture = False
                current_section = stripped[3:].strip()
                continue

            if 'Text citit' in stripped and 'audio:' in stripped:
                if capture:
                    flush_segment()
                current_segment_name = self._segment_name_for_section(current_section, len(segments))
                capture = current_segment_name is not None
                continue

            if capture:
                if not stripped or stripped.startswith('- ') or stripped.startswith('##') or stripped.startswith('###'):
                    flush_segment()
                    capture = False
                    if stripped.startswith('## '):
                        current_section = stripped[3:].strip()
                    continue

                current_lines.append(stripped)

        if capture:
            flush_segment()

        if not segments:
            raise ValueError('No audio narration blocks found in markdown.')

        return segments

    def _segment_name_for_section(self, current_section: str | None, existing_segments: int) -> str | None:
        if not current_section:
            return None

        normalized_section = current_section.strip().upper()
        if normalized_section.startswith('INTRO'):
            return 'intro'
        if normalized_section.startswith('OUTRO'):
            return 'outro'

        item_match = re.match(r'ITEM\s+(\d+)', normalized_section)
        if item_match:
            return f"story_{int(item_match.group(1)):02d}"

        if 'ITEM' in normalized_section:
            return f'story_{existing_segments:02d}'

        return None

    def _resolve_project_path(self, relative_path: Path) -> Path:
        project_root = Path(__file__).resolve().parents[3]
        return project_root / relative_path

    def _extract_title(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('# '):
                return stripped.removeprefix('# ').strip()
        return 'OpenWave Pilot'

    def _clean_briefing_text(self, briefing_text: str) -> str:
        normalized = briefing_text.replace('\r\n', '\n')
        normalized = re.sub(r'\n{3,}', '\n\n', normalized)
        normalized = re.sub(r'[ \t]+', ' ', normalized)
        return normalized.strip()

    def _safe_stem(self, file_stem: str) -> str:
        normalized = file_stem.strip().lower() or 'briefing'
        return re.sub(r'[^a-z0-9_-]+', '_', normalized)

    def _provider_tuning_signature(self, presenter, provider_name: str) -> str:
        if provider_name == 'elevenlabs':
            tuning = presenter.elevenlabs.tuning
        else:
            tuning = presenter.openai.tuning

        return (
            f'{tuning.stability}|{tuning.similarity_boost}|{tuning.style}|'
            f'{tuning.use_speaker_boost}|{tuning.speed}'
        )
