"""The single text heuristic for "is this listing remote-friendly?".

Used by the aggregator to fill JobListing.is_remote for every source that
doesn't set it authoritatively, and by the compatibility scorer. Keeping it
in one place stops the two from drifting apart (they each used to carry
their own near-identical tuple of indicator words).
"""

import unicodedata

_MARKERS = (
    "remote",
    "teletravail",
    "distanciel",
    "hybride",
    "work from home",
    "wfh",
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def is_remote_from_text(*fragments: str | None) -> bool:
    haystack = _normalize(" ".join(f for f in fragments if f))
    return any(marker in haystack for marker in _MARKERS)
