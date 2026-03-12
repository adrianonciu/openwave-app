from __future__ import annotations

import re


class SpeechPacingFormatter:
    def format_blocks(self, blocks: list[str]) -> str:
        if not blocks:
            return ""

        paced_blocks = [self._apply_quote_pauses(block.strip()) for block in blocks if block.strip()]
        if not paced_blocks:
            return ""

        formatted: list[str] = []
        for index, block in enumerate(paced_blocks):
            if index == 0:
                formatted.append(block)
                continue

            formatted.append("...\n\n" + block)

        return "\n\n".join(formatted).strip()

    def _apply_quote_pauses(self, text: str) -> str:
        text = re.sub(r'(:)\s*(["„])', r'\1 ... \2', text)
        text = re.sub(r'(că)\s+(["„])', r'\1 ... \2', text)
        return text
