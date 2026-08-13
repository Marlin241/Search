import re
import unicodedata

import httpx

from app.job_search.schemas import JobListing

MAX_COMPANIES_PER_DISCOVERY = 15

_GREENHOUSE_PROBE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
_LEVER_PROBE_URL = "https://api.lever.co/v0/postings/{slug}"


def normalize_company_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    without_punctuation = re.sub(r"[^a-z0-9\s-]", "", without_accents.lower())
    return without_punctuation.strip()


def generate_slug_candidates(normalized_name: str) -> list[str]:
    words = normalized_name.split()
    if not words:
        return []

    candidates = ["".join(words), "-".join(words)]
    seen: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.append(candidate)
    return seen


class DetectionResult:
    """Outcome of probing a company against Greenhouse/Lever.

    `confirmed=False` means the probes were inconclusive (network error or
    5xx) — the caller must NOT cache this result, since it isn't a real
    answer about whether the company has a board. `confirmed=True` with
    `source=None` means every candidate slug returned a definitive "not
    found" (e.g. 404) — that IS safe to cache.
    """

    def __init__(
        self, confirmed: bool, source: str | None = None, slug: str | None = None
    ):
        self.confirmed = confirmed
        self.source = source
        self.slug = slug


def _probe(url_template: str, slug: str, http_client: httpx.Client) -> bool | None:
    try:
        response = http_client.get(url_template.format(slug=slug))
    except httpx.HTTPError:
        return None
    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    return None


def detect_company_ats(company_name: str, http_client: httpx.Client) -> DetectionResult:
    candidates = generate_slug_candidates(normalize_company_name(company_name))
    if not candidates:
        return DetectionResult(confirmed=True, source=None, slug=None)

    any_indeterminate = False
    for url_template, source in (
        (_GREENHOUSE_PROBE_URL, "greenhouse"),
        (_LEVER_PROBE_URL, "lever"),
    ):
        for slug in candidates:
            outcome = _probe(url_template, slug, http_client)
            if outcome is True:
                return DetectionResult(confirmed=True, source=source, slug=slug)
            if outcome is None:
                any_indeterminate = True

    if any_indeterminate:
        return DetectionResult(confirmed=False)
    return DetectionResult(confirmed=True, source=None, slug=None)


def extract_unique_companies(listings: list[JobListing]) -> list[str]:
    seen_normalized: set[str] = set()
    unique_names: list[str] = []
    for listing in listings:
        if not listing.company:
            continue
        normalized = normalize_company_name(listing.company)
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        unique_names.append(listing.company)
    return unique_names
