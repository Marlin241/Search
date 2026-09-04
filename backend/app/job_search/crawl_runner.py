import logging
from collections.abc import Callable

import httpx
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.job_search.crawlers.base import CrawledListingData, Crawler, CrawlerConfig
from app.job_search.crawlers.educarriere import EducarriereCrawler
from app.job_search.crawlers.emploi_dakar import EmploiDakarCrawler
from app.job_search.crawlers.senjob import SenjobCrawler
from app.models.crawled_listing import CrawledListing
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

ENABLED_CRAWLER_REGISTRY: dict[str, Crawler] = {
    "emploi_dakar": EmploiDakarCrawler(),
    "senjob": SenjobCrawler(),
    "educarriere_ci": EducarriereCrawler(),
}

_BASE_URLS = {
    "emploi_dakar": "https://www.emploidakar.com",
    "senjob": "https://senjob.com/sn",
    "educarriere_ci": "https://emploi.educarriere.ci",
}


def _apply(
    db: Session,
    source: str,
    items: list[CrawledListingData],
    *,
    deactivate_after: int,
    suspicious_empty_threshold: int,
) -> dict[str, int]:
    counts = {"inserted": 0, "updated": 0, "deactivated": 0, "skipped_deactivation": 0}
    now = utcnow()
    seen_urls = {item.url for item in items}

    existing = {
        row.url: row
        for row in db.query(CrawledListing).filter(CrawledListing.source == source)
    }

    for item in items:
        row = existing.get(item.url)
        if row is None:
            db.add(
                CrawledListing(
                    url=item.url,
                    source=source,
                    title=item.title,
                    company=item.company,
                    location=item.location,
                    snippet=item.snippet,
                    salary=item.salary,
                    contract_type=item.contract_type,
                    is_remote=item.is_remote,
                    posted_at=item.posted_at,
                    first_seen_at=now,
                    last_seen_at=now,
                    missed_crawls=0,
                    is_active=True,
                )
            )
            counts["inserted"] += 1
        else:
            row.title = item.title
            row.company = item.company
            row.location = item.location
            row.snippet = item.snippet
            row.salary = item.salary
            row.contract_type = item.contract_type
            row.is_remote = item.is_remote
            row.posted_at = item.posted_at
            row.last_seen_at = now
            row.missed_crawls = 0
            row.is_active = True
            counts["updated"] += 1

    active_count = sum(1 for row in existing.values() if row.is_active)
    if not items and active_count > suspicious_empty_threshold:
        logger.warning(
            "%s: crawl returned 0 offers but %d active rows exist - skipping "
            "deactivation (selector likely broke)",
            source,
            active_count,
        )
        counts["skipped_deactivation"] = 1
    else:
        for url, row in existing.items():
            if url in seen_urls or not row.is_active:
                continue
            row.missed_crawls += 1
            if row.missed_crawls >= deactivate_after:
                row.is_active = False
                counts["deactivated"] += 1

    db.commit()
    return counts


def _config_for(source: str, settings: Settings) -> CrawlerConfig:
    user_agent = "ATSDiagnosticBot/1.0"
    if settings.crawler_contact_url:
        user_agent = f"ATSDiagnosticBot/1.0 (+{settings.crawler_contact_url})"
    return CrawlerConfig(
        source=source,
        base_url=_BASE_URLS[source],
        max_offers=settings.crawl_max_offers_per_site,
        request_delay_seconds=settings.crawl_request_delay_seconds,
        user_agent=user_agent,
    )


def run_crawl(db_session_factory: Callable[[], Session]) -> None:
    settings = get_settings()
    db = db_session_factory()
    try:
        for source in settings.enabled_crawlers:
            crawler = ENABLED_CRAWLER_REGISTRY.get(source)
            if crawler is None or source not in _BASE_URLS:
                logger.warning("unknown crawler '%s' in ENABLED_CRAWLERS", source)
                continue
            try:
                config = _config_for(source, settings)
                http_client = httpx.Client(
                    follow_redirects=False,
                    timeout=15.0,
                    headers={"User-Agent": config.user_agent},
                )
                try:
                    items = crawler.crawl(config, http_client)
                finally:
                    http_client.close()
                counts = _apply(
                    db,
                    source,
                    items,
                    deactivate_after=settings.crawl_deactivate_after,
                    suspicious_empty_threshold=settings.crawl_suspicious_empty_threshold,
                )
                logger.info("crawl %s: %s", source, counts)
            except Exception:
                logger.exception("crawl failed for source '%s'", source)
    finally:
        db.close()
