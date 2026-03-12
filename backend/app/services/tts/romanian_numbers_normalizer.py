from __future__ import annotations

import re
from datetime import date

# Example:
# Input: "Inflația a ajuns la 5% în 2025."
# Output: "Inflația a ajuns la cinci la sută în două mii douăzeci și cinci."
#
# Example:
# Input: "Guvernul alocă 3 milioane de euro."
# Output: "Guvernul alocă trei milioane de euro."
#
# Example:
# Input: "CNAIR anunță 12 lucrări noi."
# Output: "CNAIR anunță douăsprezece lucrări noi."
#
# Example:
# Input: "Ședința începe la 14:30."
# Output: "Ședința începe la paisprezece și treizeci."
#
# Example:
# Input: "Inflația anuală a urcat la 3,5%."
# Output: "Inflația anuală a urcat la trei virgulă cinci la sută."

_CURRENT_YEAR = date.today().year
_DATE_PLACEHOLDER = '__OW_COMPACT_DATE_'

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


def normalize_romanian_numbers_for_tts(text: str) -> str:
    if not text:
        return text

    normalized, protected_dates = _protect_invalid_compact_dates(text)
    normalized = normalize_simple_times(normalized)
    normalized = normalize_compact_dates(normalized)
    normalized = normalize_large_amounts(normalized)
    normalized = normalize_decimal_percentages(normalized)
    normalized = normalize_percentages(normalized)
    normalized = normalize_years(normalized)
    normalized = normalize_simple_currency(normalized)
    normalized = normalize_basic_numbers(normalized)
    return _restore_protected_dates(normalized, protected_dates)


def normalize_simple_times(text: str) -> str:
    text = _normalize_hour_phrases(text)
    return _normalize_colon_times(text)


def normalize_compact_dates(text: str) -> str:
    pattern = re.compile(r'\b(\d{1,2})([./])(\d{1,2})\2(\d{4})\b')

    def replace(match: re.Match[str]) -> str:
        day = int(match.group(1))
        month = int(match.group(3))
        year = int(match.group(4))

        if not _is_valid_compact_date(day, month, year):
            return match.group(0)

        month_name = _ROMANIAN_MONTHS[month - 1]
        day_text = _number_to_words(day)
        if year == _CURRENT_YEAR:
            return f'{day_text} {month_name}'
        return f'{day_text} {month_name} {_year_to_words(year)}'

    return pattern.sub(replace, text)


def normalize_decimal_percentages(text: str) -> str:
    pattern = re.compile(r'\b(\d{1,2}),(\d{1,2})\s*%')

    def replace(match: re.Match[str]) -> str:
        whole = int(match.group(1))
        if whole > 100:
            return match.group(0)
        return f'{_number_to_words(whole)} virgulă {_digits_to_words(match.group(2))} la sută'

    return pattern.sub(replace, text)


