import httpx
import pytest
import respx

from app.job_search.crawlers.http import CrawlFetchError, fetch_text


@respx.mock
def test_returns_body_text():
    respx.get("https://example.com/x").mock(
        return_value=httpx.Response(200, text="<html>ok</html>")
    )
    with httpx.Client() as c:
        assert fetch_text("https://example.com/x", c) == "<html>ok</html>"


def test_rejects_non_http_scheme():
    with httpx.Client() as c, pytest.raises(CrawlFetchError):
        fetch_text("file:///etc/passwd", c)


def test_rejects_private_host():
    with httpx.Client() as c:
        with pytest.raises(CrawlFetchError):
            fetch_text("http://127.0.0.1/x", c)
        with pytest.raises(CrawlFetchError):
            fetch_text("http://10.0.0.5/x", c)


def test_rejects_ipv4_mapped_ipv6_loopback():
    with httpx.Client() as c, pytest.raises(CrawlFetchError):
        fetch_text("http://[::ffff:127.0.0.1]/x", c)


@respx.mock
def test_rejects_host_outside_allowed_set():
    respx.get("https://evil.com/x").mock(return_value=httpx.Response(200, text="hi"))
    with httpx.Client() as c, pytest.raises(CrawlFetchError):
        fetch_text("https://evil.com/x", c, allowed_hosts=frozenset({"example.com"}))


@respx.mock
def test_http_error_becomes_crawl_fetch_error():
    respx.get("https://example.com/x").mock(return_value=httpx.Response(503))
    with httpx.Client() as c, pytest.raises(CrawlFetchError):
        fetch_text("https://example.com/x", c)


@respx.mock
def test_body_over_cap_raises():
    respx.get("https://example.com/big").mock(
        return_value=httpx.Response(200, text="x" * 5000)
    )
    with httpx.Client() as c, pytest.raises(CrawlFetchError):
        fetch_text("https://example.com/big", c, max_bytes=1000)
