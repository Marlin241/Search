from pydantic import BaseModel

from app.job_search.schemas import JobListing


class JobSearchResponse(BaseModel):
    listings: list[JobListing]
    unavailable_sources: list[str]
    search_id: str
    discovery_pending: bool


class JobSearchDiscoveryResponse(BaseModel):
    done: bool
    new_listings: list[JobListing]
