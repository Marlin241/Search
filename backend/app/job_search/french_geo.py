"""Shared geocoding against geo.api.gouv.fr for the France-only sources.

France Travail and La Bonne Alternance only cover France, and their APIs
take a French commune code / coordinates rather than a free-text place
name. This helper resolves a place name against the official French commune
registry and, crucially, distinguishes three outcomes so the callers can
tell "this is a place outside France" (return nothing - dumping every
nationwide French offer into, say, a Dakar search is worse than useless)
from "the geocoder is down" (fail open, keep the previous behaviour).
"""

import unicodedata

import httpx

COMMUNES_URL = "https://geo.api.gouv.fr/communes"
NATIONWIDE_LOCATIONS = {"france"}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return (
        "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()
    )


class GeoLookupUnavailable(Exception):
    """The geocoding service could not be reached or returned junk - the
    caller cannot conclude anything about whether the location is French."""


class NotAFrenchPlace(Exception):
    """The geocoder responded but knows no commune by this name - the
    location is (probably) outside France. A France-only source should
    return no results rather than fall back to nationwide."""


def lookup_commune(
    location: str, http_client: httpx.Client, *, fields: str
) -> dict | None:
    """Return the top matching French commune record (with `fields`
    populated), or None when the registry has no commune whose name
    actually matches `location`. Raises GeoLookupUnavailable on a
    transport/parse error.

    The `nom` search on geo.api.gouv.fr is fuzzy - "Thiès" (Senegal) comes
    back as "Thiescourt" (Oise). We keep a result only if the returned
    commune name and the query share a whole word once accents/case are
    stripped, so a genuine place outside France resolves to None.
    """
    try:
        response = http_client.get(
            COMMUNES_URL,
            params={
                "nom": location,
                "fields": f"{fields},nom" if "nom" not in fields else fields,
                "boost": "population",
                "limit": 1,
            },
        )
        response.raise_for_status()
        results = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GeoLookupUnavailable(str(exc)) from exc

    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None

    query_words = set(_normalize(location).split())
    name_words = set(_normalize(str(first.get("nom", ""))).split())
    if not query_words & name_words:
        return None
    return first
