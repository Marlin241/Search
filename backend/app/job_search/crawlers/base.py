from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx


@dataclass(frozen=True)
class CrawledListingData:
    """A single normalized job offer produced by a crawler, before it is
    upserted into the crawled_listing table by crawl_runner."""

    url: str
    title: str
    company: str | None
    location: str | None
    snippet: str
    salary: str | None
    contract_type: str | None
    is_remote: bool
    posted_at: datetime | None


@dataclass(frozen=True)
class CrawlerConfig:
    source: str
    base_url: str
    max_offers: int
    request_delay_seconds: float
    user_agent: str


class Crawler(Protocol):
    source: str

    def crawl(
        self, config: CrawlerConfig, http_client: httpx.Client
    ) -> list[CrawledListingData]: ...
