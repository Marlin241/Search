import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria
from app.job_search.timestamps import parse_iso_datetime

# Code pays Adzuna (voir self._country) -> devise ISO 4217 du salaire retourné
# par l'API. Limité aux pays effectivement configurables aujourd'hui ;
# étendre au besoin si d'autres pays Adzuna sont activés.
_COUNTRY_CURRENCIES = {
    "fr": "EUR",
    "de": "EUR",
    "es": "EUR",
    "it": "EUR",
    "nl": "EUR",
    "at": "EUR",
    "gb": "GBP",
    "us": "USD",
    "ca": "CAD",
    "au": "AUD",
}


class AdzunaClient:
    def __init__(
        self,
        app_id: str,
        app_key: str,
        country: str = "fr",
        http_client: httpx.Client | None = None,
    ):
        self._app_id = app_id
        self._app_key = app_key
        self._country = country
        self._http = http_client or httpx.Client(timeout=10.0)

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        url = f"https://api.adzuna.com/v1/api/jobs/{self._country}/search/1"
        params = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "what": criteria.keywords,
            "content-type": "application/json",
        }
        if criteria.location:
            params["where"] = criteria.location

        try:
            response = self._http.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(f"Adzuna: échec de la recherche: {exc}") from exc

        try:
            payload = response.json()
            listings = []
            currency = _COUNTRY_CURRENCIES.get(self._country.lower())
            currency_label = f" {currency}" if currency else ""
            for result in payload.get("results", []):
                salary_min = result.get("salary_min")
                salary_max = result.get("salary_max")
                salary_str = None
                if salary_min and salary_max:
                    salary_str = (
                        f"{int(salary_min):,} - {int(salary_max):,}{currency_label} / an"
                    ).replace(",", " ")
                elif salary_min:
                    salary_str = (
                        f"À partir de {int(salary_min):,}{currency_label} / an"
                    ).replace(",", " ")
                elif salary_max:
                    salary_str = (
                        f"Jusqu'à {int(salary_max):,}{currency_label} / an"
                    ).replace(",", " ")

                listings.append(
                    JobListing(
                        title=result.get("title", ""),
                        company=(result.get("company") or {}).get("display_name", ""),
                        location=(result.get("location") or {}).get("display_name"),
                        snippet=result.get("description") or "",
                        url=result.get("redirect_url", ""),
                        source="adzuna",
                        ats_type=None,
                        salary=salary_str,
                        salary_currency=currency if salary_str else None,
                        posted_at=parse_iso_datetime(result.get("created")),
                    )
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobSearchSourceError("Adzuna: réponse invalide.") from exc

        return listings
