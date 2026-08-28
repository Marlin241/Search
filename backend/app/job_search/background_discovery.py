import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.job_search.aggregator import finalize_and_filter
from app.job_search.company_cache import save_mapping
from app.job_search.discovery import detect_company_ats
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria, SluggableSearchClient
from app.utils.time import utcnow

_STATE_TTL = timedelta(minutes=5)


@dataclass
class _DiscoveryState:
    user_id: int
    done: bool
    new_listings: list[JobListing] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)


_lock = threading.Lock()
_state: dict[str, _DiscoveryState] = {}


def _purge_expired() -> None:
    cutoff = utcnow() - _STATE_TTL
    with _lock:
        expired = [
            search_id
            for search_id, entry in _state.items()
            if entry.created_at < cutoff
        ]
        for search_id in expired:
            del _state[search_id]


def create_pending_search(user_id: int, has_unknown_companies: bool) -> str:
    _purge_expired()
    search_id = secrets.token_urlsafe(16)
    with _lock:
        _state[search_id] = _DiscoveryState(
            user_id=user_id, done=not has_unknown_companies
        )
    return search_id


def get_discovery_result(search_id: str, user_id: int) -> tuple[bool, list[JobListing]]:
    _purge_expired()
    with _lock:
        entry = _state.get(search_id)
        if entry is None or entry.user_id != user_id:
            return True, []
        listings, entry.new_listings = entry.new_listings, []
        return entry.done, listings


def run_discovery(
    search_id: str,
    db_session_factory: Callable[[], Session],
    unknown_companies: list[str],
    criteria: SearchCriteria,
    greenhouse_client: SluggableSearchClient,
    lever_client: SluggableSearchClient,
) -> None:
    db = db_session_factory()
    http_client = httpx.Client(timeout=10.0)
    try:
        for company_name in unknown_companies:
            result = detect_company_ats(company_name, http_client)
            if not result.confirmed:
                continue

            save_mapping(db, company_name, result.source, result.slug)

            if result.source is None:
                continue
            assert (
                result.slug is not None
            )  # DetectionResult always sets slug alongside source

            client = (
                greenhouse_client if result.source == "greenhouse" else lever_client
            )
            try:
                listings = client.search(criteria, [result.slug])
            except JobSearchSourceError:
                continue

            # Same post-merge treatment the primary sources get in
            # search_jobs: is_remote finalized, remote / exclude / contract
            # filters applied.
            listings = finalize_and_filter(listings, criteria)

            if listings:
                with _lock:
                    entry = _state.get(search_id)
                    if entry is not None:
                        entry.new_listings.extend(listings)
    finally:
        http_client.close()
        db.close()
        with _lock:
            entry = _state.get(search_id)
            if entry is not None:
                entry.done = True
