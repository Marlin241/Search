"""Best-effort timestamp parsing shared by the job-search source adapters.

Each source exposes posting dates in its own format (ISO 8601 strings with
varying precision, epoch milliseconds); parsing failures return None rather
than raising, since a missing `posted_at` just falls back to a neutral
freshness score (see app.job_search.compatibility) instead of failing the
whole search.
"""

from datetime import UTC, datetime


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_epoch_millis(value: float | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    except (ValueError, OSError, OverflowError, TypeError):
        return None
