import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.job_search.schemas import JobListing, SearchCriteria
from app.utils.time import utcnow

# Search results for identical criteria don't depend on which user asked -
# same keywords/location/etc always return the same upstream listings - so
# this is a single global cache, not scoped per user. 15 minutes: long
# enough to absorb repeat visits/navigation within a session without paying
# for a fresh France Travail/Adzuna/La Bonne Alternance round trip, short
# enough that listings don't go stale for long.
_CACHE_TTL = timedelta(minutes=15)


@dataclass
class _CacheEntry:
    listings: list[JobListing]
    unavailable_sources: list[str]
    cached_at: datetime = field(default_factory=utcnow)


_lock = threading.Lock()
_cache: dict[str, _CacheEntry] = {}


def _purge_expired() -> None:
    cutoff = utcnow() - _CACHE_TTL
    with _lock:
        expired = [key for key, entry in _cache.items() if entry.cached_at < cutoff]
        for key in expired:
            del _cache[key]


def build_cache_key(criteria: SearchCriteria) -> str:
    """Canonical key for `criteria`: normalizes casing/whitespace/order so
    equivalent-but-differently-formatted requests share a cache entry.
    Never mutates or reuses this normalized form for the actual upstream
    search call - only for cache indexing."""
    parts = [
        criteria.keywords.strip().lower(),
        (criteria.location or "").strip().lower(),
        (criteria.contract_type or "").strip().lower(),
        "1" if criteria.remote else "0",
        ",".join(sorted(kw.strip().lower() for kw in criteria.exclude_keywords)),
    ]
    raw_key = "|".join(parts)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def get(key: str) -> tuple[list[JobListing], list[str]] | None:
    _purge_expired()
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        # Copy each listing out: the caller (search()) mutates
        # `compatibility_score` in place per-user after this call, and that
        # must never leak back into the shared cache entry.
        return (
            [listing.model_copy() for listing in entry.listings],
            list(entry.unavailable_sources),
        )


def set(key: str, listings: list[JobListing], unavailable_sources: list[str]) -> None:
    with _lock:
        _cache[key] = _CacheEntry(
            listings=[listing.model_copy() for listing in listings],
            unavailable_sources=list(unavailable_sources),
        )
