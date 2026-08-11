# Découverte automatique des entreprises Greenhouse/Lever — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual "Entreprises à suivre sur Greenhouse/Lever" search field with automatic detection — the backend derives candidate companies from France Travail/Adzuna results and discovers their Greenhouse/Lever boards itself.

**Architecture:** `POST /job-search/search` still queries France Travail/Adzuna synchronously, then serves already-known companies (cached in a new `CompanyAtsMapping` table) immediately, and kicks off a `BackgroundTasks` job to probe newly-seen companies against the Greenhouse/Lever APIs. The frontend polls a new `GET /job-search/search/{search_id}/discovery` endpoint every few seconds to append newly discovered offers without blocking the initial results.

**Tech Stack:** FastAPI + SQLAlchemy + httpx + respx (backend), Next.js + Vitest + Testing Library (frontend). No new external dependencies.

## Global Constraints

- Reference spec: `docs/superpowers/specs/2026-08-11-decouverte-entreprises-design.md` — read it before starting if anything below is ambiguous.
- `MAX_COMPANIES_PER_DISCOVERY = 15` — hard cap on unknown companies probed per search.
- No scraping of arbitrary company career pages — only the existing Greenhouse and Lever public job board APIs are probed.
- No new external dependency (no search engine API, no Redis/Celery) — background state is in-process memory, matching this project's current single-process scale.
- `CompanyAtsMapping` entries never expire / are never re-checked once confirmed (found or not found).
- Polling interval: 3000ms, matching the spec.
- In-memory discovery state TTL: 5 minutes.
- Keep changes inside `backend/app/job_search/`, `backend/app/models/`, `backend/app/routers/job_search.py`, `backend/app/schemas/job_search.py`, and the frontend `components/`, `lib/`, `app/candidatures/` — no unrelated refactors.

---

## Task 1: Refactor `GreenhouseJobBoardClient` to accept explicit company slugs

**Files:**
- Modify: `backend/app/job_search/greenhouse.py`
- Test: `backend/tests/job_search/test_greenhouse.py`

**Interfaces:**
- Produces: `GreenhouseJobBoardClient.search(self, criteria: SearchCriteria, company_slugs: list[str]) -> list[JobListing]` — replaces the old `search(self, criteria)` which read `criteria.followed_companies`. Later tasks (7, 8, 10) call this with explicitly-sourced slugs (cached or newly discovered).

- [ ] **Step 1: Update the test file to call the new signature**

Replace the full contents of `backend/tests/job_search/test_greenhouse.py` with:

```python
import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings_for_given_companies():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Développeur Python",
                        "location": {"name": "Paris"},
                        "content": "<p>Nous recherchons un <b>développeur Python</b>.</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    },
                    {
                        "title": "Chef de projet",
                        "location": {"name": "Lyon"},
                        "content": "<p>Gestion de projet.</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
                    },
                ]
            },
        )
    )

    client = GreenhouseJobBoardClient()
    listings = client.search(SearchCriteria(keywords="python"), ["acme"])

    assert len(listings) == 1
    assert listings[0].title == "Développeur Python"
    assert listings[0].ats_type == "greenhouse"
    assert "développeur Python" in listings[0].snippet
    assert "<b>" not in listings[0].snippet


@respx.mock
def test_search_with_no_keyword_returns_all_jobs():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [{"title": "Chef de projet", "absolute_url": "https://x"}]})
    )

    client = GreenhouseJobBoardClient()
    listings = client.search(SearchCriteria(keywords=""), ["acme"])

    assert len(listings) == 1


@respx.mock
def test_search_raises_on_http_error():
    respx.get("https://boards-api.greenhouse.io/v1/boards/unknown-co/jobs").mock(return_value=httpx.Response(404))

    client = GreenhouseJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"), ["unknown-co"])


def test_search_with_no_company_slugs_returns_empty_list():
    client = GreenhouseJobBoardClient()
    assert client.search(SearchCriteria(keywords="python"), []) == []


@respx.mock
def test_search_raises_on_location_field_wrong_shape():
    """Test for wrong-shaped-but-valid-JSON: location is a string instead of an object"""
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Développeur Python",
                        "location": "Paris",  # Wrong type: should be {"name": "..."}
                        "content": "<p>Test</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    }
                ]
            },
        )
    )

    client = GreenhouseJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"), ["acme"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_greenhouse.py -v`
Expected: FAIL with `TypeError: GreenhouseJobBoardClient.search() takes 2 positional arguments but 3 were given` (or similar) since the client doesn't yet accept `company_slugs`.

- [ ] **Step 3: Update the client implementation**

In `backend/app/job_search/greenhouse.py`, change:

```python
    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        listings: list[JobListing] = []
        keyword = criteria.keywords.lower()

        for company_slug in criteria.followed_companies:
```

to:

```python
    def search(self, criteria: SearchCriteria, company_slugs: list[str]) -> list[JobListing]:
        listings: list[JobListing] = []
        keyword = criteria.keywords.lower()

        for company_slug in company_slugs:
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_greenhouse.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/job_search/greenhouse.py tests/job_search/test_greenhouse.py
git commit -m "refactor: pass explicit company slugs to GreenhouseJobBoardClient.search"
```

---

## Task 2: Refactor `LeverJobBoardClient` to accept explicit company slugs

**Files:**
- Modify: `backend/app/job_search/lever.py`
- Test: `backend/tests/job_search/test_lever.py`

**Interfaces:**
- Produces: `LeverJobBoardClient.search(self, criteria: SearchCriteria, company_slugs: list[str]) -> list[JobListing]` — mirrors Task 1's `GreenhouseJobBoardClient.search`.

- [ ] **Step 1: Update the test file to call the new signature**

Replace the full contents of `backend/tests/job_search/test_lever.py` with:

```python
import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.lever import LeverJobBoardClient
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings_for_given_companies():
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "text": "Développeur Python",
                    "categories": {"location": "Paris"},
                    "descriptionPlain": "Nous recherchons un développeur Python.",
                    "hostedUrl": "https://jobs.lever.co/acme/1",
                },
                {
                    "text": "Chef de projet",
                    "categories": {"location": "Lyon"},
                    "descriptionPlain": "Gestion de projet.",
                    "hostedUrl": "https://jobs.lever.co/acme/2",
                },
            ],
        )
    )

    client = LeverJobBoardClient()
    listings = client.search(SearchCriteria(keywords="python"), ["acme"])

    assert len(listings) == 1
    assert listings[0].title == "Développeur Python"
    assert listings[0].ats_type == "lever"
    assert listings[0].location == "Paris"


@respx.mock
def test_search_with_no_keyword_returns_all_jobs():
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "text": "Chef de projet",
                    "categories": {"location": "Lyon"},
                    "descriptionPlain": "Test",
                    "hostedUrl": "https://jobs.lever.co/acme/2",
                },
            ],
        )
    )

    client = LeverJobBoardClient()
    listings = client.search(SearchCriteria(keywords=""), ["acme"])

    assert len(listings) == 1


@respx.mock
def test_search_raises_on_http_error():
    respx.get("https://api.lever.co/v0/postings/unknown-co").mock(return_value=httpx.Response(404))

    client = LeverJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"), ["unknown-co"])


def test_search_with_no_company_slugs_returns_empty_list():
    client = LeverJobBoardClient()
    assert client.search(SearchCriteria(keywords="python"), []) == []


@respx.mock
def test_search_raises_on_categories_field_wrong_shape():
    """Test for wrong-shaped-but-valid-JSON: categories is a string instead of an object"""
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "text": "Développeur Python",
                    "categories": "Paris",  # Wrong type: should be {"location": "..."}
                    "descriptionPlain": "Test",
                    "hostedUrl": "https://jobs.lever.co/acme/1",
                }
            ],
        )
    )

    client = LeverJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"), ["acme"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_lever.py -v`
