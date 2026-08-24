import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria


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
            for result in payload.get("results", []):
                salary_min = result.get("salary_min")
                salary_max = result.get("salary_max")
                salary_str = None
                if salary_min and salary_max:
                    salary_str = (
                        f"{int(salary_min):,} - {int(salary_max):,} € / an".replace(
                            ",", " "
                        )
                    )
                elif salary_min:
                    salary_str = f"À partir de {int(salary_min):,} € / an".replace(
                        ",", " "
                    )
                elif salary_max:
                    salary_str = f"Jusqu'à {int(salary_max):,} € / an".replace(",", " ")

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
                    )
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobSearchSourceError("Adzuna: réponse invalide.") from exc

        return listings
