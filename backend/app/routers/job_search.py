from typing import cast
from zoneinfo import available_timezones

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app import database
from app.auth.dependencies import get_current_user
from app.compatibility.analyzer import (
    CompatibilityAnalysisError,
    CompatibilityDetailAnalyzer,
)
from app.compatibility.dependencies import get_compatibility_detail_analyzer
from app.database import get_db
from app.job_search import search_cache
from app.job_search.aggregator import search_jobs
from app.job_search.background_discovery import (
    create_pending_search,
    get_discovery_result,
    run_discovery,
)
from app.job_search.company_cache import get_cached_mapping
from app.job_search.compatibility import score_breakdown, score_listing
from app.job_search.dependencies import get_job_search_clients
from app.job_search.discovery import (
    MAX_COMPANIES_PER_DISCOVERY,
    extract_unique_companies,
)
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import (
    JobListing,
    SearchClient,
    SearchCriteria,
    SluggableSearchClient,
)
from app.job_search.seed_companies import cache_known_seed_mappings, get_seed_companies
from app.job_search.unsubscribe import (
    InvalidUnsubscribeTokenError,
    verify_unsubscribe_token,
)
from app.models.candidate_profile import CandidateProfile
from app.models.compatibility_request_log import CompatibilityRequestLog
from app.models.job_search_request_log import JobSearchRequestLog
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_compatibility_detail_rate_limit,
    check_job_search_rate_limit,
    lock_user_for_rate_limit,
)
from app.schemas.compatibility import (
    CompatibilityDetailIn,
    CompatibilityDetailOut,
    CompatibilityScoreBreakdown,
)
from app.schemas.job_search import (
    JobSearchDiscoveryResponse,
    JobSearchResponse,
    SavedSearchIn,
    SavedSearchOut,
)

router = APIRouter(prefix="/job-search", tags=["job_search"])


def _fetch_known_company_listings(
    clients: dict[str, object], criteria: SearchCriteria, source: str, slug: str
) -> list[JobListing]:
    client = cast(SluggableSearchClient, clients[source])
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
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc

    primary_clients: dict[str, SearchClient] = {
        "france_travail": cast(SearchClient, clients["france_travail"]),
        "adzuna": cast(SearchClient, clients["adzuna"]),
        "la_bonne_alternance": cast(SearchClient, clients["la_bonne_alternance"]),
        "reliefweb": cast(SearchClient, clients["reliefweb"]),
        "jobicy": cast(SearchClient, clients["jobicy"]),
        "weworkremotely": cast(SearchClient, clients["weworkremotely"]),
        "remoteok": cast(SearchClient, clients["remoteok"]),
        "ngojobs": cast(SearchClient, clients["ngojobs"]),
    }
    # Upstream results for a given set of criteria don't depend on who's
    # asking, so a cache hit here skips France Travail/Adzuna/La Bonne
    # Alternance entirely for repeat/near-repeat searches within the TTL.
    # The per-user quota below still counts every request regardless -
    # it's an abuse guard, not a proxy for upstream cost.
    cache_key = search_cache.build_cache_key(criteria)
    cached = search_cache.get(cache_key)
    if cached is not None:
        listings, unavailable_sources = cached
    else:
        listings, unavailable_sources = search_jobs(criteria, primary_clients)
        search_cache.set(cache_key, listings, unavailable_sources)

    db.add(JobSearchRequestLog(user_id=current_user.id))
    db.commit()

    cache_known_seed_mappings(db, criteria.location)
    candidate_companies = list(
        dict.fromkeys(
            extract_unique_companies(listings) + get_seed_companies(criteria.location)
        )
    )

    known_listings: list[JobListing] = []
    unknown_companies: list[str] = []
    for company_name in candidate_companies:
        mapping = get_cached_mapping(db, company_name)
        if mapping is None:
            unknown_companies.append(company_name)
        elif mapping.source is not None:
            assert (
                mapping.slug is not None
            )  # CompanyAtsMapping always sets slug alongside source
            known_listings.extend(
                _fetch_known_company_listings(
                    clients, criteria, mapping.source, mapping.slug
                )
            )

    unknown_companies = unknown_companies[:MAX_COMPANIES_PER_DISCOVERY]
    search_id = create_pending_search(
        current_user.id, has_unknown_companies=bool(unknown_companies)
    )
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
            cast(SluggableSearchClient, clients["greenhouse"]),
            cast(SluggableSearchClient, clients["lever"]),
        )

    all_listings = listings + known_listings
    profile = (
        db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == current_user.id)
        .first()
    )
    for job_listing in all_listings:
        job_listing.compatibility_score = score_listing(job_listing, profile)
    all_listings.sort(key=lambda listing: listing.compatibility_score, reverse=True)

    return JobSearchResponse(
        listings=all_listings,
        unavailable_sources=unavailable_sources,
        search_id=search_id,
        discovery_pending=bool(unknown_companies),
    )


