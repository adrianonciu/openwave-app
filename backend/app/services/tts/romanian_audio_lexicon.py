from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class RomanianAudioLexiconEntry:
    raw: str
    type: str
    first_mention: str
    later_mention: str
    tts_hint: str


# This lexicon derives from the editorial radio-style rule for entities and acronyms.
# It is not a universal automatic rewriting system, and the editor or text generator
# remains responsible for choosing the final wording in the script.
LEXICON_PATH = Path(__file__).with_name('romanian_audio_lexicon.json')


@lru_cache(maxsize=1)
def load_romanian_audio_lexicon() -> dict[str, RomanianAudioLexiconEntry]:
    raw_data = json.loads(LEXICON_PATH.read_text(encoding='utf-8-sig'))
    return {
        raw: RomanianAudioLexiconEntry(
            raw=raw,
            type=entry.get('type', 'editorial'),
            first_mention=entry.get('first_mention', raw),
            later_mention=entry.get('later_mention', ''),
            tts_hint=entry.get('tts_hint', raw),
        )
        for raw, entry in raw_data.items()
    }


def get_romanian_audio_lexicon_entry(entity: str) -> RomanianAudioLexiconEntry | None:
    if not entity:
        return None
    return load_romanian_audio_lexicon().get(entity.strip())