Expected: FAIL with a `TypeError` about the extra `company_slugs` argument.

- [ ] **Step 3: Update the client implementation**

In `backend/app/job_search/lever.py`, change:

```python
    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        listings: list[JobListing] = []
        keyword = criteria.keywords.lower()

        for company_slug in criteria.followed_companies:
```

to:

```python
    def search(self, criteria: SearchCriteria, company_slugs: list[str]) -> list[JobListing]:
        listings: list[JobListing] = []
        keyword = criteria.keywords.lower()

        for company_slug in company_slugs:
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_lever.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/job_search/lever.py tests/job_search/test_lever.py
git commit -m "refactor: pass explicit company slugs to LeverJobBoardClient.search"
```

---

## Task 3: Remove the manual `followed_companies` field from `SearchCriteria`

**Files:**
- Modify: `backend/app/job_search/schemas.py`
- Test: `backend/tests/job_search/test_schemas.py`

**Interfaces:**
- Produces: `SearchCriteria` without a `followed_companies` field. Every later backend task constructs `SearchCriteria` without this field.

- [ ] **Step 1: Update the test**

In `backend/tests/job_search/test_schemas.py`, remove the line `assert criteria.followed_companies == []` from `test_search_criteria_defaults`, so it reads:

```python
def test_search_criteria_defaults():
    criteria = SearchCriteria(keywords="développeur python")
    assert criteria.location is None
    assert criteria.exclude_keywords == []
```

- [ ] **Step 2: Run the tests to verify they still pass (field still present)**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_schemas.py -v`
Expected: PASS — this step only removes an assertion, it doesn't yet change behavior.

- [ ] **Step 3: Remove the field from the schema**

In `backend/app/job_search/schemas.py`, remove the `followed_companies` line so `SearchCriteria` reads:

```python
class SearchCriteria(BaseModel):
    keywords: str
    location: str | None = None
    contract_type: str | None = None
    remote: bool | None = None
    exclude_keywords: list[str] = []
```

- [ ] **Step 4: Run the full job_search test suite to verify nothing else references the removed field**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/ -v`
Expected: PASS (all tests, including greenhouse/lever from Tasks 1–2, which no longer reference `followed_companies`)

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/job_search/schemas.py tests/job_search/test_schemas.py
git commit -m "feat: remove manual followed_companies search field"
```

---

## Task 4: Add the `CompanyAtsMapping` model

**Files:**
- Create: `backend/app/models/company_ats_mapping.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/test_company_ats_mapping.py`

**Interfaces:**
- Produces: `CompanyAtsMapping` SQLAlchemy model with columns `id: int`, `company_name: str` (unique), `source: str | None`, `slug: str | None`, `checked_at: datetime`. Consumed by Task 6 (`company_cache.py`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/models/test_company_ats_mapping.py`:

```python
from app.models.company_ats_mapping import CompanyAtsMapping


def test_create_found_mapping(db_session):
    db_session.add(CompanyAtsMapping(company_name="acme", source="greenhouse", slug="acme"))
    db_session.commit()

    fetched = db_session.query(CompanyAtsMapping).filter(CompanyAtsMapping.company_name == "acme").first()
    assert fetched.source == "greenhouse"
    assert fetched.slug == "acme"
    assert fetched.checked_at is not None


def test_create_not_found_mapping_allows_null_source_and_slug(db_session):
    db_session.add(CompanyAtsMapping(company_name="obscure-corp", source=None, slug=None))
    db_session.commit()

    fetched = db_session.query(CompanyAtsMapping).filter(CompanyAtsMapping.company_name == "obscure-corp").first()
    assert fetched.source is None
    assert fetched.slug is None


def test_company_name_is_unique(db_session):
    from sqlalchemy.exc import IntegrityError

    db_session.add(CompanyAtsMapping(company_name="acme", source="greenhouse", slug="acme"))
    db_session.commit()

    db_session.add(CompanyAtsMapping(company_name="acme", source="lever", slug="acme-2"))
    try:
        db_session.commit()
        assert False, "expected IntegrityError"
    except IntegrityError:
        db_session.rollback()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/models/test_company_ats_mapping.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.company_ats_mapping'`

- [ ] **Step 3: Create the model**

Create `backend/app/models/company_ats_mapping.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompanyAtsMapping(Base):
    """Cache of which Greenhouse/Lever board (if any) a company uses, keyed
    by normalized company name (app.job_search.discovery.normalize_company_name).
    Populated automatically by app.job_search.background_discovery — never
    written to by the user. Entries are never expired or re-checked: see
    docs/superpowers/specs/2026-08-11-decouverte-entreprises-design.md."""

    __tablename__ = "company_ats_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    slug: Mapped[str | None] = mapped_column(String, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 4: Register the model in `app/models/__init__.py`**

In `backend/app/models/__init__.py`, add the import and `__all__` entry:

```python
from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.candidate_profile import CandidateProfile
from app.models.application import Application
from app.models.job_search_request_log import JobSearchRequestLog
from app.models.prefilled_form_request_log import PrefilledFormRequestLog
from app.models.company_ats_mapping import CompanyAtsMapping

__all__ = [
    "User",
    "Diagnostic",
    "PersonalizedDocument",
    "PersonalizationRequestLog",
    "CandidateProfile",
    "Application",
    "JobSearchRequestLog",
    "PrefilledFormRequestLog",
    "CompanyAtsMapping",
]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && ./venv/bin/python -m pytest tests/models/test_company_ats_mapping.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/models/company_ats_mapping.py app/models/__init__.py tests/models/test_company_ats_mapping.py
git commit -m "feat: add CompanyAtsMapping model"
```

---

## Task 5: Add company-name normalization, slug detection, and extraction (`discovery.py`)

**Files:**
- Create: `backend/app/job_search/discovery.py`
- Test: `backend/tests/job_search/test_discovery.py`

**Interfaces:**
- Consumes: `app.job_search.schemas.JobListing`
- Produces:
  - `normalize_company_name(name: str) -> str` — used by Task 6 (`company_cache.py`) to build cache keys.
  - `generate_slug_candidates(normalized_name: str) -> list[str]`
  - `class DetectionResult: confirmed: bool; source: str | None; slug: str | None`
  - `detect_company_ats(company_name: str, http_client: httpx.Client) -> DetectionResult` — used by Task 7 (`background_discovery.py`).
  - `extract_unique_companies(listings: list[JobListing]) -> list[str]` — used by Task 9 (router).
  - `MAX_COMPANIES_PER_DISCOVERY = 15`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/job_search/test_discovery.py`:

