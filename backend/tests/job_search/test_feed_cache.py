from datetime import timedelta

import httpx
import pytest
import respx

from app.job_search import feed_cache
from app.job_search.errors import JobSearchSourceError

FEED_URL = "https://example.com/feed.rss"


@pytest.fixture(autouse=True)
def _clear_cache():
    feed_cache.clear()
    yield
    feed_cache.clear()


@respx.mock
def test_fetches_and_returns_body_on_miss():
    route = respx.get(FEED_URL).mock(return_value=httpx.Response(200, text="<rss/>"))
    with httpx.Client() as client:
        body = feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))
    assert body == "<rss/>"
    assert route.call_count == 1


@respx.mock
def test_second_call_within_ttl_does_not_refetch():
    route = respx.get(FEED_URL).mock(return_value=httpx.Response(200, text="<rss/>"))
    with httpx.Client() as client:
        feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))
        feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))
    assert route.call_count == 1


@respx.mock
def test_raises_job_search_source_error_on_http_error():
    respx.get(FEED_URL).mock(return_value=httpx.Response(503))
    with httpx.Client() as client, pytest.raises(JobSearchSourceError):
        feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))


@respx.mock
def test_raises_job_search_source_error_on_transport_error():
    respx.get(FEED_URL).mock(side_effect=httpx.ConnectError("boom"))
    with httpx.Client() as client, pytest.raises(JobSearchSourceError):
        feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))
