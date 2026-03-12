from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


@dataclass(frozen=True)
class NormalizationRule:
    key: str
    replacement: str
    pattern: str


@dataclass(frozen=True)
class NormalizationResult:
    text: str
    applied_rules: list[str]


class PronunciationNormalizer:
    _CURRENT_YEAR = date.today().year
    _ROMANIAN_MONTHS = (
        'ianuarie',
        'februarie',
        'martie',
        'aprilie',
        'mai',
        'iunie',
        'iulie',
        'august',
        'septembrie',
        'octombrie',
        'noiembrie',
        'decembrie',
    )
    _DIRECT_RULES = (
        NormalizationRule(
            key='CSAT',
            pattern=r'\bCSAT\b',
            replacement='Consiliul Suprem de Apărare a Țării',
        ),
        NormalizationRule(
            key='CNAIR',
            pattern=r'\bCNAIR\b',
            replacement='Compania Națională de Administrare a Infrastructurii Rutiere',
        ),
        NormalizationRule(
            key='SF',
            pattern=r'\bSF\b',
            replacement='science-fiction',
        ),
    )

    def normalize(self, text: str) -> NormalizationResult:
        normalized_text = text
        applied_rules: list[str] = []

        normalized_text, date_replacements = self._omit_current_year_in_dates(normalized_text)
        if date_replacements:
            applied_rules.append('current_year_dates')

        for rule in self._DIRECT_RULES:
            updated_text, replacements = re.subn(rule.pattern, rule.replacement, normalized_text)
            if replacements:
                normalized_text = updated_text
                applied_rules.append(rule.key)

        normalized_text, number_replacements = self._normalize_thousands_range_numbers(normalized_text)
        if number_replacements:
            applied_rules.append('thousands_range_numbers')

        return NormalizationResult(text=normalized_text, applied_rules=applied_rules)

    def _omit_current_year_in_dates(self, text: str) -> tuple[str, int]:
        months_pattern = '|'.join(self._ROMANIAN_MONTHS)
        pattern = rf'\b(\d{{1,2}}\s+(?:{months_pattern}))\s+{self._CURRENT_YEAR}\b'
        return re.subn(pattern, r'\1', text, flags=re.IGNORECASE)

    def _normalize_thousands_range_numbers(self, text: str) -> tuple[str, int]:
        replacement_count = 0

        def replacer(match: re.Match[str]) -> str:
            nonlocal replacement_count
            raw_value = match.group(0)
            integer_value = int(raw_value.replace('.', ''))
            if integer_value < 1000 or integer_value > 999999:
                return raw_value
            if 1900 <= integer_value <= 2100:
                return raw_value

            replacement_count += 1
            return self._number_to_words(integer_value)

        normalized_text = re.sub(r'\b\d{1,3}(?:\.\d{3})+\b', replacer, text)
        normalized_text = re.sub(r'\b\d{4,6}\b', replacer, normalized_text)
        return normalized_text, replacement_count

    def _number_to_words(self, value: int) -> str:
        under_twenty = {
            0: 'zero',
            1: 'unu',
            2: 'două',
            3: 'trei',
            4: 'patru',
            5: 'cinci',
            6: 'șase',
            7: 'șapte',
            8: 'opt',
            9: 'nouă',
            10: 'zece',
            11: 'unsprezece',
            12: 'douăsprezece',
            13: 'treisprezece',
            14: 'paisprezece',
            15: 'cincisprezece',
            16: 'șaisprezece',
            17: 'șaptesprezece',
            18: 'optsprezece',
            19: 'nouăsprezece',
        }
        tens_words = {
            2: 'douăzeci',
            3: 'treizeci',
            4: 'patruzeci',
            5: 'cincizeci',
            6: 'șaizeci',
            7: 'șaptezeci',
            8: 'optzeci',
            9: 'nouăzeci',
        }

        def under_one_thousand(number: int) -> str:
            if number < 20:
                return under_twenty[number]
            if number < 100:
                tens, remainder = divmod(number, 10)
                if remainder == 0:
                    return tens_words[tens]
                return f"{tens_words[tens]} și {under_twenty[remainder]}"

            hundreds, remainder = divmod(number, 100)
            if hundreds == 1:
                prefix = 'o sută'
            elif hundreds == 2:
                prefix = 'două sute'
            else:
                prefix = f"{under_twenty[hundreds]} sute"

            if remainder == 0:
                return prefix
            return f"{prefix} {under_one_thousand(remainder)}"

        thousands, remainder = divmod(value, 1000)
        if thousands == 0:
            return under_one_thousand(value)

        if thousands == 1:
            thousands_text = 'o mie'
        elif thousands == 2:
            thousands_text = 'două mii'
        elif 3 <= thousands < 20:
            thousands_text = f"{under_one_thousand(thousands)} mii"
        else:
            thousands_text = f"{under_one_thousand(thousands)} de mii"

        if remainder == 0:
            return thousands_text
        return f"{thousands_text} {under_one_thousand(remainder)}"