```python
import httpx
import respx

from app.job_search.discovery import (
    detect_company_ats,
    extract_unique_companies,
    generate_slug_candidates,
    normalize_company_name,
)
from app.job_search.schemas import JobListing


def _listing(company: str, url: str = "https://example.com/1") -> JobListing:
    return JobListing(
        title="Développeur",
        company=company,
        location=None,
        snippet="",
        url=url,
        source="france_travail",
        ats_type=None,
    )


def test_normalize_company_name_strips_accents_and_apostrophes():
    assert normalize_company_name("L'Oréal") == "loreal"


def test_normalize_company_name_lowercases_and_trims():
    assert normalize_company_name("  Acme Corp  ") == "acme corp"


def test_generate_slug_candidates_single_word():
    assert generate_slug_candidates("loreal") == ["loreal"]


def test_generate_slug_candidates_multi_word():
    assert generate_slug_candidates("la poste") == ["laposte", "la-poste"]


def test_generate_slug_candidates_empty_string_returns_no_candidates():
    assert generate_slug_candidates("") == []


@respx.mock
def test_detect_company_ats_finds_greenhouse_on_first_candidate():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(return_value=httpx.Response(200, json={}))

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is True
    assert result.source == "greenhouse"
    assert result.slug == "acme"


@respx.mock
def test_detect_company_ats_falls_back_to_lever_when_greenhouse_404s():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(return_value=httpx.Response(404))
    respx.get("https://api.lever.co/v0/postings/acme").mock(return_value=httpx.Response(200, json=[]))

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is True
    assert result.source == "lever"
    assert result.slug == "acme"


@respx.mock
def test_detect_company_ats_confirmed_not_found_when_all_candidates_404():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(return_value=httpx.Response(404))
    respx.get("https://api.lever.co/v0/postings/acme").mock(return_value=httpx.Response(404))

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is True
    assert result.source is None
    assert result.slug is None


@respx.mock
def test_detect_company_ats_not_confirmed_on_network_error():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(side_effect=httpx.ConnectError("down"))
    respx.get("https://api.lever.co/v0/postings/acme").mock(return_value=httpx.Response(404))

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is False


@respx.mock
def test_detect_company_ats_not_confirmed_on_server_error():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(return_value=httpx.Response(500))
    respx.get("https://api.lever.co/v0/postings/acme").mock(return_value=httpx.Response(404))

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is False


def test_extract_unique_companies_dedupes_case_insensitively_preserving_first_seen_casing():
    listings = [_listing("Acme", "https://example.com/1"), _listing("ACME", "https://example.com/2"), _listing("Globex", "https://example.com/3")]

    assert extract_unique_companies(listings) == ["Acme", "Globex"]


def test_extract_unique_companies_skips_blank_company_names():
    listings = [_listing("", "https://example.com/1"), _listing("Acme", "https://example.com/2")]

    assert extract_unique_companies(listings) == ["Acme"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.job_search.discovery'`

- [ ] **Step 3: Implement `discovery.py`**

Create `backend/app/job_search/discovery.py`:

```python
import re
import unicodedata

import httpx

from app.job_search.schemas import JobListing

MAX_COMPANIES_PER_DISCOVERY = 15

_GREENHOUSE_PROBE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
_LEVER_PROBE_URL = "https://api.lever.co/v0/postings/{slug}"


def normalize_company_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
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

    def __init__(self, confirmed: bool, source: str | None = None, slug: str | None = None):
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
    for url_template, source in ((_GREENHOUSE_PROBE_URL, "greenhouse"), (_LEVER_PROBE_URL, "lever")):
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_discovery.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/job_search/discovery.py tests/job_search/test_discovery.py
git commit -m "feat: add company name normalization and Greenhouse/Lever detection"
```

---

## Task 6: Add the DB-backed company ATS cache (`company_cache.py`)

**Files:**
- Create: `backend/app/job_search/company_cache.py`
- Test: `backend/tests/job_search/test_company_cache.py`

