"""Country handling for geographic job search.

The Adzuna aggregator (our Indeed-and-friends source) is queried per country,
so "search worldwide" means iterating over every supported country endpoint.

Usage in the agent:
  * the user passes certain countries (codes or names) -> we search those
  * the user passes none -> we search WORLD (all supported countries)
"""

from __future__ import annotations

# Adzuna's supported country endpoints: ISO code -> display name.
SUPPORTED: dict[str, str] = {
    "gb": "United Kingdom", "us": "United States", "at": "Austria",
    "au": "Australia", "be": "Belgium", "br": "Brazil", "ca": "Canada",
    "ch": "Switzerland", "de": "Germany", "es": "Spain", "fr": "France",
    "in": "India", "it": "Italy", "mx": "Mexico", "nl": "Netherlands",
    "nz": "New Zealand", "pl": "Poland", "sg": "Singapore", "za": "South Africa",
}

# Everything, for the "around the world" default.
WORLD: list[str] = list(SUPPORTED.keys())

# Common names / synonyms -> ISO code, so users can type "USA", "UK", etc.
_ALIASES: dict[str, str] = {
    "uk": "gb", "u.k.": "gb", "britain": "gb", "great britain": "gb",
    "england": "gb", "united kingdom": "gb",
    "usa": "us", "u.s.": "us", "u.s.a.": "us", "america": "us",
    "united states": "us", "united states of america": "us",
    "deutschland": "de", "germany": "de",
    "españa": "es", "spain": "es", "holland": "nl", "netherlands": "nl",
    "schweiz": "ch", "switzerland": "ch", "österreich": "at", "austria": "at",
    "aus": "au", "australia": "au", "nz": "nz", "new zealand": "nz",
    "can": "ca", "canada": "ca", "france": "fr", "italy": "it", "italia": "it",
    "brazil": "br", "brasil": "br", "india": "in", "mexico": "mx", "méxico": "mx",
    "poland": "pl", "polska": "pl", "singapore": "sg", "south africa": "za",
    "belgium": "be", "belgique": "be",
}


def resolve_countries(values: list[str] | None) -> tuple[list[str], list[str]]:
    """Normalize a list of country codes/names to supported ISO codes.

    Returns (resolved_codes, unknown_inputs). An empty/None input yields an
    empty resolved list — the caller treats that as "search worldwide".
    """
    if not values:
        return [], []

    resolved: list[str] = []
    unknown: list[str] = []
    for raw in values:
        key = raw.strip().lower()
        if not key:
            continue
        if key in SUPPORTED:
            code = key
        elif key in _ALIASES:
            code = _ALIASES[key]
        else:
            unknown.append(raw)
            continue
        if code not in resolved:
            resolved.append(code)
    return resolved, unknown


def names(codes: list[str]) -> str:
    return ", ".join(SUPPORTED.get(c, c) for c in codes)
