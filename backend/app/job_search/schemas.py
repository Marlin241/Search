from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class SearchCriteria(BaseModel):
    keywords: str
    location: str | None = None
    contract_type: str | None = None
    remote: bool | None = None
    exclude_keywords: list[str] = []


class JobListing(BaseModel):
    title: str
    company: str
    location: str | None
    snippet: str
    url: str
    source: str
    ats_type: str | None
    salary: str | None = None
    posted_at: datetime | None = None
    # Set by remote-only source clients; for every other source the
    # aggregator fills it from app.job_search.remote_signals right after the
    # merge. Defaults to False so no adapter is forced to pass it.
    is_remote: bool = False
    # Overwritten by the /job-search/search endpoint before the response is
    # returned (see app.job_search.compatibility.score_listing); defaults to
    # 0 here only so adapters that don't score listings themselves (all of
    # them) don't need to pass it.
    compatibility_score: int = 0


class SearchClient(Protocol):
    """Structural type for the France Travail/Adzuna/La Bonne Alternance
    clients: single-criteria search, no company slug."""

    def search(self, criteria: SearchCriteria) -> list[JobListing]: ...


class SluggableSearchClient(Protocol):
    """Structural type for the Greenhouse/Lever clients: search scoped to a
    specific set of company slugs."""

    def search(
        self, criteria: SearchCriteria, company_slugs: list[str]
    ) -> list[JobListing]: ...
