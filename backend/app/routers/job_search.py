from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import database
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.job_search.aggregator import search_jobs
from app.job_search.background_discovery import create_pending_search, get_discovery_result, run_discovery
from app.job_search.company_cache import get_cached_mapping
from app.job_search.dependencies import get_job_search_clients
from app.job_search.discovery import MAX_COMPANIES_PER_DISCOVERY, extract_unique_companies
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria
from app.models.job_search_request_log import JobSearchRequestLog
from app.models.user import User
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_job_search_rate_limit,
    lock_user_for_rate_limit,
)
from app.schemas.job_search import JobSearchDiscoveryResponse, JobSearchResponse

router = APIRouter(prefix="/job-search", tags=["job_search"])


def _fetch_known_company_listings(
    clients: dict[str, object], criteria: SearchCriteria, source: str, slug: str
) -> list[JobListing]:
    client = clients[source]
    try:
        return client.search(criteria, [slug])
    except JobSearchSourceError:
        return []


@router.post("/search", response_model=JobSearchResponse)
def search(
    criteria: SearchCriteria,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clients: dict[str, object] = Depends(get_job_search_clients),
) -> JobSearchResponse:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_job_search_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    primary_clients = {"france_travail": clients["france_travail"], "adzuna": clients["adzuna"]}
    listings, unavailable_sources = search_jobs(criteria, primary_clients)

    db.add(JobSearchRequestLog(user_id=current_user.id))
    db.commit()

    known_listings: list[JobListing] = []
    unknown_companies: list[str] = []
    for company_name in extract_unique_companies(listings):
        mapping = get_cached_mapping(db, company_name)
        if mapping is None:
            unknown_companies.append(company_name)
        elif mapping.source is not None:
            known_listings.extend(
                _fetch_known_company_listings(clients, criteria, mapping.source, mapping.slug)
            )

    unknown_companies = unknown_companies[:MAX_COMPANIES_PER_DISCOVERY]
    search_id = create_pending_search(current_user.id, has_unknown_companies=bool(unknown_companies))
    if unknown_companies:
        background_tasks.add_task(
            run_discovery,
            search_id,
            # Looked up as database.SessionLocal (not a bare `SessionLocal` name
            # imported at module load) so the test suite's monkeypatch of
            # database.SessionLocal (see tests/conftest.py) takes effect. This
            # attribute access happens now, while handling the request (after
            # any test monkeypatch has already been applied), not at module
            # import time.
            database.SessionLocal,
            unknown_companies,
            criteria,
            clients["greenhouse"],
            clients["lever"],
        )

    return JobSearchResponse(
        listings=listings + known_listings,
        unavailable_sources=unavailable_sources,
        search_id=search_id,
        discovery_pending=bool(unknown_companies),
    )


@router.get("/search/{search_id}/discovery", response_model=JobSearchDiscoveryResponse)
def get_discovery(
    search_id: str,
    current_user: User = Depends(get_current_user),
) -> JobSearchDiscoveryResponse:
    done, new_listings = get_discovery_result(search_id, current_user.id)
    return JobSearchDiscoveryResponse(done=done, new_listings=new_listings)
