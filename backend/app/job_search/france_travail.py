import re

import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.french_geo import (
    NATIONWIDE_LOCATIONS,
    GeoLookupUnavailable,
    NotAFrenchPlace,
    lookup_commune,
)
from app.job_search.schemas import JobListing, SearchCriteria
from app.job_search.timestamps import parse_iso_datetime

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

_INSEE_CODE_RE = re.compile(r"^\d{5}$")

# France Travail's typeContrat referential only recognizes these codes; a
# value it doesn't recognize (e.g. "alternance", "stage") makes the whole
# search request fail with a 400, which takes the entire source down rather
# than just narrowing results. Contract types outside this map (apprenticeship
# offers are better served by La Bonne Alternance anyway, and are filtered
# back out client-side by the aggregator - see aggregator.py) are simply left
# unfiltered on this source instead of being sent through as an unrecognized
# code. Keys are the values the frontend's contract-type dropdown sends.
_CONTRACT_TYPE_CODES = {"cdi": "CDI", "cdd": "CDD", "interim": "MIS", "sai": "SAI"}


class FranceTravailClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        http_client: httpx.Client | None = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http_client or httpx.Client(timeout=10.0)

    def _get_access_token(self) -> str:
        try:
            response = self._http.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": "api_offresdemploiv2 o2dsoffre",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(
                f"France Travail: échec de l'authentification: {exc}"
            ) from exc

        try:
            return response.json()["access_token"]
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobSearchSourceError(
                "France Travail: réponse d'authentification invalide."
            ) from exc

    def _resolve_commune_code(self, location: str) -> str | None:
        # The France Travail API only accepts INSEE commune codes, not free-text
        # place names. Returns None for a nationwide search ("France"/empty) or
        # when the geocoder is unreachable (fail open). Raises NotAFrenchPlace
        # when the geocoder responds but knows no such commune - the caller
        # turns that into an empty result set, since France Travail is
        # France-only and a real place elsewhere (e.g. "Dakar") should yield
        # nothing here rather than every nationwide French offer.
        location = location.strip()
        if not location or location.casefold() in NATIONWIDE_LOCATIONS:
            return None
        if _INSEE_CODE_RE.match(location):
            return location

        try:
            commune = lookup_commune(location, self._http, fields="code")
        except GeoLookupUnavailable:
            return None
        if commune is None:
            raise NotAFrenchPlace(location)
        return commune.get("code")

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        # No token caching in this version: search is on-demand and
        # rate-limited (Task 9), so re-authenticating on every call trades a
        # small amount of latency for not having to manage token expiry.
        token = self._get_access_token()

        params: dict[str, str] = {"motsCles": criteria.keywords}
        if criteria.location:
            try:
                commune_code = self._resolve_commune_code(criteria.location)
            except NotAFrenchPlace:
                return []
            if commune_code:
                params["commune"] = commune_code
        if criteria.contract_type:
            code = _CONTRACT_TYPE_CODES.get(criteria.contract_type.strip().lower())
            if code:
                params["typeContrat"] = code

        try:
            response = self._http.get(
                SEARCH_URL, params=params, headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(
                f"France Travail: échec de la recherche: {exc}"
            ) from exc

        try:
            payload = response.json()
            listings = []
            for offre in payload.get("resultats", []):
                salary_data = offre.get("salaire") or {}
                salary_parts = []
                if salary_data.get("libelle"):
                    salary_parts.append(salary_data["libelle"])
                if salary_data.get("complement1"):
                    salary_parts.append(salary_data["complement1"])
                salary_str = " - ".join(salary_parts) if salary_parts else None

                listings.append(
                    JobListing(
                        title=offre.get("intitule", ""),
                        company=(offre.get("entreprise") or {}).get("nom", ""),
                        location=(offre.get("lieuTravail") or {}).get("libelle"),
                        snippet=offre.get("description") or "",
                        url=(offre.get("origineOffre") or {}).get("urlOrigine", ""),
                        source="france_travail",
                        ats_type=None,
                        salary=salary_str,
                        posted_at=parse_iso_datetime(offre.get("dateCreation")),
                    )
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobSearchSourceError("France Travail: réponse invalide.") from exc

        return listings
