import httpx
from bs4 import BeautifulSoup

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria


def _strip_html(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


class GreenhouseJobBoardClient:
    def __init__(self, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(timeout=10.0)

    def search(self, criteria: SearchCriteria, company_slugs: list[str]) -> list[JobListing]:
        listings: list[JobListing] = []
        keyword = criteria.keywords.lower()

        for company_slug in company_slugs:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
            try:
                response = self._http.get(url, params={"content": "true"})
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise JobSearchSourceError(f"Greenhouse ({company_slug}): échec de la recherche: {exc}") from exc

            try:
                payload = response.json()
                for job in payload.get("jobs", []):
                    title = job.get("title", "")
                    if keyword and keyword not in title.lower():
                        continue
                    listings.append(
                        JobListing(
                            title=title,
                            company=company_slug,
                            location=(job.get("location") or {}).get("name"),
                            snippet=_strip_html(job.get("content", ""))[:500],
                            url=job.get("absolute_url", ""),
                            source="greenhouse",
                            ats_type="greenhouse",
                        )
                    )
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                raise JobSearchSourceError(f"Greenhouse ({company_slug}): réponse invalide.") from exc

        return listings
