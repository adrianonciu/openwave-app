from __future__ import annotations

import json
from pathlib import Path
import re
import unicodedata

from app.models.local_source_registry import LocalCountySourceGroup, LocalSourceEntry

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "romanian_local_sources_by_county.json"
_SUFFIX_PATTERN = re.compile(r"\b(county|judetul|judet|region|regiunea)\b", re.IGNORECASE)


class LocalSourceRegistryService:
    def load_registry(self) -> list[LocalCountySourceGroup]:
        raw_data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return [LocalCountySourceGroup(**item) for item in raw_data.get("counties", [])]

    def get_local_sources_for_region(self, region: str) -> list[LocalSourceEntry]:
        normalized_region = self._normalize_region_key(region)
        if not normalized_region:
            return []

        for county in self.load_registry():
            if self._normalize_region_key(county.county_name) == normalized_region:
                return [entry for entry in county.source_entries if entry.enabled]
        return []

    def has_local_sources_for_region(self, region: str) -> bool:
        return bool(self.get_local_sources_for_region(region))

    def _normalize_region_key(self, value: str | None) -> str:
        raw_value = (value or "").strip().lower()
        if not raw_value:
            return ""
        ascii_value = unicodedata.normalize("NFKD", raw_value).encode("ascii", "ignore").decode("ascii")
        ascii_value = _SUFFIX_PATTERN.sub(" ", ascii_value)
        ascii_value = ascii_value.replace("-", " ")
        ascii_value = re.sub(r"\s+", " ", ascii_value).strip()
        return ascii_value