def normalize_large_amounts(text: str) -> str:
    pattern = re.compile(
        r'\b(\d{1,3})\s+(milioane|miliard(?:e)?)\b(\s+de\s+(?:lei|euro|dolari))?',
        flags=re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        value = int(match.group(1))
        unit = match.group(2).lower()
        trailing = match.group(3) or ''
        if value > 20:
            return match.group(0)
        return f'{_number_to_words(value, feminine=True)} {unit}{trailing}'

    return pattern.sub(replace, text)


def normalize_percentages(text: str) -> str:
    pattern = re.compile(r'\b(\d{1,3})\s*%')

    def replace(match: re.Match[str]) -> str:
        value = int(match.group(1))
        if value > 100:
            return match.group(0)
        return f'{_number_to_words(value)} la sută'

    return pattern.sub(replace, text)


def normalize_years(text: str) -> str:
    pattern = re.compile(r'\b(20\d{2})\b')
    return pattern.sub(lambda match: _year_to_words(int(match.group(1))), text)


def normalize_simple_currency(text: str) -> str:
    pattern = re.compile(r'\b(\d{1,3})\s+(lei|euro|dolari)\b', flags=re.IGNORECASE)

    def replace(match: re.Match[str]) -> str:
        value = int(match.group(1))
        currency = match.group(2).lower()
        if value > 999:
            return match.group(0)
        return f'{_number_to_words(value)} {currency}'

    return pattern.sub(replace, text)


def normalize_basic_numbers(text: str) -> str:
    months_pattern = '|'.join(_ROMANIAN_MONTHS)
    pattern = re.compile(rf'\b(\d{{1,3}})\b(?!\s*(?:{months_pattern})\b)(?!:)')

    def replace(match: re.Match[str]) -> str:
        value = int(match.group(1))
        return _number_to_words(value)

    return pattern.sub(replace, text)


def _normalize_hour_phrases(text: str) -> str:
    pattern = re.compile(r'\bora\s+(\d{1,2})\b', flags=re.IGNORECASE)

    def replace(match: re.Match[str]) -> str:
        hour = int(match.group(1))
        if hour > 23:
            return match.group(0)
        return f'ora {_number_to_words(hour)}'

    return pattern.sub(replace, text)


def _normalize_colon_times(text: str) -> str:
    pattern = re.compile(r'\b(?P<prefix>la\s+)?(?P<hour>\d{1,2}):(?P<minute>\d{2})\b', flags=re.IGNORECASE)

    def replace(match: re.Match[str]) -> str:
        hour = int(match.group('hour'))
        minute = int(match.group('minute'))
        if hour > 23 or minute > 59:
            return match.group(0)

        prefix = match.group('prefix') or ''
        hour_text = _number_to_words(hour)
        if minute == 0:
            return f'{prefix}{hour_text} fix'
        if minute < 10:
            return f'{prefix}{hour_text} și {_number_to_words(minute)} minute'
        return f'{prefix}{hour_text} și {_number_to_words(minute)}'

    return pattern.sub(replace, text)


def _number_to_words(value: int, feminine: bool = False) -> str:
    if value < 0 or value > 9999:
        return str(value)

    units_masc = {
        0: 'zero',
        1: 'unu',
        2: 'doi',
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
    units_fem = dict(units_masc)
    units_fem[1] = 'una'
    units_fem[2] = 'două'
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

    def under_one_thousand(number: int, local_feminine: bool = False) -> str:
        local_units = units_fem if local_feminine else units_masc
        if number < 20:
            return local_units[number]
        if number < 100:
            tens, remainder = divmod(number, 10)
            if remainder == 0:
                return tens_words[tens]
            return f"{tens_words[tens]} și {local_units[remainder]}"

        hundreds, remainder = divmod(number, 100)
        if hundreds == 1:
            prefix = 'o sută'
        elif hundreds == 2:
            prefix = 'două sute'
        else:
            prefix = f"{units_masc[hundreds]} sute"

        if remainder == 0:
            return prefix
        return f"{prefix} {under_one_thousand(remainder, local_feminine=local_feminine)}"

    if value < 1000:
        return under_one_thousand(value, local_feminine=feminine)

    thousands, remainder = divmod(value, 1000)
    if thousands == 1:
        thousands_text = 'o mie'
    elif thousands == 2:
        thousands_text = 'două mii'
    elif 3 <= thousands < 20:
        thousands_text = f"{under_one_thousand(thousands, local_feminine=True)} mii"
    else:
        thousands_text = f"{under_one_thousand(thousands)} de mii"

    if remainder == 0:
        return thousands_text
    return f"{thousands_text} {under_one_thousand(remainder)}"


def _year_to_words(value: int) -> str:
    if 2000 <= value <= 2099:
        if value == 2000:
            return 'două mii'
        return f"două mii {_number_to_words(value - 2000)}"
    return _number_to_words(value)


def _digits_to_words(value: str) -> str:
    return ' '.join(_number_to_words(int(character)) for character in value)


def _is_valid_compact_date(day: int, month: int, year: int) -> bool:
    if year < 1900 or year > 2100:
        return False
    if month < 1 or month > 12:
        return False
    if day < 1:
        return False

    month_lengths = {
        1: 31,
        2: 29 if _is_leap_year(year) else 28,
        3: 31,
        4: 30,
        5: 31,
        6: 30,
        7: 31,
        8: 31,
        9: 30,
        10: 31,
        11: 30,
        12: 31,
    }
    return day <= month_lengths[month]


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _protect_invalid_compact_dates(text: str) -> tuple[str, list[str]]:
    protected_dates: list[str] = []
    pattern = re.compile(r'\b(\d{1,2})([./])(\d{1,2})\2(\d{4})\b')

    def replace(match: re.Match[str]) -> str:
        day = int(match.group(1))
        month = int(match.group(3))
        year = int(match.group(4))
        if _is_valid_compact_date(day, month, year):
            return match.group(0)

        placeholder = f'{_DATE_PLACEHOLDER}{len(protected_dates)}__'
        protected_dates.append(match.group(0))
        return placeholder

    return pattern.sub(replace, text), protected_dates


def _restore_protected_dates(text: str, protected_dates: list[str]) -> str:
    restored = text
    for index, raw_date in enumerate(protected_dates):
        restored = restored.replace(f'{_DATE_PLACEHOLDER}{index}__', raw_date)
    return restored
