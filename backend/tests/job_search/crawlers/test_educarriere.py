from datetime import datetime
from pathlib import Path

import httpx
import pytest
import respx

from app.job_search.crawlers.base import CrawlerConfig
from app.job_search.crawlers.educarriere import (
    EducarriereCrawler,
    _listing_urls,
    _parse_offer,
)
from app.job_search.crawlers.http import CrawlFetchError

FIXTURES = Path(__file__).parent / "fixtures"
LISTING = (FIXTURES / "educarriere_listing.html").read_text()
OFFER = (FIXTURES / "educarriere_offer.html").read_text()

BASE = "https://emploi.educarriere.ci"
LIST_URL = "https://emploi.educarriere.ci/page/all"

CONFIG = CrawlerConfig(
    source="educarriere_ci",
    base_url=BASE,
    max_offers=10,
    request_delay_seconds=0.0,
    user_agent="ATSDiagnosticBot/1.0 (+https://example.com)",
)


def test_listing_urls_keeps_only_offer_pages_deduped():
    urls = _listing_urls(LISTING)
    assert urls == [
        "https://emploi.educarriere.ci/offre-154728-controleur-de-gestion-senior.html",
        "https://emploi.educarriere.ci/offre-154665-management-trainee-program.html",
        "https://emploi.educarriere.ci/offre-154506-controleur-de-gestion.html",
        "https://emploi.educarriere.ci/offre-154374-chef-departement-mecanisation.html",
    ]


def test_parse_offer_extracts_fields_from_body_not_junk_og_tags():
    url = "https://emploi.educarriere.ci/offre-154728-controleur-de-gestion-senior.html"
    data = _parse_offer(OFFER, url)
    assert data is not None
    assert data.title == "CONTROLEUR DE GESTION SENIOR"
    assert data.company == "Raynal & Fadika RH"
    assert data.location == "Côte d'Ivoire"
    assert data.contract_type == "CDD"
    assert data.posted_at == datetime(2026, 9, 2)
    assert data.is_remote is False
    assert "Lorem ipsum" not in data.snippet
    assert "Mission de l" in data.snippet


def test_parse_offer_infers_stage_from_the_type_badge():
    html = OFFER.replace("Emploi\n    Postuler", "Stage\n    Postuler").replace(
        "TYPE DE CONTRAT : CDD de 12 mois renouvelable", ""
    )
    data = _parse_offer(html, "https://emploi.educarriere.ci/offre-1-x.html")
    assert data is not None
    assert data.contract_type == "Stage"


def test_parse_offer_returns_none_without_post_body():
    html = "<html><head><title>x - Offres d'emploi</title></head><body></body></html>"
    assert _parse_offer(html, "https://emploi.educarriere.ci/offre-1-x.html") is None


@respx.mock
def test_crawl_reads_listing_then_fetches_capped_offers():
    cfg = CrawlerConfig(
        source="educarriere_ci",
        base_url=BASE,
        max_offers=2,
        request_delay_seconds=0.0,
        user_agent="x",
    )
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, text=LISTING))
    offers = respx.get(
        url__regex=r"https://emploi\.educarriere\.ci/offre-.*\.html"
    ).mock(return_value=httpx.Response(200, text=OFFER))
    with httpx.Client(follow_redirects=False) as client:
        results = EducarriereCrawler().crawl(cfg, client)
    assert len(results) == 2
    assert offers.call_count == 2


@respx.mock
def test_crawl_skips_an_offer_that_fails_to_fetch():
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, text=LISTING))
    respx.get(
        "https://emploi.educarriere.ci/offre-154728-controleur-de-gestion-senior.html"
    ).mock(return_value=httpx.Response(500))
    respx.get(url__regex=r"https://emploi\.educarriere\.ci/offre-.*\.html").mock(
        return_value=httpx.Response(200, text=OFFER)
    )
    with httpx.Client(follow_redirects=False) as client:
        results = EducarriereCrawler().crawl(CONFIG, client)
    assert len(results) == 3
    assert all("154728" not in r.url for r in results)


@respx.mock
def test_crawl_propagates_a_listing_failure():
    respx.get(LIST_URL).mock(return_value=httpx.Response(503))
    with (
        httpx.Client(follow_redirects=False) as client,
        pytest.raises(CrawlFetchError),
    ):
        EducarriereCrawler().crawl(CONFIG, client)
