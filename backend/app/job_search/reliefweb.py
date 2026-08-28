import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria
from app.job_search.timestamps import parse_iso_datetime

_API_URL = "https://api.reliefweb.int/v1/jobs"
_LIMIT = 20
_INCLUDE_FIELDS = (
    "title",
    "url",
    "url_alias",
    "source.name",
    "country.name",
    "city.name",
    "date.created",
    "body",
)


class ReliefWebClient:
    """ReliefWeb (api.reliefweb.int): humanitarian / NGO job postings, with
    strong coverage of West and Central Africa. Public API, no key; an
    `appname` identifying the caller is expected. Keyword search is
    server-side (query[value]); results are restricted to a configured set
    of countries via a country.name filter."""

    def __init__(
        self,
        appname: str,
        countries: list[str],
        http_client: httpx.Client | None = None,
    ):
        self._appname = appname
        self._countries = countries
        self._http = http_client or httpx.Client(timeout=10.0)

    def _params(
        self, criteria: SearchCriteria
    ) -> list[tuple[str, str | int | float | bool | None]]:
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("appname", self._appname),
            ("profile", "list"),
            ("limit", str(_LIMIT)),
            ("query[value]", criteria.keywords),
            ("query[operator]", "AND"),
            ("filter[field]", "country.name"),
            ("filter[operator]", "OR"),
        ]
        for field_name in _INCLUDE_FIELDS:
            params.append(("fields[include][]", field_name))
        for country in self._countries:
            params.append(("filter[value][]", country))
        return params

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        try:
            response = self._http.get(_API_URL, params=self._params(criteria))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(
                f"ReliefWeb: échec de la recherche: {exc}"
            ) from exc

        try:
            payload = response.json()
            listings: list[JobListing] = []
            for entry in payload.get("data", []):
                fields = entry.get("fields") or {}
                title = fields.get("title")
                url = fields.get("url_alias") or fields.get("url")
                if not title or not url:
                    continue
                sources = fields.get("source") or []
                company = sources[0].get("name", "") if sources else ""
                countries = [c.get("name") for c in (fields.get("country") or [])]
                cities = [c.get("name") for c in (fields.get("city") or [])]
                location = (
                    ", ".join(part for part in [*cities[:1], *countries[:1]] if part)
                    or None
                )
                created = (fields.get("date") or {}).get("created")
                listings.append(
                    JobListing(
                        title=title,
                        company=company,
                        location=location,
                        snippet=(fields.get("body") or "")[:500],
                        url=url,
                        source="reliefweb",
                        ats_type=None,
                        posted_at=parse_iso_datetime(created),
                    )
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobSearchSourceError("ReliefWeb: réponse invalide.") from exc

        return listings
