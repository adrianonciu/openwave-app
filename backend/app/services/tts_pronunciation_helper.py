from __future__ import annotations

import re

PRONUNCIATION_MAP: dict[str, str] = {
    "Bolojan": "bo-lo-jan",
    "Viziteu": "vi-zi-teu",
    "Ormuz": "or-muz",
}


def get_tts_pronunciation_map() -> dict[str, str]:
    return dict(PRONUNCIATION_MAP)


def apply_tts_pronunciation_hints(text: str) -> str:
    if not text:
        return text

    normalized = text
    for raw, hint in PRONUNCIATION_MAP.items():
        normalized = re.sub(rf"\b{re.escape(raw)}\b", hint, normalized)
    return normalized
