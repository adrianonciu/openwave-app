from __future__ import annotations

import re

from app.services.tts.romanian_audio_lexicon import load_romanian_audio_lexicon

# Example:
# Input: "Decizia CSAT a fost anunțată astăzi."
# Output: "Decizia Consiliul Suprem de Apărare a Țării a fost anunțată astăzi."
#
# Example:
# Input: "CNAIR a anunțat 12 lucrări."
# Output: "compania de drumuri a anunțat douăsprezece lucrări."

# Acronym spelling is only a limited fallback for a few problematic cases.
# In many situations, the full expanded form or a radio-friendly editorial rewrite
# is preferable to forcing letter-by-letter pronunciation in TTS.
ACRONYM_MAP = {
    'CSAT': 'Ce Se A Te',
    'CNAIR': 'Ce Ne A Ir',
}


def normalize_for_romanian_tts(text: str) -> str:
    if not text:
        return text

    normalized = _normalize_spacing(text)
    normalized = _apply_lexicon_tts_hints(normalized)
    normalized = _expand_acronyms(normalized)
    normalized = _normalize_spacing(normalized)
    return normalized


def _apply_lexicon_tts_hints(text: str) -> str:
    normalized = text
    for raw, entry in load_romanian_audio_lexicon().items():
        if not entry.tts_hint:
            continue
        normalized = re.sub(rf'\b{re.escape(raw)}\b', entry.tts_hint, normalized)
    return normalized


def _expand_acronyms(text: str) -> str:
    normalized = text
    for acronym, replacement in ACRONYM_MAP.items():
        normalized = re.sub(rf'\b{re.escape(acronym)}\b', replacement, normalized)
    return normalized


def _normalize_spacing(text: str) -> str:
    normalized = text.replace('\r\n', '\n')
    normalized = re.sub(r'[ \t]+', ' ', normalized)
    normalized = re.sub(r'\s+([,.;:!?])', r'\1', normalized)
    normalized = re.sub(r'([,.;:!?])([^\s"\')\]])', r'\1 \2', normalized)
    normalized = re.sub(r'\n{3,}', '\n\n', normalized)
    return normalized.strip()
