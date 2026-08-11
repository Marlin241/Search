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
