from datetime import datetime
from pathlib import Path

import httpx
import pytest
import respx

from app.job_search.crawlers.base import CrawlerConfig
from app.job_search.crawlers.http import CrawlFetchError
from app.job_search.crawlers.senjob import SenjobCrawler, _listing_rows, _parse_offer

FIXTURES = Path(__file__).parent / "fixtures"
LISTING = (FIXTURES / "senjob_listing.html").read_text()
LISTING_P2 = (FIXTURES / "senjob_listing_p2.html").read_text()
OFFER = (FIXTURES / "senjob_offer.html").read_text()

BASE = "https://senjob.com/sn"
LISTING_URL = "https://senjob.com/sn/offres-d-emploi.php"

CONFIG = CrawlerConfig(
    source="senjob",
    base_url=BASE,
    max_offers=3,
    request_delay_seconds=0.0,
    user_agent="ATSDiagnosticBot/1.0 (+https://example.com)",
)


def _row(url: str):
    return next(r for r in _listing_rows(LISTING) if r.url == url)


def test_listing_rows_dedupe_the_sponsored_duplicate():
    rows = _listing_rows(LISTING)
    urls = [r.url for r in rows]
    # "comptable_e_163619" appears in a featured row AND a normal row.
    assert urls.count("https://senjob.com/sn/jobseekers/comptable_e_163619.html") == 1
    assert len(rows) == 3


def test_listing_row_carries_title_location_and_iso_date():
    row = _row(
        "https://senjob.com/sn/jobseekers/conducteur-de-travaux-electriques_e_163624.html"
    )
    assert row.title == "Conducteur de travaux électriques"
    assert row.location == "Thiès"
    assert row.posted_at == datetime(2026, 9, 2)


def test_parse_offer_merges_detail_page_and_listing_row():
    row = _row("https://senjob.com/sn/jobseekers/comptable_e_163619.html")
    data = _parse_offer(OFFER, row)
    assert data is not None
    assert data.title == "Comptable"
    assert data.url == row.url
    assert data.location == "Dakar"
    assert data.company is None
    assert data.posted_at == datetime(2026, 9, 3)
    # snippet comes from og:description, HTML-unescaped and tag-stripped
    assert "<b>" not in data.snippet
    assert "Comptable confirmé(e)" in data.snippet
    assert data.contract_type == "CDI"
    assert data.is_remote is False


def test_parse_offer_returns_none_when_description_missing():
    row = _row("https://senjob.com/sn/jobseekers/comptable_e_163619.html")
    assert (
        _parse_offer("<html><head><title>x</title></head><body></body></html>", row)
        is None
    )


def test_parse_offer_flags_remote_from_title():
    row = _row(
        "https://senjob.com/sn/jobseekers/stagiaire-ux-ui-designer_e_163628.html"
    )
    html = OFFER.replace(
        "<title>Comptable</title>", "<title>Community Manager (télétravail)</title>"
    )
    data = _parse_offer(html, row)
    assert data is not None and data.is_remote is True


@respx.mock
def test_crawl_paginates_dedupes_and_caps_at_max_offers():
    respx.get(LISTING_URL).mock(return_value=httpx.Response(200, text=LISTING))
    respx.get(f"{LISTING_URL}?page=2").mock(
        return_value=httpx.Response(200, text=LISTING_P2)
    )
    offer_route = respx.get(
        url__regex=r"https://senjob\.com/sn/jobseekers/.*\.html"
    ).mock(return_value=httpx.Response(200, text=OFFER))

    with httpx.Client(follow_redirects=False) as client:
        results = SenjobCrawler().crawl(CONFIG, client)

    assert len(results) == 3  # capped at max_offers before page 2 is needed
    assert offer_route.call_count == 3
    assert len({r.url for r in results}) == 3


@respx.mock
def test_crawl_follows_pagination_when_first_page_is_short():
    cfg = CrawlerConfig(
        source="senjob",
        base_url=BASE,
        max_offers=5,
        request_delay_seconds=0.0,
        user_agent="x",
    )
    # register the query-specific routes before the bare one (respx picks
    # the first matching route, and a query-less URL still matches ?page=N)
    respx.get(LISTING_URL, params={"page": "2"}).mock(
        return_value=httpx.Response(200, text=LISTING_P2)
    )
    respx.get(LISTING_URL, params={"page": "3"}).mock(
        return_value=httpx.Response(200, text=LISTING_P2)
    )
    respx.get(LISTING_URL).mock(return_value=httpx.Response(200, text=LISTING))
    respx.get(url__regex=r"https://senjob\.com/sn/jobseekers/.*\.html").mock(
        return_value=httpx.Response(200, text=OFFER)
    )

    with httpx.Client(follow_redirects=False) as client:
        results = SenjobCrawler().crawl(cfg, client)

    # 3 from page 1 + 2 new from page 2; page 3 repeats page 2 -> stop.
    assert len(results) == 5


@respx.mock
def test_crawl_skips_an_offer_that_fails_to_fetch():
    respx.get(LISTING_URL).mock(return_value=httpx.Response(200, text=LISTING))
    respx.get(f"{LISTING_URL}?page=2").mock(
        return_value=httpx.Response(200, text=LISTING_P2)
    )
    respx.get("https://senjob.com/sn/jobseekers/comptable_e_163619.html").mock(
        return_value=httpx.Response(500)
    )
    respx.get(url__regex=r"https://senjob\.com/sn/jobseekers/.*\.html").mock(
        return_value=httpx.Response(200, text=OFFER)
    )
    with httpx.Client(follow_redirects=False) as client:
        results = SenjobCrawler().crawl(CONFIG, client)
    assert len(results) == 2
    assert all("comptable_e_163619" not in r.url for r in results)


@respx.mock
def test_crawl_propagates_a_first_page_failure():
    respx.get(LISTING_URL).mock(return_value=httpx.Response(503))
    with (
        httpx.Client(follow_redirects=False) as client,
        pytest.raises(CrawlFetchError),
    ):
        SenjobCrawler().crawl(CONFIG, client)