**Interfaces:**
- Consumes: `app.job_search.discovery.normalize_company_name`, `app.models.company_ats_mapping.CompanyAtsMapping`
- Produces:
  - `get_cached_mapping(db: Session, company_name: str) -> CompanyAtsMapping | None` — used by Task 9 (router).
  - `save_mapping(db: Session, company_name: str, source: str | None, slug: str | None) -> None` — used by Task 7 (`background_discovery.py`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/job_search/test_company_cache.py`:

```python
from app.job_search.company_cache import get_cached_mapping, save_mapping
from app.models.company_ats_mapping import CompanyAtsMapping


def test_get_cached_mapping_returns_none_when_absent(db_session):
    assert get_cached_mapping(db_session, "Acme") is None


def test_save_then_get_cached_mapping_returns_found_result(db_session):
    save_mapping(db_session, "Acme", "greenhouse", "acme")

    mapping = get_cached_mapping(db_session, "Acme")

    assert mapping is not None
    assert mapping.source == "greenhouse"
    assert mapping.slug == "acme"


def test_save_then_get_cached_mapping_returns_not_found_result(db_session):
    save_mapping(db_session, "Obscure Corp", None, None)

    mapping = get_cached_mapping(db_session, "Obscure Corp")

    assert mapping is not None
    assert mapping.source is None
    assert mapping.slug is None


def test_get_cached_mapping_matches_regardless_of_casing_and_accents(db_session):
    save_mapping(db_session, "L'Oréal", "lever", "loreal")

    assert get_cached_mapping(db_session, "loreal") is not None
    assert get_cached_mapping(db_session, "LOREAL") is not None


def test_save_mapping_ignores_duplicate_insert_for_same_normalized_name(db_session):
    save_mapping(db_session, "Acme", "greenhouse", "acme")
    save_mapping(db_session, "ACME", "lever", "acme-2")  # same normalized name, should not crash or overwrite

    rows = db_session.query(CompanyAtsMapping).filter(CompanyAtsMapping.company_name == "acme").all()
    assert len(rows) == 1
    assert rows[0].source == "greenhouse"  # first write wins
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_company_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.job_search.company_cache'`

- [ ] **Step 3: Implement `company_cache.py`**

Create `backend/app/job_search/company_cache.py`:

```python
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.job_search.discovery import normalize_company_name
from app.models.company_ats_mapping import CompanyAtsMapping


def get_cached_mapping(db: Session, company_name: str) -> CompanyAtsMapping | None:
    normalized = normalize_company_name(company_name)
    return db.scalar(select(CompanyAtsMapping).where(CompanyAtsMapping.company_name == normalized))


def save_mapping(db: Session, company_name: str, source: str | None, slug: str | None) -> None:
    normalized = normalize_company_name(company_name)
    db.add(CompanyAtsMapping(company_name=normalized, source=source, slug=slug, checked_at=datetime.utcnow()))
    try:
        db.commit()
    except IntegrityError:
        # Another request already wrote this company_name (unique constraint) —
        # its result stands, this attempt is simply dropped.
        db.rollback()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_company_cache.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/job_search/company_cache.py tests/job_search/test_company_cache.py
git commit -m "feat: add DB-backed company ATS cache"
```

---

## Task 7: Add in-memory background discovery orchestration (`background_discovery.py`)

**Files:**
- Create: `backend/app/job_search/background_discovery.py`
- Test: `backend/tests/job_search/test_background_discovery.py`

**Interfaces:**
- Consumes: `app.job_search.discovery.detect_company_ats`, `app.job_search.company_cache.save_mapping`, `app.job_search.greenhouse.GreenhouseJobBoardClient.search`, `app.job_search.lever.LeverJobBoardClient.search`, `app.job_search.errors.JobSearchSourceError`, `app.job_search.schemas.SearchCriteria`, `app.job_search.schemas.JobListing`
- Produces:
  - `create_pending_search(user_id: int, has_unknown_companies: bool) -> str` — used by Task 9 (router).
  - `get_discovery_result(search_id: str, user_id: int) -> tuple[bool, list[JobListing]]` — returns `(done, new_listings_since_last_call)`. Used by Task 9 (router).
  - `run_discovery(search_id: str, db_session_factory: Callable[[], Session], unknown_companies: list[str], criteria: SearchCriteria, greenhouse_client: GreenhouseJobBoardClient, lever_client: LeverJobBoardClient) -> None` — the function scheduled via `BackgroundTasks` in Task 9.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/job_search/test_background_discovery.py`:

```python
import httpx
import respx

from app.job_search.background_discovery import create_pending_search, get_discovery_result, run_discovery
from app.job_search.errors import JobSearchSourceError
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.lever import LeverJobBoardClient
from app.job_search.schemas import SearchCriteria
from app.models.company_ats_mapping import CompanyAtsMapping


def test_create_pending_search_with_no_unknown_companies_is_immediately_done():
    search_id = create_pending_search(user_id=1, has_unknown_companies=False)

    done, new_listings = get_discovery_result(search_id, user_id=1)

    assert done is True
    assert new_listings == []


def test_create_pending_search_with_unknown_companies_is_not_done_yet():
    search_id = create_pending_search(user_id=1, has_unknown_companies=True)

    done, _ = get_discovery_result(search_id, user_id=1)

    assert done is False


def test_get_discovery_result_for_unknown_search_id_returns_done_true_empty():
    done, new_listings = get_discovery_result("does-not-exist", user_id=1)

    assert done is True
    assert new_listings == []


def test_get_discovery_result_for_wrong_user_returns_done_true_empty():
    search_id = create_pending_search(user_id=1, has_unknown_companies=True)

    done, new_listings = get_discovery_result(search_id, user_id=2)

    assert done is True
    assert new_listings == []


@respx.mock
def test_run_discovery_saves_confirmed_mapping_and_delivers_listings(db_session):
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Ingénieur backend",
                        "location": {"name": "Paris"},
                        "content": "<p>Poste chez Acme.</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    }
                ]
            },
        )
    )

    search_id = create_pending_search(user_id=1, has_unknown_companies=True)
    run_discovery(
        search_id,
        lambda: db_session,
        ["Acme"],
        SearchCriteria(keywords="backend"),
        GreenhouseJobBoardClient(),
        LeverJobBoardClient(),
    )

    done, new_listings = get_discovery_result(search_id, user_id=1)
    assert done is True
    assert len(new_listings) == 1
    assert new_listings[0].title == "Ingénieur backend"

    mapping = db_session.query(CompanyAtsMapping).filter(CompanyAtsMapping.company_name == "acme").first()
    assert mapping.source == "greenhouse"


@respx.mock
def test_run_discovery_does_not_cache_indeterminate_detection(db_session):
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(side_effect=httpx.ConnectError("down"))
    respx.get("https://api.lever.co/v0/postings/acme").mock(return_value=httpx.Response(404))

    search_id = create_pending_search(user_id=1, has_unknown_companies=True)
    run_discovery(
        search_id,
        lambda: db_session,
        ["Acme"],
        SearchCriteria(keywords="backend"),
        GreenhouseJobBoardClient(),
        LeverJobBoardClient(),
    )

    done, new_listings = get_discovery_result(search_id, user_id=1)
    assert done is True
    assert new_listings == []
    assert db_session.query(CompanyAtsMapping).filter(CompanyAtsMapping.company_name == "acme").first() is None


