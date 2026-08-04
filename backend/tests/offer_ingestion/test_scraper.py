import httpx
import pytest
import respx

from app.offer_ingestion.scraper import scrape_offer, ScrapingError


@respx.mock
def test_scrape_offer_success():
    respx.get("https://example.com/job").mock(
        return_value=httpx.Response(200, html="<html><body>" + ("Description du poste. " * 50) + "</body></html>")
    )
    text = scrape_offer("https://example.com/job")
    assert "Description du poste" in text


@respx.mock
def test_scrape_offer_blocked_raises():
    respx.get("https://example.com/blocked").mock(return_value=httpx.Response(403))
    with pytest.raises(ScrapingError):
        scrape_offer("https://example.com/blocked")


@respx.mock
def test_scrape_offer_empty_content_raises():
    respx.get("https://example.com/empty").mock(
        return_value=httpx.Response(200, html="<html><body></body></html>")
    )
    with pytest.raises(ScrapingError):
        scrape_offer("https://example.com/empty")
