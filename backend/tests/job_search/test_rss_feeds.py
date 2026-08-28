import httpx
import pytest
import respx

from app.job_search import feed_cache
from app.job_search.errors import JobSearchSourceError
from app.job_search.rss_feeds import RssFeedClient
from app.job_search.schemas import SearchCriteria

FEED_A = "https://weworkremotely.com/remote-jobs.rss"

_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Acme: Senior Python Developer</title>
    <link>https://weworkremotely.com/remote-jobs/acme-python</link>
    <description>Remote Python role, worldwide.</description>
    <pubDate>Wed, 20 Aug 2026 10:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Globex: Product Designer</title>
    <link>https://weworkremotely.com/remote-jobs/globex-designer</link>
    <description>Design systems.</description>
    <pubDate>Tue, 19 Aug 2026 10:00:00 +0000</pubDate>
  </item>
</channel></rss>
"""


@pytest.fixture(autouse=True)
def _clear():
    feed_cache.clear()
    yield
    feed_cache.clear()


@respx.mock
def test_returns_keyword_matched_entries_with_company_split():
    respx.get(FEED_A).mock(return_value=httpx.Response(200, text=_RSS))
    client = RssFeedClient("weworkremotely", [FEED_A], remote_only=True)
    listings = client.search(SearchCriteria(keywords="python", remote=True))
    assert len(listings) == 1
    assert listings[0].title == "Senior Python Developer"
    assert listings[0].company == "Acme"
    assert listings[0].url == "https://weworkremotely.com/remote-jobs/acme-python"
    assert listings[0].source == "weworkremotely"
    assert listings[0].posted_at is not None


@respx.mock
def test_remote_only_returns_empty_when_located_and_not_remote():
    route = respx.get(FEED_A).mock(return_value=httpx.Response(200, text=_RSS))
    client = RssFeedClient("weworkremotely", [FEED_A], remote_only=True)
    assert client.search(SearchCriteria(keywords="python", location="Dakar")) == []
    assert route.call_count == 0


@respx.mock
def test_non_remote_only_feed_ignores_location_rule():
    respx.get(FEED_A).mock(return_value=httpx.Response(200, text=_RSS))
    client = RssFeedClient("ngojobs", [FEED_A], remote_only=False)
    listings = client.search(SearchCriteria(keywords="python", location="Dakar"))
    assert len(listings) == 1


@respx.mock
def test_dedupes_identical_links_across_feeds():
    feed_b = "https://example.com/b.rss"
    respx.get(FEED_A).mock(return_value=httpx.Response(200, text=_RSS))
    respx.get(feed_b).mock(return_value=httpx.Response(200, text=_RSS))
    client = RssFeedClient("ngojobs", [FEED_A, feed_b], remote_only=False)
    listings = client.search(SearchCriteria(keywords="python"))
    assert len(listings) == 1


@respx.mock
def test_raises_when_a_feed_url_is_unavailable():
    respx.get(FEED_A).mock(return_value=httpx.Response(500))
    client = RssFeedClient("ngojobs", [FEED_A], remote_only=False)
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))
