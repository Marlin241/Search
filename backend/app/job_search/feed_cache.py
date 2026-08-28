"""In-memory TTL cache for raw feed/API response bodies, keyed by URL.

Used by the RSS-feed source adapters (see app.job_search.rss_feeds): several
feeds return their entire catalogue on every request, so re-downloading them
for each user search within a short window is wasted work. Mirrors the
shape of app.job_search.search_cache (threading.Lock, dataclass entry) but
caches a single URL's body rather than a whole merged search result.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

from app.job_search.errors import JobSearchSourceError
from app.utils.time import utcnow


@dataclass
class _Entry:
    body: str
    cached_at: datetime = field(default_factory=utcnow)


_lock = threading.Lock()
_cache: dict[str, _Entry] = {}


def clear() -> None:
    with _lock:
        _cache.clear()


def get_or_fetch(url: str, http_client: httpx.Client, ttl: timedelta) -> str:
    """Return the text body of ``GET url``. On a non-expired cache hit,
    returns the memoised value with no network call. On a miss or expiry,
    performs the GET, raising JobSearchSourceError on any transport error or
    a >= 400 status, then memoises and returns ``response.text``."""
    cutoff = utcnow() - ttl
    with _lock:
        entry = _cache.get(url)
        if entry is not None and entry.cached_at >= cutoff:
            return entry.body

    try:
        response = http_client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JobSearchSourceError(f"Flux {url} indisponible: {exc}") from exc

    body = response.text
    with _lock:
        _cache[url] = _Entry(body=body)
    return body
