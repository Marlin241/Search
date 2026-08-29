import calendar
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any

import feedparser
import httpx

from app.job_search import feed_cache
from app.job_search.keyword_matching import keyword_matches_title
from app.job_search.schemas import JobListing, SearchCriteria
from app.job_search.text_utils import html_to_text

_USER_AGENT = "ATSDiagnosticBot/1.0"


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _entry_datetime(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)
    except (ValueError, OverflowError, OSError):
        return None


def _split_company_title(raw_title: str) -> tuple[str, str]:
    if ": " in raw_title:
        company, _, title = raw_title.partition(": ")
        return company.strip(), title.strip()
    return "", raw_title.strip()


class RssFeedClient:
    """Generic RSS/Atom job-feed adapter. One instance per logical source
    (We Work Remotely, RemoteOK, NGO Jobs in Africa), configured with one or
    more feed URLs. Feed bodies are cached per-URL (see feed_cache) so
    repeated searches within the TTL don't re-download them. Keyword
    filtering is client-side against the entry title. `remote_only` sources
    contribute nothing to a location-pinned, non-remote search; non-remote
    feeds (e.g. NGO Jobs in Africa) keep, on a location-pinned search, only
    the entries whose text mentions that location - so an Africa-wide feed
    doesn't leak into a "Paris" search."""

    def __init__(
        self,
        source_name: str,
        feed_urls: list[str],
        remote_only: bool,
        http_client: httpx.Client | None = None,
        ttl_minutes: int = 30,
    ):
        self._source = source_name
        self._feed_urls = feed_urls
        self._remote_only = remote_only
        self._http = http_client or httpx.Client(
            timeout=10.0, headers={"User-Agent": _USER_AGENT}
        )
        self._ttl = timedelta(minutes=ttl_minutes)

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        if (
            self._remote_only
            and not criteria.remote
            and (criteria.location or "").strip()
        ):
            return []

        pinned_location = (criteria.location or "").strip()
        location_needle = (
            _strip_accents(pinned_location)
            if pinned_location and not self._remote_only
            else None
        )

        listings: list[JobListing] = []
        seen_urls: set[str] = set()
        for feed_url in self._feed_urls:
            body = feed_cache.get_or_fetch(feed_url, self._http, self._ttl)
            parsed = feedparser.parse(body)
            for entry in parsed.entries:
                link = entry.get("link")
                raw_title = entry.get("title")
                if not link or not raw_title or link in seen_urls:
                    continue
                if not keyword_matches_title(criteria.keywords, raw_title):
                    continue
                summary = html_to_text(
                    entry.get("summary", "") or entry.get("description", "")
                )
                if (
                    location_needle is not None
                    and location_needle not in _strip_accents(f"{raw_title} {summary}")
                ):
                    continue
                seen_urls.add(link)
                company, title = _split_company_title(raw_title)
                listings.append(
                    JobListing(
                        title=title,
                        company=company,
                        location="Remote" if self._remote_only else None,
                        snippet=summary[:12_000],
                        url=link,
                        source=self._source,
                        ats_type=None,
                        is_remote=self._remote_only,
                        posted_at=_entry_datetime(entry),
                    )
                )
        return listings
