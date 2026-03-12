from __future__ import annotations

import re

from app.services.tts.romanian_audio_lexicon import load_romanian_audio_lexicon


# This formatter applies a small, explicit editorial lexicon before TTS.
# It is intentionally conservative: exact matches only, no NLP, no co-reference.
# Example:
#   'CSAT a decis. CSAT a transmis.'
# becomes:
#   'Consiliul Suprem de Apărare a Țării a decis. consiliul a transmis.'


def apply_romanian_editorial_lexicon(blocks: list[str]) -> list[str]:
    if not blocks:
        return []

    seen_entities: set[str] = set()
    lexicon = load_romanian_audio_lexicon()
    formatted_blocks: list[str] = []

    for block in blocks:
        formatted_text = block
        for raw, entry in lexicon.items():
            pattern = re.compile(rf'\b{re.escape(raw)}\b')

            def replace(match: re.Match[str]) -> str:
                if raw not in seen_entities:
                    seen_entities.add(raw)
                    return entry.first_mention
                if entry.later_mention:
                    return entry.later_mention
                return match.group(0)

            formatted_text = pattern.sub(replace, formatted_text)

        formatted_blocks.append(formatted_text)

    return formatted_blocks


def apply_romanian_editorial_lexicon_to_text(text: str) -> str:
    if not text:
        return text
    formatted_blocks = apply_romanian_editorial_lexicon([text])
    return formatted_blocks[0] if formatted_blocks else text
