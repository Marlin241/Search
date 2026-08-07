import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria

TOKEN_URL = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


class FranceTravailClient:
    def __init__(self, client_id: str, client_secret: str, http_client: httpx.Client | None = None):
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
            raise JobSearchSourceError(f"France Travail: échec de l'authentification: {exc}") from exc

        try:
            return response.json()["access_token"]
        except (ValueError, KeyError) as exc:
            raise JobSearchSourceError("France Travail: réponse d'authentification invalide.") from exc

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        # No token caching in this version: search is on-demand and
        # rate-limited (Task 9), so re-authenticating on every call trades a
        # small amount of latency for not having to manage token expiry.
        token = self._get_access_token()

        params: dict[str, str] = {"motsCles": criteria.keywords}
        if criteria.location:
            params["commune"] = criteria.location
        if criteria.contract_type:
            params["typeContrat"] = criteria.contract_type

        try:
            response = self._http.get(SEARCH_URL, params=params, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(f"France Travail: échec de la recherche: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise JobSearchSourceError("France Travail: réponse invalide (pas du JSON).") from exc

        return [
            JobListing(
                title=offre.get("intitule", ""),
                company=(offre.get("entreprise") or {}).get("nom", ""),
                location=(offre.get("lieuTravail") or {}).get("libelle"),
                snippet=(offre.get("description") or "")[:500],
                url=(offre.get("origineOffre") or {}).get("urlOrigine", ""),
                source="france_travail",
                ats_type=None,
            )
            for offre in payload.get("resultats", [])
        ]
