from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC "now", matching the deprecated `datetime.utcnow()` this
    replaces byte-for-byte - every `DateTime` column and comparison in this
    codebase stores/expects naive values, so switching to a timezone-aware
    return here would break comparisons against those columns."""
    return datetime.now(UTC).replace(tzinfo=None)
