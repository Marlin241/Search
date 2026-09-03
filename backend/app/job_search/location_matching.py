"""Location matching for job-search sources that carry a structured
`location` string (the crawled boards).

A plain accent-insensitive substring test is too strict for the West
African boards: a Dakar job is routinely posted with a location of
"Liberté 6, en face UNO" or "Diamniadio, Sénégal", and a Dakar job seeker
who typed "Dakar" should still see it. This module adds:

- neighbourhood / suburb -> metro matching ("Yopougon" counts as Abidjan);
- country-level matching: an offer located only at country level
  ("Sénégal") matches any city search from that country.

An offer that names a *different* city is NOT matched: a "Dakar" search
does not keep "Thiès, Sénégal".
"""

import re
import unicodedata

_FILLER_RE = re.compile(r"[\s'’.,;:/\\()\[\]–—-]+")


def _norm(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _FILLER_RE.sub(" ", no_accents).strip().lower()


# Neighbourhoods / suburbs / landmarks that mean "this metro area". Each set
# includes the metro's own name so `_resolve_metro("dakar")` -> "dakar".
_METRO_ALIASES: dict[str, frozenset[str]] = {
    "dakar": frozenset(
        {
            "dakar",
            "pikine",
            "guediawaye",
            "rufisque",
            "bargny",
            "diamniadio",
            "sebikotane",
            "sangalkam",
            "keur massar",
            "yeumbeul",
            "malika",
            "thiaroye",
            "liberte",
            "medina",
            "fann",
            "point e",
            "mermoz",
            "sacre coeur",
            "ouakam",
            "ngor",
            "yoff",
            "almadies",
            "grand dakar",
            "grand yoff",
            "hann",
            "hlm",
            "sicap",
            "parcelles",
            "patte d oie",
            "colobane",
            "gueule tapee",
            "castors",
            "dieuppeul",
            "camberene",
            "nord foire",
            "cite keur gorgui",
            "uno",
        }
    ),
    "abidjan": frozenset(
        {
            "abidjan",
            "cocody",
            "yopougon",
            "treichville",
            "marcory",
            "koumassi",
            "port bouet",
            "adjame",
            "attecoube",
            "abobo",
            "bingerville",
            "anyama",
            "riviera",
            "angre",
            "deux plateaux",
            "ii plateaux",
            "2 plateaux",
            "vridi",
            "zone 4",
            "grand bassam",
        }
    ),
}

_METRO_COUNTRY = {"dakar": "senegal", "abidjan": "cote d ivoire"}

# A location made up only of these tokens is "country level, no city".
_COUNTRY_TOKENS = (
    "cote d ivoire",
    "cote divoire",
    "ivory coast",
    "senegal",
    "rci",
    "afrique de l ouest",
    "afrique centrale",
    "afrique",
    "national",
    "nationale",
    "toute la region",
    "plusieurs villes",
    "several locations",
)


def _resolve_metro(text: str) -> str | None:
    for metro, aliases in _METRO_ALIASES.items():
        if any(alias in text for alias in aliases):
            return metro
    return None


def _is_country_only(text: str) -> bool:
    stripped = text
    for token in _COUNTRY_TOKENS:
        stripped = stripped.replace(token, " ")
    return not stripped.strip()


def location_matches(needle: str | None, offer_location: str | None) -> bool:
    """True when a location-pinned search should keep an offer located at
    `offer_location`. See the module docstring for the rules."""
    n = _norm(needle or "")
    if not n:
        return True
    o = _norm(offer_location or "")
    if not o:
        return True
    if n in o or o in n:
        return True

    n_metro = _resolve_metro(n)
    if n_metro is not None and n_metro == _resolve_metro(o):
        return True

    n_country = _METRO_COUNTRY.get(n_metro or "")
    return n_country is not None and _is_country_only(o) and n_country in o