@respx.mock
def test_run_discovery_continues_after_a_listings_fetch_failure(db_session, monkeypatch):
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(return_value=httpx.Response(200, json={}))
    respx.get("https://boards-api.greenhouse.io/v1/boards/globex/jobs").mock(return_value=httpx.Response(200, json={}))

    greenhouse_client = GreenhouseJobBoardClient()

    original_search = greenhouse_client.search

    def flaky_search(criteria, company_slugs):
        if company_slugs == ["acme"]:
            raise JobSearchSourceError("boom")
        return original_search(criteria, company_slugs)

    monkeypatch.setattr(greenhouse_client, "search", flaky_search)

    search_id = create_pending_search(user_id=1, has_unknown_companies=True)
    run_discovery(
        search_id,
        lambda: db_session,
        ["Acme", "Globex"],
        SearchCriteria(keywords=""),
        greenhouse_client,
        LeverJobBoardClient(),
    )

    done, _ = get_discovery_result(search_id, user_id=1)
    assert done is True
    # Both companies still get their mapping saved despite Acme's listings fetch failing
    names = {
        row.company_name
        for row in db_session.query(CompanyAtsMapping).all()
    }
    assert names == {"acme", "globex"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_background_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.job_search.background_discovery'`

- [ ] **Step 3: Implement `background_discovery.py`**

Create `backend/app/job_search/background_discovery.py`:

```python
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

import httpx
from sqlalchemy.orm import Session

from app.job_search.company_cache import save_mapping
from app.job_search.discovery import detect_company_ats
from app.job_search.errors import JobSearchSourceError
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.lever import LeverJobBoardClient
from app.job_search.schemas import JobListing, SearchCriteria

_STATE_TTL = timedelta(minutes=5)


@dataclass
class _DiscoveryState:
    user_id: int
    done: bool
    new_listings: list[JobListing] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


_lock = threading.Lock()
_state: dict[str, _DiscoveryState] = {}


def _purge_expired() -> None:
    cutoff = datetime.utcnow() - _STATE_TTL
    with _lock:
        expired = [search_id for search_id, entry in _state.items() if entry.created_at < cutoff]
        for search_id in expired:
            del _state[search_id]


def create_pending_search(user_id: int, has_unknown_companies: bool) -> str:
    _purge_expired()
    search_id = secrets.token_urlsafe(16)
    with _lock:
        _state[search_id] = _DiscoveryState(user_id=user_id, done=not has_unknown_companies)
    return search_id


def get_discovery_result(search_id: str, user_id: int) -> tuple[bool, list[JobListing]]:
    _purge_expired()
    with _lock:
        entry = _state.get(search_id)
        if entry is None or entry.user_id != user_id:
            return True, []
        listings, entry.new_listings = entry.new_listings, []
        return entry.done, listings


def run_discovery(
    search_id: str,
    db_session_factory: Callable[[], Session],
    unknown_companies: list[str],
    criteria: SearchCriteria,
    greenhouse_client: GreenhouseJobBoardClient,
    lever_client: LeverJobBoardClient,
) -> None:
    db = db_session_factory()
    http_client = httpx.Client(timeout=10.0)
    try:
        for company_name in unknown_companies:
            result = detect_company_ats(company_name, http_client)
            if not result.confirmed:
                continue

            save_mapping(db, company_name, result.source, result.slug)

            if result.source is None:
                continue

            client = greenhouse_client if result.source == "greenhouse" else lever_client
            try:
                listings = client.search(criteria, [result.slug])
            except JobSearchSourceError:
                continue

            if listings:
                with _lock:
                    entry = _state.get(search_id)
                    if entry is not None:
                        entry.new_listings.extend(listings)
    finally:
        http_client.close()
        db.close()
        with _lock:
            entry = _state.get(search_id)
            if entry is not None:
                entry.done = True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_background_discovery.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/job_search/background_discovery.py tests/job_search/test_background_discovery.py
git commit -m "feat: add in-memory background discovery orchestration"
```

---

## Task 8: Extend the job search response schemas

**Files:**
- Modify: `backend/app/schemas/job_search.py`
- Test: `backend/tests/schemas/test_job_search_schemas.py`

**Interfaces:**
- Produces:
  - `JobSearchResponse` gains `search_id: str` and `discovery_pending: bool`.
  - New `JobSearchDiscoveryResponse(BaseModel)` with `done: bool` and `new_listings: list[JobListing]`.
  - Used by Task 9 (router).

- [ ] **Step 1: Write the failing test**

Check whether `backend/tests/schemas/` exists as a directory:

Run: `cd backend && ls tests/schemas 2>/dev/null || echo "missing"`

If it prints `missing`, create `backend/tests/schemas/__init__.py` as an empty file first.

Create `backend/tests/schemas/test_job_search_schemas.py`:

```python
from app.job_search.schemas import JobListing
from app.schemas.job_search import JobSearchDiscoveryResponse, JobSearchResponse


def test_job_search_response_includes_discovery_fields():
    response = JobSearchResponse(
        listings=[], unavailable_sources=[], search_id="abc123", discovery_pending=True
    )
    assert response.search_id == "abc123"
    assert response.discovery_pending is True


def test_job_search_discovery_response_shape():
    listing = JobListing(
        title="Développeur",
        company="Acme",
        location=None,
        snippet="",
        url="https://example.com/1",
        source="greenhouse",
        ats_type="greenhouse",
    )
    response = JobSearchDiscoveryResponse(done=True, new_listings=[listing])
    assert response.done is True
    assert response.new_listings[0].company == "Acme"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/schemas/test_job_search_schemas.py -v`
Expected: FAIL — `search_id`/`discovery_pending` not accepted, or `JobSearchDiscoveryResponse` doesn't exist.

- [ ] **Step 3: Update the schemas**

Replace the full contents of `backend/app/schemas/job_search.py`:

```python
from pydantic import BaseModel

from app.job_search.schemas import JobListing


class JobSearchResponse(BaseModel):
    listings: list[JobListing]
    unavailable_sources: list[str]
    search_id: str
    discovery_pending: bool


class JobSearchDiscoveryResponse(BaseModel):
    done: bool
    new_listings: list[JobListing]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && ./venv/bin/python -m pytest tests/schemas/test_job_search_schemas.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/schemas/job_search.py tests/schemas/test_job_search_schemas.py
git commit -m "feat: add search_id/discovery_pending to job search response schemas"
```

---

## Task 9: Wire discovery into the job search router

**Files:**
- Modify: `backend/app/routers/job_search.py`
- Test: `backend/tests/routers/test_job_search.py`

**Interfaces:**
- Consumes: everything from Tasks 1–8 (`extract_unique_companies`, `MAX_COMPANIES_PER_DISCOVERY`, `get_cached_mapping`, `create_pending_search`, `run_discovery`, `get_discovery_result`, `JobSearchDiscoveryResponse`).
- Produces: `POST /job-search/search` now returns `search_id`/`discovery_pending` and includes known-company Greenhouse/Lever listings; new `GET /job-search/search/{search_id}/discovery`.

- [ ] **Step 0: Make background tasks usable against the test database**

`run_discovery` (Task 7) opens its own DB session via a factory callable, because
it runs after the request-scoped session (`db: Session = Depends(get_db)`) has
already been closed. In production this factory is `app.database.SessionLocal`.
In tests, `db_session`/`client` (`backend/tests/conftest.py`) point the
*request-scoped* session at an isolated in-memory SQLite engine, but
`SessionLocal` itself is a module-level `sessionmaker` bound to the real
(unreachable in tests) `DATABASE_URL` at import time — rebinding
`database.engine` via `monkeypatch.setattr` does not retroactively change it.
Left as-is, any test that reaches the background-task path would try to open a
real Postgres connection and fail.

Fix this by rebinding `SessionLocal` itself in the `client` fixture, alongside
the existing `engine` rebind. In `backend/tests/conftest.py`, update the
`client` fixture:

```python
@pytest.fixture()
def client(db_session, monkeypatch):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # The app's lifespan calls database.Base.metadata.create_all(bind=database.engine)
    # on startup. Point it at the same isolated in-memory engine db_session uses,
    # instead of the real (unreachable in tests) DATABASE_URL-configured engine.
    monkeypatch.setattr(database, "engine", db_session.get_bind())
    # Background tasks (e.g. app.job_search.background_discovery.run_discovery)
    # can't use the request-scoped db_session/override_get_db above — they run
    # after the response, via their own database.SessionLocal() call. Rebind it
    # to the same in-memory test engine (StaticPool keeps it on the same
    # underlying connection as db_session) so it doesn't try to reach the
    # unused DATABASE_URL from the environment.
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

This only works if the router code looks up `database.SessionLocal` fresh on
each request (via `from app import database` + `database.SessionLocal`)
instead of `from app.database import SessionLocal` — the latter would capture
the original object at import time and never see this monkeypatch. Step 3
below uses the correct form.

Run: `cd backend && ./venv/bin/python -m pytest tests/ -q` (sanity check — should still pass, this step alone changes no behavior yet)
Expected: PASS

- [ ] **Step 1: Update the router test file**

Replace the full contents of `backend/tests/routers/test_job_search.py`:

```python
import httpx
import respx

from app.job_search.dependencies import get_job_search_clients
from app.job_search.errors import JobSearchSourceError
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.lever import LeverJobBoardClient
from app.job_search.schemas import JobListing
from app.main import app
from app.rate_limit.limiter import MAX_SEARCHES_PER_HOUR


def _register_and_login(client, email: str = "jane@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": email, "password": "s3cret!1"})
    return login.json()["access_token"]


class FakeWorkingClient:
    """Used by tests that don't care about company discovery. `company` is
    deliberately blank — extract_unique_companies() skips blank names — so
    these tests never trigger the background discovery path (which would
    otherwise make real, unmocked HTTP calls to Greenhouse/Lever). Tests that
    DO want to exercise discovery use CompanyMentioningClient below."""

    def search(self, criteria):
        return [
            JobListing(
                title="Développeur Python",
                company="",
                location="Paris",
                snippet="...",
                url="https://example.com/1",
                source="fake",
                ats_type=None,
            )
        ]


