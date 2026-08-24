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
