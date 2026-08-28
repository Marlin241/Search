import re

import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.keyword_matching import keyword_matches_title
from app.job_search.schemas import JobListing, SearchCriteria
from app.job_search.timestamps import parse_iso_datetime

_API_URL = "https://jobicy.com/api/v2/remote-jobs"
_COUNT = 50
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    return _TAG_RE.sub("", value or "").strip()


class JobicyClient:
    """Jobicy (jobicy.com/api/v2): remote-only job board, worldwide. Public
    API, no key. Every listing is remote, so this client contributes only
    when the search is remote-oriented: it returns nothing (without a
    network call) when the user pinned a location and did not ask for
    remote. Keyword filtering is client-side against the job title."""

    def __init__(self, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(timeout=10.0)

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        if not criteria.remote and (criteria.location or "").strip():
            return []

        try:
            response = self._http.get(
                _API_URL, params={"count": _COUNT, "tag": criteria.keywords}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(f"Jobicy: échec de la recherche: {exc}") from exc

        try:
            payload = response.json()
            listings: list[JobListing] = []
            for job in payload.get("jobs", []):
                title = job.get("jobTitle")
                url = job.get("url")
                if not title or not url:
                    continue
                if not keyword_matches_title(criteria.keywords, title):
                    continue
                salary = None
                smin, smax = job.get("salaryMin"), job.get("salaryMax")
                currency = job.get("salaryCurrency") or ""
                if smin and smax:
                    salary = f"{smin} - {smax} {currency}".strip()
                pub = (job.get("pubDate") or "").replace(" ", "T")
                listings.append(
                    JobListing(
                        title=title,
                        company=job.get("companyName", ""),
                        location=job.get("jobGeo") or "Remote",
                        snippet=_strip_html(job.get("jobDescription", ""))[:500],
                        url=url,
                        source="jobicy",
                        ats_type=None,
                        salary=salary,
                        posted_at=parse_iso_datetime(pub),
                    )
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobSearchSourceError("Jobicy: réponse invalide.") from exc

        return listings