class CompanyMentioningClient:
    def search(self, criteria):
        return [
            JobListing(
                title="Développeur Python",
                company="Acme",
                location="Paris",
                snippet="...",
                url="https://example.com/1",
                source="fake",
                ats_type=None,
            )
        ]


class FakeFailingClient:
    def search(self, criteria):
        raise JobSearchSourceError("down")


class EmptyGreenhouseOrLeverClient:
    def search(self, criteria, company_slugs):
        return []


class EmptyPrimaryClient:
    def search(self, criteria):
        return []


def _default_clients(overrides: dict[str, object]) -> dict[str, object]:
    base: dict[str, object] = {
        "france_travail": EmptyPrimaryClient(),
        "adzuna": EmptyPrimaryClient(),
        "greenhouse": EmptyGreenhouseOrLeverClient(),
        "lever": EmptyGreenhouseOrLeverClient(),
    }
    base.update(overrides)
    return base


def test_search_returns_listings_and_unavailable_sources(client):
    app.dependency_overrides[get_job_search_clients] = lambda: _default_clients(
        {"france_travail": FakeWorkingClient(), "adzuna": FakeFailingClient()}
    )
    token = _register_and_login(client)

    response = client.post(
        "/job-search/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"keywords": "python"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["listings"]) == 1
    assert body["unavailable_sources"] == ["adzuna"]
    assert "search_id" in body


def test_search_requires_auth(client):
    app.dependency_overrides[get_job_search_clients] = lambda: _default_clients({"france_travail": FakeWorkingClient()})
    response = client.post("/job-search/search", json={"keywords": "python"})
    assert response.status_code == 401


def test_search_rate_limited_after_max_per_hour(client):
    app.dependency_overrides[get_job_search_clients] = lambda: _default_clients({"france_travail": FakeWorkingClient()})
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(MAX_SEARCHES_PER_HOUR):
        response = client.post("/job-search/search", headers=headers, json={"keywords": "python"})
        assert response.status_code == 200

    response = client.post("/job-search/search", headers=headers, json={"keywords": "python"})
    assert response.status_code == 429


def test_search_with_no_companies_in_results_is_not_discovery_pending(client):
    class NoCompanyClient:
        def search(self, criteria):
            return []

    app.dependency_overrides[get_job_search_clients] = lambda: _default_clients({"france_travail": NoCompanyClient()})
    token = _register_and_login(client)

    response = client.post(
        "/job-search/search", headers={"Authorization": f"Bearer {token}"}, json={"keywords": "python"}
    )

    assert response.json()["discovery_pending"] is False


@respx.mock
def test_search_discovers_unknown_company_and_polling_returns_new_listing(client):
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Ingénieur backend",
                        "location": {"name": "Paris"},
                        "content": "<p>Poste Acme.</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    }
                ]
            },
        )
    )

    app.dependency_overrides[get_job_search_clients] = lambda: {
        "france_travail": CompanyMentioningClient(),
        "adzuna": EmptyPrimaryClient(),
        "greenhouse": GreenhouseJobBoardClient(),
        "lever": LeverJobBoardClient(),
    }
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/job-search/search", headers=headers, json={"keywords": "python"})
    assert response.status_code == 200
    body = response.json()
    assert body["discovery_pending"] is True
    search_id = body["search_id"]

    poll = client.get(f"/job-search/search/{search_id}/discovery", headers=headers)
    assert poll.status_code == 200
    poll_body = poll.json()
    assert poll_body["done"] is True
    assert len(poll_body["new_listings"]) == 1
    assert poll_body["new_listings"][0]["title"] == "Ingénieur backend"


