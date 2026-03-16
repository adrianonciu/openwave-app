from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

_SUFFIX_PATTERN = re.compile(r"(county|judetul|judet|municipiul|orasul|ora?ul|comuna|city|sectorul|sector)", re.IGNORECASE)

COUNTY_CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "Alba": ("Alba Iulia",),
    "Arad": ("Arad",),
    "Arges": ("Pitesti", "Campulung", "Curtea de Arges"),
    "Bacau": ("Bacau", "Onesti", "Moinesti"),
    "Bihor": ("Oradea",),
    "Bistrita-Nasaud": ("Bistrita",),
    "Botosani": ("Botosani", "Dorohoi"),
    "Braila": ("Braila",),
    "Brasov": ("Brasov",),
    "Bucuresti": ("Bucuresti", "Bucharest"),
    "Buzau": ("Buzau",),
    "Calarasi": ("Calarasi",),
    "Caras-Severin": ("Resita", "Caransebes"),
    "Cluj": ("Cluj", "Cluj-Napoca", "Turda", "Dej"),
    "Constanta": ("Constanta", "Mangalia"),
    "Covasna": ("Sfantu Gheorghe", "Targu Secuiesc"),
    "Dambovita": ("Targoviste",),
    "Dolj": ("Craiova",),
    "Galati": ("Galati", "Tecuci"),
    "Giurgiu": ("Giurgiu",),
    "Gorj": ("Targu Jiu",),
    "Harghita": ("Miercurea Ciuc", "Odorheiu Secuiesc"),
    "Hunedoara": ("Deva", "Hunedoara", "Petrosani"),
    "Ialomita": ("Slobozia",),
    "Iasi": ("Iasi", "Pascani"),
    "Ilfov": ("Buftea", "Voluntari", "Otopeni"),
    "Maramures": ("Baia Mare", "Sighetu Marmatiei"),
    "Mehedinti": ("Drobeta-Turnu Severin",),
    "Mures": ("Targu Mures", "Sighisoara"),
    "Neamt": ("Piatra Neamt", "Roman"),
    "Olt": ("Slatina",),
    "Prahova": ("Ploiesti", "Campina"),
    "Salaj": ("Zalau",),
    "Satu Mare": ("Satu Mare",),
    "Sibiu": ("Sibiu", "Medias"),
    "Suceava": ("Suceava", "Falticeni", "Radauti"),
    "Teleorman": ("Alexandria", "Rosiori de Vede"),
    "Timis": ("Timisoara", "Lugoj"),
    "Tulcea": ("Tulcea",),
    "Valcea": ("Ramnicu Valcea", "Ramnicul Valcea"),
    "Vaslui": ("Vaslui", "Barlad", "Husi"),
    "Vrancea": ("Focsani",),
}

COUNTY_MACRO_REGION: dict[str, str] = {
    "Alba": "Transilvania",
    "Arad": "Crisana",
    "Arges": "Muntenia",
    "Bacau": "Moldova",
    "Bihor": "Crisana",
    "Bistrita-Nasaud": "Transilvania",
    "Botosani": "Moldova",
    "Braila": "Muntenia",
    "Brasov": "Transilvania",
    "Bucuresti": "Bucuresti-Ilfov",
    "Buzau": "Muntenia",
    "Calarasi": "Muntenia",
    "Caras-Severin": "Banat",
    "Cluj": "Transilvania",
    "Constanta": "Dobrogea",
    "Covasna": "Transilvania",
    "Dambovita": "Muntenia",
    "Dolj": "Oltenia",
    "Galati": "Moldova",
    "Giurgiu": "Muntenia",
    "Gorj": "Oltenia",
    "Harghita": "Transilvania",
    "Hunedoara": "Transilvania",
    "Ialomita": "Muntenia",
    "Iasi": "Moldova",
    "Ilfov": "Bucuresti-Ilfov",
    "Maramures": "Maramures",
    "Mehedinti": "Oltenia",
    "Mures": "Transilvania",
    "Neamt": "Moldova",
    "Olt": "Oltenia",
    "Prahova": "Muntenia",
    "Salaj": "Transilvania",
    "Satu Mare": "Maramures",
    "Sibiu": "Transilvania",
    "Suceava": "Moldova",
    "Teleorman": "Muntenia",
    "Timis": "Banat",
    "Tulcea": "Dobrogea",
    "Valcea": "Oltenia",
    "Vaslui": "Moldova",
    "Vrancea": "Moldova",
}

COUNTY_ALIASES = {county: {county, *cities} for county, cities in COUNTY_CITY_ALIASES.items()}


@dataclass(frozen=True)
class ResolvedRomanianGeography:
    input_city: str | None
    input_region: str | None
    resolved_city: str | None
    resolved_county: str | None
    resolved_macro_region: str | None


def _normalize(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    ascii_value = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    ascii_value = _SUFFIX_PATTERN.sub(" ", ascii_value)
    ascii_value = ascii_value.replace("-", " ")
    return re.sub(r"\s+", " ", ascii_value).strip()


_NORMALIZED_COUNTY_ALIASES: dict[str, str] = {}
for county_name, aliases in COUNTY_ALIASES.items():
    for alias in aliases:
        _NORMALIZED_COUNTY_ALIASES[_normalize(alias)] = county_name


def resolve_county(value: str | None) -> str | None:
    normalized = _normalize(value)
    return _NORMALIZED_COUNTY_ALIASES.get(normalized)


def resolve_macro_region(county: str | None) -> str | None:
    return COUNTY_MACRO_REGION.get(county or "")


def resolve_listener_geography(city: str | None = None, region: str | None = None) -> ResolvedRomanianGeography:
    resolved_county = resolve_county(region) or resolve_county(city)
    resolved_city = (city or "").strip() or None
    return ResolvedRomanianGeography(
        input_city=(city or "").strip() or None,
        input_region=(region or "").strip() or None,
        resolved_city=resolved_city,
        resolved_county=resolved_county,
        resolved_macro_region=resolve_macro_region(resolved_county),
    )


def regional_aliases(county: str | None, macro_region: str | None = None) -> set[str]:
    aliases: set[str] = set()
    if county:
        aliases.add(_normalize(county))
    if macro_region:
        aliases.add(_normalize(macro_region))
    return {alias for alias in aliases if alias}
