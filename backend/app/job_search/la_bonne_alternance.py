import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.french_geo import (
    NATIONWIDE_LOCATIONS,
    GeoLookupUnavailable,
    NotAFrenchPlace,
    lookup_commune,
)
from app.job_search.keyword_matching import keyword_matches_title
from app.job_search.schemas import JobListing, SearchCriteria

SEARCH_URL = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"

_DEFAULT_RADIUS_KM = 30


class LaBonneAlternanceClient:
    """La Bonne Alternance (api.apprentissage.beta.gouv.fr): apprenticeship
    ("alternance") job offers in France. Like France Travail, this is a
    France-scoped public API - it has no reach outside France. Unlike France
    Travail, the search endpoint takes no free-text keyword parameter (only
    geo/ROME/RNCP/diploma filters), so keyword matching is done client-side
    against each offer's title, same as the Greenhouse/Lever clients."""

    def __init__(self, api_key: str, http_client: httpx.Client | None = None):
        self._api_key = api_key
        self._http = http_client or httpx.Client(timeout=10.0)

    def _resolve_coordinates(self, location: str) -> tuple[float, float] | None:
        # Returns None for a nationwide search or an unreachable geocoder
        # (fail open); raises NotAFrenchPlace when the geocoder knows no such
        # commune, so search() can return nothing rather than nationwide
        # French apprenticeships for, say, a Dakar search.
        location = location.strip()
        if not location or location.casefold() in NATIONWIDE_LOCATIONS:
            return None

        try:
            commune = lookup_commune(location, self._http, fields="centre")
        except GeoLookupUnavailable:
            return None
        if commune is None:
            raise NotAFrenchPlace(location)

        coordinates = (commune.get("centre") or {}).get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) != 2:
            return None
        longitude, latitude = coordinates
        return longitude, latitude

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        params: dict[str, str | float | int] = {}
        if criteria.location:
            try:
                coordinates = self._resolve_coordinates(criteria.location)
            except NotAFrenchPlace:
                return []
            if coordinates:
                longitude, latitude = coordinates
                params["longitude"] = longitude
                params["latitude"] = latitude
                params["radius"] = _DEFAULT_RADIUS_KM

        try:
            response = self._http.get(
                SEARCH_URL,
                params=params,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(
                f"La Bonne Alternance: échec de la recherche: {exc}"
            ) from exc

        try:
            payload = response.json()
            listings = []
            for job in payload.get("jobs", []):
                offer = job.get("offer") or {}
                title = offer.get("title", "")
                if not keyword_matches_title(criteria.keywords, title):
                    continue
                workplace = job.get("workplace") or {}
                apply_ = job.get("apply") or {}
                salary_data = offer.get("salary") or {}
                salary_str = salary_data.get("label") or None
                listings.append(
                    JobListing(
                        title=title,
                        company=workplace.get("name")
                        or workplace.get("legal_name")
                        or "",
                        location=(workplace.get("location") or {}).get("address"),
                        snippet=offer.get("description") or "",
                        url=apply_.get("url", ""),
                        source="la_bonne_alternance",
                        ats_type=None,
                        salary=salary_str,
                    )
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobSearchSourceError(
                "La Bonne Alternance: réponse invalide."
            ) from exc

        return listings