@router.post("/compatibility-detail", response_model=CompatibilityDetailOut)
def get_compatibility_detail(
    payload: CompatibilityDetailIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analyzer: CompatibilityDetailAnalyzer = Depends(get_compatibility_detail_analyzer),
) -> CompatibilityDetailOut:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_compatibility_detail_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc

    profile = (
        db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == current_user.id)
        .first()
    )
    if profile is None or not profile.cv_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Un CV est nécessaire pour obtenir le détail de compatibilité.",
        )

    breakdown = score_breakdown(payload.listing, profile)
    offer_text = (
        f"{payload.listing.title}\n{payload.listing.company}\n{payload.listing.snippet}"
    )

    try:
        detail = analyzer.analyze(profile.cv_text, offer_text, breakdown)
    except CompatibilityAnalysisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    db.add(CompatibilityRequestLog(user_id=current_user.id))
    db.commit()

    return CompatibilityDetailOut(
        breakdown=CompatibilityScoreBreakdown(**breakdown),
        summary=detail.summary,
        strengths=detail.strengths,
        concerns=detail.concerns,
    )


@router.get("/search/{search_id}/discovery", response_model=JobSearchDiscoveryResponse)
def get_discovery(
    search_id: str,
    current_user: User = Depends(get_current_user),
) -> JobSearchDiscoveryResponse:
    done, new_listings = get_discovery_result(search_id, current_user.id)
    return JobSearchDiscoveryResponse(done=done, new_listings=new_listings)


def _to_saved_search_out(saved_search: SavedSearch) -> SavedSearchOut:
    return SavedSearchOut(
        keywords=saved_search.keywords,
        location=saved_search.location,
        contract_type=saved_search.contract_type,
        remote=saved_search.remote,
        exclude_keywords=saved_search.exclude_keywords,
        timezone=saved_search.timezone,
        enabled=saved_search.enabled,
    )


@router.get("/saved-search", response_model=SavedSearchOut)
def get_saved_search(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchOut:
    saved_search = (
        db.query(SavedSearch).filter(SavedSearch.user_id == current_user.id).first()
    )
    if saved_search is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune recherche sauvegardée.",
        )
    return _to_saved_search_out(saved_search)


@router.put("/saved-search", response_model=SavedSearchOut)
def put_saved_search(
    payload: SavedSearchIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchOut:
    if payload.timezone not in available_timezones():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fuseau horaire invalide.",
        )

    saved_search = (
        db.query(SavedSearch).filter(SavedSearch.user_id == current_user.id).first()
    )
    if saved_search is None:
        saved_search = SavedSearch(user_id=current_user.id)
        db.add(saved_search)

    saved_search.keywords = payload.keywords
    saved_search.location = payload.location
    saved_search.contract_type = payload.contract_type
    saved_search.remote = payload.remote
    saved_search.exclude_keywords = payload.exclude_keywords
    saved_search.timezone = payload.timezone
    saved_search.enabled = payload.enabled
    db.commit()
    db.refresh(saved_search)
    return _to_saved_search_out(saved_search)


@router.get("/saved-search/unsubscribe", response_class=HTMLResponse)
def unsubscribe_saved_search(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    # GET (not POST) is deliberate: this link is clicked directly from an
    # email client, with no form/JS available to issue a POST. The tradeoff
    # (an email link-scanner could pre-fetch and trigger it) is accepted
    # because the side effect is low-consequence and reversible - just
    # SavedSearch.enabled = False, undone with one click in the app - and
    # the token itself (see unsubscribe.py) can only ever do this one
    # action, on a distinct signing key from login tokens. No-referrer is
    # set so the token in the URL can't leak via a Referer header if a
    # future revision of this page ever adds an outbound link.
    headers = {"Referrer-Policy": "no-referrer"}
    try:
        user_id = verify_unsubscribe_token(token)
    except InvalidUnsubscribeTokenError:
        return HTMLResponse(
            "<html><body><p>Ce lien de désabonnement n'est plus valide.</p></body></html>",
            status_code=400,
            headers=headers,
        )
    saved_search = db.query(SavedSearch).filter(SavedSearch.user_id == user_id).first()
    if saved_search is not None:
        saved_search.enabled = False
        db.commit()
    return HTMLResponse(
        "<html><body><p>Vous ne recevrez plus d'alertes email pour votre "
        "recherche sauvegardée.</p></body></html>",
        headers=headers,
    )
