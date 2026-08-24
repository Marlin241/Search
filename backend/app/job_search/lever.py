import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.keyword_matching import keyword_matches_title
from app.job_search.schemas import JobListing, SearchCriteria


class LeverJobBoardClient:
    def __init__(self, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(timeout=10.0)

    def search(
        self, criteria: SearchCriteria, company_slugs: list[str]
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        keyword = criteria.keywords

        for company_slug in company_slugs:
            url = f"https://api.lever.co/v0/postings/{company_slug}"
            try:
                response = self._http.get(url, params={"mode": "json"})
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise JobSearchSourceError(
                    f"Lever ({company_slug}): échec de la recherche: {exc}"
                ) from exc

            try:
                postings = response.json()
                for posting in postings:
                    title = posting.get("text", "")
                    if not keyword_matches_title(keyword, title):
                        continue
                    categories = posting.get("categories") or {}
                    listings.append(
                        JobListing(
                            title=title,
                            company=company_slug,
                            location=categories.get("location"),
                            snippet=posting.get("descriptionPlain") or "",
                            url=posting.get("hostedUrl", ""),
                            source="lever",
                            ats_type="lever",
                            salary=None,
                        )
                    )
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                raise JobSearchSourceError(
                    f"Lever ({company_slug}): réponse invalide."
                ) from exc

        return listings
