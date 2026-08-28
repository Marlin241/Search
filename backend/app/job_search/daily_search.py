import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.job_search.aggregator import search_jobs
from app.job_search.company_cache import get_cached_mapping, save_mapping
from app.job_search.dependencies import get_job_search_clients
from app.job_search.discovery import detect_company_ats, extract_unique_companies
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import (
    JobListing,
    SearchClient,
    SearchCriteria,
    SluggableSearchClient,
)
from app.job_search.seed_companies import cache_known_seed_mappings, get_seed_companies
from app.job_search.unsubscribe import create_unsubscribe_token
from app.models.notified_listing import NotifiedListing
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.notifications.resend_client import EmailSendError, send_daily_digest_email

logger = logging.getLogger(__name__)

NOTIFICATION_HOUR = 8


def _is_notification_time(saved_search: SavedSearch, now: datetime) -> bool:
    return now.astimezone(ZoneInfo(saved_search.timezone)).hour == NOTIFICATION_HOUR


def _resolve_and_fetch_known_companies(
    db: Session,
    criteria: SearchCriteria,
    candidate_companies: list[str],
    clients: dict[str, object],
    http_client: httpx.Client,
) -> list[JobListing]:
    known_listings: list[JobListing] = []
    for company_name in candidate_companies:
        mapping = get_cached_mapping(db, company_name)
        if mapping is None:
            result = detect_company_ats(company_name, http_client)
            if not result.confirmed:
                continue
            save_mapping(db, company_name, result.source, result.slug)
            if result.source is None:
                continue
            assert (
                result.slug is not None
            )  # DetectionResult always sets slug alongside source
            source, slug = result.source, result.slug
        elif mapping.source is not None:
            assert (
                mapping.slug is not None
            )  # CompanyAtsMapping always sets slug alongside source
            source, slug = mapping.source, mapping.slug
        else:
            continue

        client = cast(SluggableSearchClient, clients[source])
        try:
            known_listings.extend(client.search(criteria, [slug]))
        except JobSearchSourceError:
            continue
    return known_listings


def _process_saved_search(
    db: Session, saved_search: SavedSearch, clients: dict[str, object]
) -> None:
    criteria = SearchCriteria(
        keywords=saved_search.keywords,
        location=saved_search.location,
        contract_type=saved_search.contract_type,
        remote=saved_search.remote,
        exclude_keywords=saved_search.exclude_keywords,
    )
    primary_clients: dict[str, SearchClient] = {
        "france_travail": cast(SearchClient, clients["france_travail"]),
        "adzuna": cast(SearchClient, clients["adzuna"]),
        "la_bonne_alternance": cast(SearchClient, clients["la_bonne_alternance"]),
        "reliefweb": cast(SearchClient, clients["reliefweb"]),
        "jobicy": cast(SearchClient, clients["jobicy"]),
        "weworkremotely": cast(SearchClient, clients["weworkremotely"]),
        "ngojobs": cast(SearchClient, clients["ngojobs"]),
        "crawled": cast(SearchClient, clients["crawled"]),
    }
    listings, _unavailable_sources = search_jobs(criteria, primary_clients)

    cache_known_seed_mappings(db, criteria.location)
    candidate_companies = list(
        dict.fromkeys(
            extract_unique_companies(listings) + get_seed_companies(criteria.location)
        )
    )

    http_client = httpx.Client(timeout=10.0)
    try:
        known_listings = _resolve_and_fetch_known_companies(
            db, criteria, candidate_companies, clients, http_client
        )
    finally:
        http_client.close()

    all_listings = listings + known_listings
    already_notified = {
        row.offer_url
        for row in db.query(NotifiedListing)
        .filter(NotifiedListing.user_id == saved_search.user_id)
        .all()
    }
    new_listings = [
        listing for listing in all_listings if listing.url not in already_notified
    ]
    if not new_listings:
        return

    user = db.get(User, saved_search.user_id)
    if user is None:
        return

    token = create_unsubscribe_token(user.id)
    try:
        send_daily_digest_email(user.email, new_listings, token)
    except EmailSendError:
        logger.error(
            "Échec de l'envoi de l'email quotidien pour l'utilisateur %s",
            user.id,
        )
        return

    for listing in new_listings:
        db.add(NotifiedListing(user_id=saved_search.user_id, offer_url=listing.url))
    db.commit()


def run_daily_search(db_session_factory: Callable[[], Session]) -> None:
    db = db_session_factory()
    try:
        clients = get_job_search_clients()
        now = datetime.now(UTC)
        saved_searches = (
            db.query(SavedSearch).filter(SavedSearch.enabled.is_(True)).all()
        )
        for saved_search in saved_searches:
            if not _is_notification_time(saved_search, now):
                continue
            try:
                _process_saved_search(db, saved_search, clients)
            except Exception:
                # Isolation volontairement large (pas une exception métier
                # précise) : une panne inattendue pour un utilisateur (bug,
                # erreur réseau, erreur DB) ne doit jamais empêcher le
                # traitement des autres utilisateurs de ce passage horaire.
                logger.exception(
                    "Échec du traitement de la recherche sauvegardée pour "
                    "l'utilisateur %s",
                    saved_search.user_id,
                )
    finally:
        db.close()
