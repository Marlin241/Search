"""Deterministic, dependency-free compatibility scoring for job listings.

Pure Python, no I/O and no LLM calls - this is what runs on every listing of
every search (20-40 results), so it has to be cheap. The LLM-backed *detail*
(app.compatibility.analyzer) is a separate, rate-limited, on-demand call that
only runs when a user clicks a single listing to see why it scored the way
it did; it explains this score, it never recomputes it.
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

NEUTRAL_TITLE_SCORE = 50
NEUTRAL_LOCATION_SCORE = 30
NEUTRAL_SENIORITY_SCORE = 50
NEUTRAL_SALARY_SCORE = 60
NEUTRAL_FRESHNESS_SCORE = 50

# The user hasn't onboarded (no CandidateProfile) yet: nothing here can be
# personalized, so every listing gets the same middling score rather than 0,
# which would visually read as "bad match" for offers nobody has judged.
NO_PROFILE_SCORE = 50

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

_SALARY_NUMBER_RE = re.compile(r"\d[\d\s .,]*\d|\d")

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


def _score_title(listing: JobListing, profile: CandidateProfile) -> int:
    desired = profile.desired_job_titles or []
    if not desired:
        return NEUTRAL_TITLE_SCORE
    title_tokens = _tokens(listing.title)
    if not title_tokens:
        return NEUTRAL_TITLE_SCORE
    best_overlap = 0.0
    for desired_title in desired:
        desired_tokens = _tokens(desired_title)
        if not desired_tokens:
            continue
        overlap = len(desired_tokens & title_tokens) / len(desired_tokens)
        best_overlap = max(best_overlap, overlap)
    return round(best_overlap * 100)


def _score_location(listing: JobListing, profile: CandidateProfile) -> int:
    is_remote_listing = listing.is_remote
    desired_locations = profile.desired_locations or []

    if profile.remote_preference and is_remote_listing:
        return 100

    if not listing.location:
        return NEUTRAL_LOCATION_SCORE

    if not desired_locations and not profile.remote_preference:
        # No location constraint entered - nothing to penalize against.
        return 60

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


def _score_seniority(listing: JobListing, profile: CandidateProfile) -> int:
    if not profile.seniority_level:
        return NEUTRAL_SENIORITY_SCORE
    desired_range = _SENIORITY_YEAR_RANGES.get(profile.seniority_level)
    if desired_range is None:
        return NEUTRAL_SENIORITY_SCORE

    match = _EXPERIENCE_RE.search(listing.snippet)
    if not match:
        return NEUTRAL_SENIORITY_SCORE
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
        cleaned = re.sub(r"[\s .,]", "", raw)
        if cleaned.isdigit():
            value = int(cleaned)
            if value >= 1000:  # filters out stray small numbers (e.g. "35h/semaine")
                numbers.append(value)
    if not numbers:
        return None
    return (min(numbers), max(numbers))


def _score_salary(listing: JobListing, profile: CandidateProfile) -> int:
    if profile.salary_min is None and profile.salary_max is None:
        return NEUTRAL_SALARY_SCORE
    if not listing.salary:
        return NEUTRAL_SALARY_SCORE
    extracted = _extract_salary_range(listing.salary)
    if extracted is None:
        return NEUTRAL_SALARY_SCORE
    offer_mid = sum(extracted) / 2

    desired_min = profile.salary_min if profile.salary_min is not None else 0
    desired_max = profile.salary_max if profile.salary_max is not None else float("inf")
    if desired_min <= offer_mid <= desired_max:
        return 100
    if offer_mid > desired_max:
        return 90  # above expectations is never a bad thing
    gap_ratio = (desired_min - offer_mid) / desired_min if desired_min else 1.0
    return max(10, round(100 - gap_ratio * 200))


def _score_freshness(listing: JobListing) -> int:
    if listing.posted_at is None:
        return NEUTRAL_FRESHNESS_SCORE
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
) -> dict[str, int]:
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


def _weighted_total(scores: dict[str, int]) -> int:
    total = (
        scores["title"] * WEIGHT_TITLE
        + scores["location"] * WEIGHT_LOCATION
        + scores["seniority"] * WEIGHT_SENIORITY
        + scores["salary"] * WEIGHT_SALARY
        + scores["freshness"] * WEIGHT_FRESHNESS
    )
    return round(total / 100)


def score_listing(listing: JobListing, profile: CandidateProfile | None) -> int:
    """The single number shown on every job card."""
    return _weighted_total(_component_scores(listing, profile))


def score_breakdown(
    listing: JobListing, profile: CandidateProfile | None
) -> dict[str, int]:
    """Component scores plus the overall weighted score - feeds the
    compatibility-detail LLM call, which explains this breakdown rather than
    recomputing it."""
    scores = _component_scores(listing, profile)
    scores["overall"] = _weighted_total(scores)
    return scores
