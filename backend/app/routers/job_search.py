from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.job_search.aggregator import search_jobs
from app.job_search.dependencies import get_job_search_clients
from app.job_search.schemas import SearchCriteria
from app.models.job_search_request_log import JobSearchRequestLog
from app.models.user import User
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_job_search_rate_limit,
    lock_user_for_rate_limit,
)
from app.schemas.job_search import JobSearchResponse

router = APIRouter(prefix="/job-search", tags=["job_search"])


@router.post("/search", response_model=JobSearchResponse)
def search(
    criteria: SearchCriteria,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clients: dict[str, object] = Depends(get_job_search_clients),
) -> JobSearchResponse:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_job_search_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    listings, unavailable_sources = search_jobs(criteria, clients)

    db.add(JobSearchRequestLog(user_id=current_user.id))
    db.commit()

    return JobSearchResponse(listings=listings, unavailable_sources=unavailable_sources)
