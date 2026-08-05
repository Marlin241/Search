import socket
from unittest.mock import patch

import httpx
import pytest
import respx

from app.offer_ingestion.scraper import scrape_offer, ScrapingError, MAX_RESPONSE_BYTES


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


def test_scrape_offer_rejects_non_http_scheme():
    # No respx mock is set up at all: if the code tried to make a network
    # call, respx would not be active here and this would attempt a real
    # file read / crash instead of raising ScrapingError cleanly.
    with pytest.raises(ScrapingError):
        scrape_offer("file:///etc/passwd")


@respx.mock
@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://localhost/"])
def test_scrape_offer_rejects_loopback_address(url):
    # Real DNS/hosts resolution: 127.0.0.1 and localhost genuinely resolve
    # to loopback on any machine, so no DNS mocking is needed here.
    #
    # Deliberately no respx route is registered for these URLs. respx's
    # default assert_all_mocked=True means that if _validate_url failed to
    # block the request, scrape_offer would attempt a real send and respx
    # would raise AllMockedAssertionError - which is NOT a subclass of
    # httpx.HTTPError, so it would propagate straight out of scrape_offer's
    # `except httpx.HTTPError` handler and fail this test loudly, rather
    # than accidentally being swallowed into a ScrapingError as it would if
    # the request were instead attempted for real against a closed local
    # port. This proves the block happens before any network attempt.
    with pytest.raises(ScrapingError):
        scrape_offer(url)


@respx.mock
def test_scrape_offer_rejects_shared_address_space():
    # RFC 6598 Carrier-Grade NAT / Shared Address Space (100.64.0.0/10).
    # Not a real DNS name, so we mock socket.getaddrinfo to resolve it into
    # that range - same trick as the loopback test: no respx route is
    # registered for it, so if _validate_url's new range check were broken
    # or removed, scrape_offer would attempt a real send and respx would
    # raise AllMockedAssertionError (not caught by scrape_offer's
    # `except httpx.HTTPError`), failing this test loudly instead of
    # accidentally passing.
    fake_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.64.0.1", 80)),
    ]
    with patch("app.offer_ingestion.scraper.socket.getaddrinfo", return_value=fake_addrinfo):
        with pytest.raises(ScrapingError):
            scrape_offer("http://cgnat.example.com/")


@respx.mock
def test_scrape_offer_rejects_redirect_to_internal_address():
    # An external URL that redirects to an internal address must be
    # rejected before the internal hop is fetched - this is the
    # follow_redirects=True bypass the brief calls out.
    respx.get("https://example.com/redirect").mock(
        return_value=httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
    )
    with pytest.raises(ScrapingError):
        scrape_offer("https://example.com/redirect")


@respx.mock
def test_scrape_offer_rejects_oversized_response():
    oversized_body = b"<html><body>" + b"a" * (MAX_RESPONSE_BYTES + 1024) + b"</body></html>"
    respx.get("https://example.com/huge").mock(
        return_value=httpx.Response(200, content=oversized_body)
    )
    with pytest.raises(ScrapingError):
        scrape_offer("https://example.com/huge")
