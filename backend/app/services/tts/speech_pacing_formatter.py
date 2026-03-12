from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TtsPacingConfig:
    pause_after_intro: int = 700
    pause_between_stories: int = 600
    pause_before_quotes: int = 300
    pause_before_outro: int = 700


TTS_PACING = TtsPacingConfig()


class SpeechPacingFormatter:
    def __init__(self, pacing: TtsPacingConfig = TTS_PACING) -> None:
        self._pacing = pacing

    def format_text_for_tts(self, story_blocks: list[str]) -> str:
        if not story_blocks:
            return ""

        cleaned_blocks = [block.strip() for block in story_blocks if block.strip()]
        if not cleaned_blocks:
            return ""

        paced_blocks = [self._apply_quote_pauses(block) for block in cleaned_blocks]
        formatted_blocks: list[str] = []
        last_index = len(paced_blocks) - 1

        for index, block in enumerate(paced_blocks):
            if index == 0:
                formatted_blocks.append(block)
                continue

            pause_duration = (
                self._pacing.pause_before_outro
                if index == last_index
                else self._pacing.pause_between_stories
            )
            if index == 1:
                pause_duration = self._pacing.pause_after_intro

            formatted_blocks.append(f"{self._pause_marker(pause_duration)}\n\n{block}")

        return "\n\n".join(formatted_blocks).strip()

    def format_blocks(self, story_blocks: list[str]) -> str:
        return self.format_text_for_tts(story_blocks)

    def _apply_quote_pauses(self, text: str) -> str:
        pause_marker = self._pause_marker(self._pacing.pause_before_quotes, inline=True)
        text = re.sub(r'(:)\s*(["„])', rf"\1 {pause_marker} \2", text)
        text = re.sub(r'(că)\s+(["„])', rf"\1 {pause_marker} \2", text)
        return text

    def _pause_marker(self, duration_ms: int, inline: bool = False) -> str:
        if duration_ms >= 650:
            return "...."
        if duration_ms >= 450:
            return "..."
        if inline:
            return ".."
        return "..."