def test_get_discovery_for_unknown_search_id_returns_done_true(client):
    app.dependency_overrides[get_job_search_clients] = lambda: _default_clients({"france_travail": FakeWorkingClient()})
    token = _register_and_login(client)

    response = client.get(
        "/job-search/search/does-not-exist/discovery", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == {"done": True, "new_listings": []}


def test_get_discovery_requires_auth(client):
    response = client.get("/job-search/search/some-id/discovery")
    assert response.status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/routers/test_job_search.py -v`
Expected: FAIL — the router doesn't produce `search_id`/`discovery_pending` yet, and `GET /job-search/search/{search_id}/discovery` doesn't exist (404).

- [ ] **Step 3: Update the router**

Replace the full contents of `backend/app/routers/job_search.py`:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import database
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.job_search.aggregator import search_jobs
from app.job_search.background_discovery import create_pending_search, get_discovery_result, run_discovery
from app.job_search.company_cache import get_cached_mapping
from app.job_search.dependencies import get_job_search_clients
from app.job_search.discovery import MAX_COMPANIES_PER_DISCOVERY, extract_unique_companies
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria
from app.models.job_search_request_log import JobSearchRequestLog
from app.models.user import User
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_job_search_rate_limit,
    lock_user_for_rate_limit,
)
from app.schemas.job_search import JobSearchDiscoveryResponse, JobSearchResponse

router = APIRouter(prefix="/job-search", tags=["job_search"])


def _fetch_known_company_listings(
    clients: dict[str, object], criteria: SearchCriteria, source: str, slug: str
) -> list[JobListing]:
    client = clients[source]
    try:
        return client.search(criteria, [slug])
    except JobSearchSourceError:
        return []


@router.post("/search", response_model=JobSearchResponse)
def search(
    criteria: SearchCriteria,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clients: dict[str, object] = Depends(get_job_search_clients),
) -> JobSearchResponse:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_job_search_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    primary_clients = {"france_travail": clients["france_travail"], "adzuna": clients["adzuna"]}
    listings, unavailable_sources = search_jobs(criteria, primary_clients)

    db.add(JobSearchRequestLog(user_id=current_user.id))
    db.commit()

    known_listings: list[JobListing] = []
    unknown_companies: list[str] = []
    for company_name in extract_unique_companies(listings):
        mapping = get_cached_mapping(db, company_name)
        if mapping is None:
            unknown_companies.append(company_name)
        elif mapping.source is not None:
            known_listings.extend(
                _fetch_known_company_listings(clients, criteria, mapping.source, mapping.slug)
            )

    unknown_companies = unknown_companies[:MAX_COMPANIES_PER_DISCOVERY]
    search_id = create_pending_search(current_user.id, has_unknown_companies=bool(unknown_companies))
    if unknown_companies:
        background_tasks.add_task(
            run_discovery,
            search_id,
            # Looked up as database.SessionLocal (not a bare `SessionLocal` name
            # imported at module load) so the test suite's monkeypatch of
            # database.SessionLocal (see tests/conftest.py) takes effect — see
            # Task 9 Step 0 in the implementation plan for why. This attribute
            # access happens now, while handling the request (after any test
            # monkeypatch has already been applied), not at module import time.
            database.SessionLocal,
            unknown_companies,
            criteria,
            clients["greenhouse"],
            clients["lever"],
        )

    return JobSearchResponse(
        listings=listings + known_listings,
        unavailable_sources=unavailable_sources,
        search_id=search_id,
        discovery_pending=bool(unknown_companies),
    )


@router.get("/search/{search_id}/discovery", response_model=JobSearchDiscoveryResponse)
def get_discovery(
    search_id: str,
    current_user: User = Depends(get_current_user),
) -> JobSearchDiscoveryResponse:
    done, new_listings = get_discovery_result(search_id, current_user.id)
    return JobSearchDiscoveryResponse(done=done, new_listings=new_listings)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/routers/test_job_search.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && ./venv/bin/python -m pytest -q`
Expected: PASS, no regressions in unrelated modules (applications, diagnostics, etc.)

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/routers/job_search.py tests/routers/test_job_search.py
git commit -m "feat: serve known companies synchronously and discover unknown ones in the background"
```

---

## Task 10: Remove the manual company field from `SearchCriteriaForm`

**Files:**
- Modify: `frontend/components/SearchCriteriaForm.tsx`
- Test: `frontend/components/SearchCriteriaForm.test.tsx`

**Interfaces:**
- Produces: `SearchCriteriaFormValue` without `followedCompanies`; `toSearchCriteria` no longer sets `followed_companies`.

- [ ] **Step 1: Update the test file**

In `frontend/components/SearchCriteriaForm.test.tsx`, replace the `toSearchCriteria` describe block with:

```typescript
describe("toSearchCriteria", () => {
  it("splits comma-separated exclude keywords into a trimmed array", () => {
    const result = toSearchCriteria({
      ...EMPTY_SEARCH_CRITERIA_FORM_VALUE,
      keywords: "python",
      excludeKeywords: "stage, junior",
    });
    expect(result.exclude_keywords).toEqual(["stage", "junior"]);
  });

  it("omits empty optional fields", () => {
    const result = toSearchCriteria(EMPTY_SEARCH_CRITERIA_FORM_VALUE);
    expect(result.location).toBeUndefined();
    expect(result.contract_type).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run components/SearchCriteriaForm.test.tsx`
Expected: FAIL — TypeScript error, `SearchCriteria`/`SearchCriteriaFormValue` still requires `followedCompanies`/`followed_companies` at this point, and `toSearchCriteria` still emits it (test itself would actually still pass since we didn't assert its absence — this step mainly guards against forgetting to remove usage; proceed to Step 3 regardless).

- [ ] **Step 3: Update the component**

In `frontend/components/SearchCriteriaForm.tsx`:

Remove `followedCompanies: string;` from the `SearchCriteriaFormValue` interface.

Remove `followedCompanies: "",` from `EMPTY_SEARCH_CRITERIA_FORM_VALUE`.

Remove `followed_companies: splitCommaList(value.followedCompanies),` from `toSearchCriteria`.

Remove this entire `<label>` block:

```tsx
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Entreprises à suivre sur Greenhouse/Lever (séparées par des virgules)
        <input
          type="text"
          value={value.followedCompanies}
          onChange={(event) => onChange({ ...value, followedCompanies: event.target.value })}
          placeholder="ex: acme, globex"
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
```

- [ ] **Step 4: Update `lib/types.ts` so `SearchCriteria` no longer requires `followed_companies`**

In `frontend/lib/types.ts`, remove `followed_companies: string[];` from the `SearchCriteria` interface (this is required for Step 3's edit to type-check — see Task 11 for the full follow-up changes to this file).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run components/SearchCriteriaForm.test.tsx`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
cd frontend
git add components/SearchCriteriaForm.tsx components/SearchCriteriaForm.test.tsx lib/types.ts
git commit -m "feat: remove manual followed-companies field from search form"
```

---

## Task 11: Add frontend types and API wrapper for discovery polling

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/api.test.ts`

**Interfaces:**
- Produces:
  - `JobSearchResult` gains `search_id: string` and `discovery_pending: boolean`.
  - New `JobSearchDiscoveryResult { done: boolean; new_listings: JobListing[]; }`.
  - `fetchJobSearchDiscovery(token: string, searchId: string): Promise<JobSearchDiscoveryResult>` — used by Task 12 (`discoveryPolling.ts`).

- [ ] **Step 1: Update the `searchJobs` test to match the new response shape**

In `frontend/lib/api.test.ts`, update the `searchJobs` describe block:

```typescript
describe("searchJobs", () => {
  it("posts criteria to /job-search/search and returns listings", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        listings: [
          {
            title: "Développeur Python",
            company: "Acme",
            location: "Paris",
            snippet: "...",
            url: "https://example.com/1",
            source: "adzuna",
            ats_type: null,
          },
        ],
        unavailable_sources: ["france_travail"],
        search_id: "search-1",
        discovery_pending: false,
      })
    );

    const result = await searchJobs("tok", {
      keywords: "python",
      exclude_keywords: [],
    });

    expect(result.listings).toHaveLength(1);
    expect(result.unavailable_sources).toEqual(["france_travail"]);
    expect(result.search_id).toBe("search-1");
    expect(result.discovery_pending).toBe(false);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/job-search/search");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string).keywords).toBe("python");
  });
});

describe("fetchJobSearchDiscovery", () => {
  it("gets the discovery status and new listings for a search", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        done: true,
        new_listings: [
          {
            title: "Ingénieur backend",
            company: "Acme",
            location: null,
            snippet: "",
            url: "https://example.com/2",
            source: "greenhouse",
            ats_type: "greenhouse",
          },
        ],
      })
    );

    const result = await fetchJobSearchDiscovery("tok", "search-1");

    expect(result.done).toBe(true);
    expect(result.new_listings).toHaveLength(1);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/job-search/search/search-1/discovery");
    expect(init?.method).toBe("GET");
  });
});
```

Also add `fetchJobSearchDiscovery` to the import list at the top of the file (alongside `searchJobs`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: FAIL — `fetchJobSearchDiscovery` doesn't exist; `searchJobs` call site has a TypeScript error for the removed `followed_companies` field being absent (this is fine, it should NOT be passed) or for missing `search_id`/`discovery_pending` in the mocked response type.

- [ ] **Step 3: Update `lib/types.ts`**

In `frontend/lib/types.ts`, update `JobSearchResult` and add `JobSearchDiscoveryResult`:

```typescript
export interface JobSearchResult {
  listings: JobListing[];
  unavailable_sources: string[];
  search_id: string;
  discovery_pending: boolean;
}

export interface JobSearchDiscoveryResult {
  done: boolean;
  new_listings: JobListing[];
}
```

- [ ] **Step 4: Update `lib/api.ts`**

In `frontend/lib/api.ts`, add `JobSearchDiscoveryResult` to the type import at the top of the file, and add this function after `searchJobs`:

```typescript
export function fetchJobSearchDiscovery(token: string, searchId: string): Promise<JobSearchDiscoveryResult> {
  return request<JobSearchDiscoveryResult>(`/job-search/search/${searchId}/discovery`, { method: "GET" }, token);
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd frontend
git add lib/types.ts lib/api.ts lib/api.test.ts
git commit -m "feat: add frontend types and API wrapper for discovery polling"
```

---

## Task 12: Add the `discoveryPolling.ts` helper

**Files:**
- Create: `frontend/lib/discoveryPolling.ts`
- Create: `frontend/lib/discoveryPolling.test.ts`

**Interfaces:**
- Consumes: `fetchJobSearchDiscovery` from `./api` (Task 11).
- Produces: `pollJobSearchDiscovery(token: string, searchId: string, onNewListings: (listings: JobListing[]) => void, onDone: () => void, intervalMs?: number): () => void` — the returned function cancels polling. Used by Task 13 (`app/candidatures/page.tsx`).

- [ ] **Step 1: Write the failing tests**

Create `frontend/lib/discoveryPolling.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { pollJobSearchDiscovery } from "./discoveryPolling";
import * as api from "./api";
import type { JobListing } from "./types";

vi.mock("./api", () => ({
  fetchJobSearchDiscovery: vi.fn(),
}));

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function listing(url: string): JobListing {
  return {
    title: "Ingénieur backend",
    company: "Acme",
    location: null,
    snippet: "",
    url,
    source: "greenhouse",
    ats_type: "greenhouse",
  };
}

describe("pollJobSearchDiscovery", () => {
  it("calls onNewListings for each batch and onDone when finished", async () => {
    vi.mocked(api.fetchJobSearchDiscovery)
      .mockResolvedValueOnce({ done: false, new_listings: [listing("https://example.com/a")] })
      .mockResolvedValueOnce({ done: true, new_listings: [listing("https://example.com/b")] });

    const onNewListings = vi.fn();
    const onDone = vi.fn();

    pollJobSearchDiscovery("tok", "search-1", onNewListings, onDone, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(onNewListings).toHaveBeenNthCalledWith(1, [listing("https://example.com/a")]);
    expect(onDone).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1000);
    expect(onNewListings).toHaveBeenNthCalledWith(2, [listing("https://example.com/b")]);
    expect(onDone).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(5000);
    expect(api.fetchJobSearchDiscovery).toHaveBeenCalledTimes(2);
  });

  it("stops polling and calls onDone when a request fails", async () => {
    vi.mocked(api.fetchJobSearchDiscovery).mockRejectedValue(new Error("network error"));

    const onNewListings = vi.fn();
    const onDone = vi.fn();

    pollJobSearchDiscovery("tok", "search-1", onNewListings, onDone, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onNewListings).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(5000);
    expect(api.fetchJobSearchDiscovery).toHaveBeenCalledTimes(1);
  });

  it("returns a cancel function that stops further polling", async () => {
    vi.mocked(api.fetchJobSearchDiscovery).mockResolvedValue({ done: false, new_listings: [] });

    const cancel = pollJobSearchDiscovery("tok", "search-1", vi.fn(), vi.fn(), 1000);
    cancel();

    await vi.advanceTimersByTimeAsync(5000);
    expect(api.fetchJobSearchDiscovery).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run lib/discoveryPolling.test.ts`
Expected: FAIL with a module resolution error, `./discoveryPolling` doesn't exist.

- [ ] **Step 3: Implement `discoveryPolling.ts`**

Create `frontend/lib/discoveryPolling.ts`:

```typescript
import { fetchJobSearchDiscovery } from "./api";
import type { JobListing } from "./types";

export function pollJobSearchDiscovery(
  token: string,
  searchId: string,
  onNewListings: (listings: JobListing[]) => void,
  onDone: () => void,
  intervalMs: number = 3000
): () => void {
  const intervalId = setInterval(async () => {
    try {
      const result = await fetchJobSearchDiscovery(token, searchId);
      if (result.new_listings.length > 0) onNewListings(result.new_listings);
      if (result.done) {
        clearInterval(intervalId);
        onDone();
      }
    } catch {
      clearInterval(intervalId);
      onDone();
    }
  }, intervalMs);

  return () => clearInterval(intervalId);
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run lib/discoveryPolling.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd frontend
git add lib/discoveryPolling.ts lib/discoveryPolling.test.ts
git commit -m "feat: add job search discovery polling helper"
```

---

## Task 13: Wire progressive polling into the candidatures page

**Files:**
- Modify: `frontend/app/candidatures/page.tsx`

**Interfaces:**
- Consumes: `pollJobSearchDiscovery` (Task 12), `JobSearchResult.search_id`/`discovery_pending` (Task 11).

- [ ] **Step 1: Update the component**

In `frontend/app/candidatures/page.tsx`, add the import:

```tsx
import { pollJobSearchDiscovery } from "@/lib/discoveryPolling";
```

Add `useRef` to the existing `"react"` import:

```tsx
import { useRef, useState } from "react";
```

Inside `CandidaturesPageContent`, add a new piece of state and a ref right after the existing `useState` calls:

```tsx
  const [isDiscovering, setIsDiscovering] = useState(false);
  const cancelPollRef = useRef<(() => void) | null>(null);
```

Update `handleSearch` to start polling when the response says discovery is pending:

```tsx
  async function handleSearch() {
    if (!token) return;
    setBanner(null);
    setIsSearching(true);
    cancelPollRef.current?.();
    setIsDiscovering(false);
    try {
      const result = await searchJobs(token, toSearchCriteria(criteria));
      setSearchResult(result);
      if (result.discovery_pending) {
        setIsDiscovering(true);
        cancelPollRef.current = pollJobSearchDiscovery(
          token,
          result.search_id,
          (newListings) => {
            setSearchResult((prev) => (prev ? { ...prev, listings: [...prev.listings, ...newListings] } : prev));
          },
          () => setIsDiscovering(false)
        );
      }
    } catch (error) {
      if (!handleAuthError(error)) setBanner(toBannerContent(error));
    } finally {
      setIsSearching(false);
    }
  }
```

Add an indicator right after the `SearchCriteriaForm`, before the `banner` block:

```tsx
      {isDiscovering && (
        <p className="mt-3 text-sm text-slate-500">Recherche en cours sur les sites des entreprises...</p>
      )}
```

- [ ] **Step 2: Type-check the frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: PASS, no regressions (page.tsx itself has no dedicated test — see Task 14 for manual verification).

- [ ] **Step 4: Commit**

```bash
cd frontend
git add app/candidatures/page.tsx
git commit -m "feat: poll for newly discovered company offers after a search"
```

---

## Task 14: Full-suite verification and manual smoke test

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && ./venv/bin/python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: all tests pass.

- [ ] **Step 3: Rebuild and restart the stack**

Run: `docker compose up -d --build backend frontend`

- [ ] **Step 4: Manual smoke test**

In the browser, on the `/candidatures` page:
1. Confirm the "Entreprises à suivre sur Greenhouse/Lever" field is gone from the form.
2. Search with keywords that return France Travail/Adzuna results for well-known companies (e.g. a large French tech employer).
3. Confirm results appear immediately, followed a few seconds later by a transient "Recherche en cours sur les sites des entreprises..." message if `discovery_pending` was true, and confirm it disappears once discovery finishes.
4. Re-run the same search a second time and confirm it returns at least as fast (previously-discovered companies are now served from cache without the discovery delay).

- [ ] **Step 5: Report results to the user**

Summarize pass/fail for each step above; do not mark this task done until the manual smoke test has actually been run against the real Greenhouse/Lever APIs (mocked tests alone don't prove real-world slug guesses work).
