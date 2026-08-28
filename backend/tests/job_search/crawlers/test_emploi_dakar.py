from pathlib import Path

import httpx
import pytest
import respx

from app.job_search.crawlers.base import CrawlerConfig
from app.job_search.crawlers.emploi_dakar import EmploiDakarCrawler, _parse_offer
from app.job_search.crawlers.http import CrawlFetchError

FIXTURES = Path(__file__).parent / "fixtures"
SITEMAP = (FIXTURES / "emploi_dakar_sitemap.xml").read_text()
OFFER = (FIXTURES / "emploi_dakar_offer.html").read_text()

CONFIG = CrawlerConfig(
    source="emploi_dakar",
    base_url="https://www.emploidakar.com",
    max_offers=2,
    request_delay_seconds=0.0,
    user_agent="ATSDiagnosticBot/1.0 (+https://example.com)",
)


def test_parse_offer_extracts_core_fields():
    data = _parse_offer(OFFER, "https://www.emploidakar.com/offre-demploi/x/")
    assert data is not None
    assert data.title
    assert data.url == "https://www.emploidakar.com/offre-demploi/x/"
    assert data.snippet


def test_parse_offer_returns_none_without_single_job_listing_block():
    assert _parse_offer("<html><body>nope</body></html>", "https://x/") is None


@respx.mock
def test_crawl_reads_sitemap_then_fetches_capped_most_recent_offers():
    respx.get("https://www.emploidakar.com/job_listing-sitemap.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP)
    )
    bbb = respx.get("https://www.emploidakar.com/offre-demploi/bbb/").mock(
        return_value=httpx.Response(200, text=OFFER)
    )
    aaa = respx.get("https://www.emploidakar.com/offre-demploi/aaa/").mock(
        return_value=httpx.Response(200, text=OFFER)
    )
    ccc = respx.get("https://www.emploidakar.com/offre-demploi/ccc/").mock(
        return_value=httpx.Response(200, text=OFFER)
    )

    with httpx.Client(follow_redirects=False) as client:
        results = EmploiDakarCrawler().crawl(CONFIG, client)

    assert len(results) == 2
    assert bbb.called and aaa.called and not ccc.called
    assert all(
        r.url.startswith("https://www.emploidakar.com/offre-demploi/") for r in results
    )


@respx.mock
def test_crawl_skips_an_offer_that_fails_to_fetch():
    respx.get("https://www.emploidakar.com/job_listing-sitemap.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP)
    )
    respx.get("https://www.emploidakar.com/offre-demploi/bbb/").mock(
        return_value=httpx.Response(200, text=OFFER)
    )
    respx.get("https://www.emploidakar.com/offre-demploi/aaa/").mock(
        return_value=httpx.Response(500)
    )
    with httpx.Client(follow_redirects=False) as client:
        results = EmploiDakarCrawler().crawl(CONFIG, client)
    assert len(results) == 1


@respx.mock
def test_crawl_propagates_a_sitemap_failure():
    respx.get("https://www.emploidakar.com/job_listing-sitemap.xml").mock(
        return_value=httpx.Response(503)
    )
    with (
        httpx.Client(follow_redirects=False) as client,
        pytest.raises(CrawlFetchError),
    ):
        EmploiDakarCrawler().crawl(CONFIG, client)
