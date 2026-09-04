from collections.abc import Callable

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import database
from app.job_search.errors import JobSearchSourceError
from app.job_search.keyword_matching import keyword_matches_title
from app.job_search.location_matching import location_matches
from app.job_search.schemas import JobListing, SearchCriteria
from app.models.crawled_listing import CrawledListing

_RESULT_LIMIT = 50


class CrawledListingClient:
    """Reads crawled_listing (populated by crawl_runner) as a job-search
    source. Same SearchClient shape as the live source clients, so the
    aggregator merges and scores its results with no special-casing.

    The exact filters (is_active, contract_type, remote) run in SQL; the
    text filters (keywords, location) run in Python. Keywords are matched
    against the offer title with the same accent-insensitive, synonym-aware
    helper the other title-matching sources use (so "développeur" also
    finds "Developer"); location matching (app.job_search.location_matching)
    is accent-insensitive and metro-aware, so a "Dakar" search also keeps an
    offer posted in a Dakar neighbourhood or at country level. The candidate
    set is bounded by the number of active crawled rows (a few thousand at
    most), so the in-memory pass is cheap.
    """

    def __init__(self, session_factory: Callable[[], Session] | None = None):
        self._session_factory = session_factory or database.SessionLocal

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        pinned_location = (criteria.location or "").strip() or None

        session = self._session_factory()
        try:
            query = session.query(CrawledListing).filter(
                CrawledListing.is_active.is_(True)
            )
            if criteria.contract_type:
                query = query.filter(
                    func.lower(CrawledListing.contract_type).like(
                        f"%{criteria.contract_type.lower()}%"
                    )
                )
            if criteria.remote:
                query = query.filter(CrawledListing.is_remote.is_(True))
            rows = query.order_by(
                func.coalesce(
                    CrawledListing.posted_at, CrawledListing.first_seen_at
                ).desc()
            ).all()
        except SQLAlchemyError as exc:
            raise JobSearchSourceError(f"crawled_listing: {exc}") from exc
        finally:
            session.close()

        listings: list[JobListing] = []
        for row in rows:
            if not keyword_matches_title(criteria.keywords, row.title):
                continue
            if not location_matches(pinned_location, row.location):
                continue
            listings.append(
                JobListing(
                    title=row.title,
                    company=row.company or "",
                    location=row.location,
                    snippet=row.snippet,
                    url=row.url,
                    source=row.source,
                    ats_type=None,
                    salary=row.salary,
                    posted_at=row.posted_at,
                    is_remote=row.is_remote,
                )
            )
            if len(listings) >= _RESULT_LIMIT:
                break
        return listings
