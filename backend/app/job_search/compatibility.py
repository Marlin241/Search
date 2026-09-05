"""Deterministic, dependency-free compatibility scoring for job listings.

Pure Python, no I/O and no LLM calls - this is what runs on every listing of
every search (20-40 results), so it has to be cheap. The LLM-backed *detail*
(app.compatibility.analyzer) is a separate, rate-limited, on-demand call that
only runs when a user clicks a single listing to see why it scored the way
it did; it explains this score, it never recomputes it.

Each `_score_*` function returns `None` when there simply isn't enough data
to judge that criterion (no preference set, no data on the listing...)
instead of guessing a "neutral" number - a criterion nobody can evaluate
must not silently push the overall score up or down. `_weighted_total` only
averages over the criteria that *were* evaluated, redistributing their
weight rather than assuming a fixed denominator of 100.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

from app.job_search.schemas import JobListing
from app.models.candidate_profile import CandidateProfile

# Rubric weights, out of 100.
WEIGHT_TITLE = 35
WEIGHT_LOCATION = 20
WEIGHT_SENIORITY = 15
WEIGHT_SALARY = 15
WEIGHT_FRESHNESS = 15

_WEIGHTS = {
    "title": WEIGHT_TITLE,
    "location": WEIGHT_LOCATION,
    "seniority": WEIGHT_SENIORITY,
    "salary": WEIGHT_SALARY,
    "freshness": WEIGHT_FRESHNESS,
}

# The user hasn't onboarded (no CandidateProfile) yet: nothing here can be
# personalized, so every listing gets the same middling score rather than 0,
# which would visually read as "bad match" for offers nobody has judged, and
# rather than None, which would leave nothing to sort search results on.
NO_PROFILE_SCORE = 50

# Sources known to price in euros - the candidate's own salary expectation is
# now collected in FCFA (XOF), so comparing raw digits against these would
# silently compare the wrong currency. Until listings carry an explicit
# currency (see the FCFA/EUR conversion left for later), the salary
# criterion is simply left unevaluated for these sources, exactly like the
# Senegalese crawlers already do (they never populate `salary` at all).
_EUR_DENOMINATED_SOURCES = {"france_travail", "adzuna"}

# Mirrors frontend/components/onboarding/StepJobTitles.tsx::SENIORITY_LEVELS.
# Upper bound for "senior" is a practical cap, not a real ceiling.
_SENIORITY_YEAR_RANGES: dict[str, tuple[float, float]] = {
    "junior": (0, 1),
    "confirme": (1, 3),
    "confirme_plus": (3, 6),
    "senior": (6, 30),
}

_EXPERIENCE_RE = re.compile(
    r"(\d+)\s*(?:-|à|to)\s*(\d+)\s*ans?\s*d[’']exp|"
    r"(\d+)\s*\+?\s*ans?\s*d[’']exp",
    re.IGNORECASE,
)

_SALARY_NUMBER_RE = re.compile(r"\d[\d\s .,]*\d|\d")

_FRESHNESS_FULL_CREDIT_DAYS = 7
_FRESHNESS_FLOOR_DAYS = 60
_FRESHNESS_FLOOR_SCORE = 15


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _normalize(value: str) -> str:
    return _strip_accents(value.casefold())


def _tokens(value: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9]+", _normalize(value)) if len(tok) > 2}


def _score_title(listing: JobListing, profile: CandidateProfile) -> int | None:
    desired = profile.desired_job_titles or []
    if not desired:
        return None
    title_tokens = _tokens(listing.title)
    if not title_tokens:
        return None
    best_overlap = 0.0
    for desired_title in desired:
        desired_tokens = _tokens(desired_title)
        if not desired_tokens:
            continue
        overlap = len(desired_tokens & title_tokens) / len(desired_tokens)
        best_overlap = max(best_overlap, overlap)
    return round(best_overlap * 100)


def _score_location(listing: JobListing, profile: CandidateProfile) -> int | None:
    is_remote_listing = listing.is_remote
    desired_locations = profile.desired_locations or []

    if profile.remote_preference and is_remote_listing:
        return 100

    if not listing.location:
        return None

    if not desired_locations and not profile.remote_preference:
        # No location constraint entered - nothing to compare against.
        return None

    normalized_location = _normalize(listing.location)
    for desired in desired_locations:
        normalized_desired = _normalize(desired)
        if normalized_desired and (
            normalized_desired in normalized_location
            or normalized_location in normalized_desired
        ):
            return 100

    if profile.remote_preference and not is_remote_listing:
        return 20
    return 25


def _score_seniority(listing: JobListing, profile: CandidateProfile) -> int | None:
    if not profile.seniority_level:
        return None
    desired_range = _SENIORITY_YEAR_RANGES.get(profile.seniority_level)
    if desired_range is None:
        return None

    match = _EXPERIENCE_RE.search(listing.snippet)
    if not match:
        return None
    if match.group(1) and match.group(2):
        offer_years = (float(match.group(1)) + float(match.group(2))) / 2
    else:
        offer_years = float(match.group(3))

    desired_low, desired_high = desired_range
    if desired_low <= offer_years <= desired_high:
        return 100
    distance = (
        desired_low - offer_years
        if offer_years < desired_low
        else offer_years - desired_high
    )
    # Full credit inside the bracket, fading to a floor over a ~5-year gap.
    return max(10, round(100 - distance * 20))


def _extract_salary_range(salary_text: str) -> tuple[int, int] | None:
    numbers = []
    for raw in _SALARY_NUMBER_RE.findall(salary_text):
        cleaned = re.sub(r"[\s .,]", "", raw)
        if cleaned.isdigit():
            value = int(cleaned)
            if value >= 1000:  # filters out stray small numbers (e.g. "35h/semaine")
                numbers.append(value)
    if not numbers:
        return None
    return (min(numbers), max(numbers))


def _score_salary(listing: JobListing, profile: CandidateProfile) -> int | None:
    if listing.source in _EUR_DENOMINATED_SOURCES:
        return None
    if profile.salary_min is None and profile.salary_max is None:
        return None
    if not listing.salary:
        return None
    extracted = _extract_salary_range(listing.salary)
    if extracted is None:
        return None
    offer_mid = sum(extracted) / 2

    desired_min = profile.salary_min if profile.salary_min is not None else 0
    desired_max = profile.salary_max if profile.salary_max is not None else float("inf")
    if desired_min <= offer_mid <= desired_max:
        return 100
    if offer_mid > desired_max:
        return 90  # above expectations is never a bad thing
    gap_ratio = (desired_min - offer_mid) / desired_min if desired_min else 1.0
    return max(10, round(100 - gap_ratio * 200))


def _score_freshness(listing: JobListing) -> int | None:
    if listing.posted_at is None:
        return None
    posted_at = listing.posted_at
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    age_days = (datetime.now(UTC) - posted_at).total_seconds() / 86400
    if age_days <= _FRESHNESS_FULL_CREDIT_DAYS:
        return 100
    if age_days >= _FRESHNESS_FLOOR_DAYS:
        return _FRESHNESS_FLOOR_SCORE
    span = _FRESHNESS_FLOOR_DAYS - _FRESHNESS_FULL_CREDIT_DAYS
    progress = (age_days - _FRESHNESS_FULL_CREDIT_DAYS) / span
    return round(100 - progress * (100 - _FRESHNESS_FLOOR_SCORE))


def _component_scores(
    listing: JobListing, profile: CandidateProfile | None
) -> dict[str, int | None]:
    if profile is None:
        return {
            "title": NO_PROFILE_SCORE,
            "location": NO_PROFILE_SCORE,
            "seniority": NO_PROFILE_SCORE,
            "salary": NO_PROFILE_SCORE,
            "freshness": NO_PROFILE_SCORE,
        }
    return {
        "title": _score_title(listing, profile),
        "location": _score_location(listing, profile),
        "seniority": _score_seniority(listing, profile),
        "salary": _score_salary(listing, profile),
        "freshness": _score_freshness(listing),
    }


def _weighted_total(scores: dict[str, int | None]) -> int:
    evaluated = {key: value for key, value in scores.items() if value is not None}
    if not evaluated:
        # Nothing could be judged at all (e.g. a listing missing every
        # signal) - fall back to the same neutral score as "no profile"
        # rather than divide by zero.
        return NO_PROFILE_SCORE
    weighted_sum = sum(value * _WEIGHTS[key] for key, value in evaluated.items())
    total_weight = sum(_WEIGHTS[key] for key in evaluated)
    return round(weighted_sum / total_weight)


def score_listing(listing: JobListing, profile: CandidateProfile | None) -> int:
    """The single number shown on every job card."""
    return _weighted_total(_component_scores(listing, profile))


def score_breakdown(
    listing: JobListing, profile: CandidateProfile | None
) -> dict[str, int | None]:
    """Component scores plus the overall weighted score - feeds the
    compatibility-detail LLM call, which explains this breakdown rather than
    recomputing it. A `None` component means "not enough data to judge",
    never "bad match"."""
    scores = _component_scores(listing, profile)
    scores["overall"] = _weighted_total(scores)
    return scores
