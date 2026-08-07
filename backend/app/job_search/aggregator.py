from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria


def search_jobs(criteria: SearchCriteria, clients: dict[str, object]) -> tuple[list[JobListing], list[str]]:
    listings: list[JobListing] = []
    unavailable_sources: list[str] = []
    for source_name, source_client in clients.items():
        try:
            listings.extend(source_client.search(criteria))
        except JobSearchSourceError:
            unavailable_sources.append(source_name)
    return listings, unavailable_sources
