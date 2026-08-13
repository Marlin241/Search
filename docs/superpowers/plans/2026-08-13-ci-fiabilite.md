# CI et fiabilité (lint, types, sécurité, tests) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up automated CI (GitHub Actions) and local pre-commit hooks that run tests, lint, type checks, and security/dependency audits on this repo, starting from a genuinely clean baseline (0 ruff errors, 0 mypy errors) rather than a baseline full of pre-existing findings.

**Architecture:** A single `.github/workflows/ci.yml` with two parallel jobs (`backend`, `frontend`). Backend gets a new `pyproject.toml` (ruff + mypy + bandit config) and `requirements-dev.txt` additions (ruff, mypy, bandit, pip-audit, pre-commit). Frontend gets a new `.eslintrc.json` (`next/core-web-vitals` + `next/typescript`) and two new `package.json` scripts (`lint`, `typecheck`). A root `.pre-commit-config.yaml` wires the same backend tools into local pre-commit hooks via `language: system` (reusing `backend/venv`, no separate isolated environment). Getting there requires first fixing ~29 pre-existing mypy errors and ~103 pre-existing ruff findings across the backend — this plan fixes them as real, tested code changes (not config suppressions), verified file-by-file before the CI/pre-commit wiring goes in.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0 (typed `Mapped[...]` models), pydantic v2, ruff 0.16, mypy 2.3, bandit 1.9, pip-audit 2.10, pre-commit 4.6, Next.js 14.2, TypeScript 5.5, ESLint 8.57 + `eslint-config-next`, vitest.

## Global Constraints

- mypy runs in **permissive mode** (no `--strict`, `ignore_missing_imports = true`) — see spec `docs/superpowers/specs/2026-08-13-ci-fiabilite-design.md` §"Configuration Python". Every mypy error fixed in this plan is fixed as real code (annotations, `TYPE_CHECKING` imports, `Protocol`s, `cast`/`assert` narrowing) — never with a blanket `# type: ignore` or a module-level mypy override, so the permissive baseline stays meaningfully enforced from day one.
- `bandit` and `pip-audit` are **non-blocking** at rollout, both in CI (`continue-on-error: true`) and in pre-commit (`|| true` in the hook's `entry`). Flipping them to blocking is an explicit follow-up **not** part of this plan (spec, "Prochaines étapes").
- Every fix must leave `pytest` (314 tests, `backend/`) and `vitest run` (144 tests, `frontend/`) green. Run both after every task that touches application code.
- No behavior changes. Every fix in Tasks 2–7 is a typing/lint fix only — verified against the existing test suite, not new functionality.

---

## Task 1: Backend dev tooling — dependencies and config

**Files:**
- Modify: `backend/requirements-dev.txt`
- Create: `backend/pyproject.toml`

**Interfaces:**
- Produces: `backend/pyproject.toml` with `[tool.ruff]` (target-version py313, excludes `venv`/`.pytest_cache`, `[tool.ruff.lint] ignore = ["B008"]`), `[tool.mypy]` (`ignore_missing_imports = true`, `plugins = ["pydantic.mypy"]`), `[tool.bandit]` (`exclude_dirs = ["tests", "venv"]`). All later tasks assume this file exists with exactly this content.

- [ ] **Step 1: Add dev tooling to `requirements-dev.txt`**

Modify `backend/requirements-dev.txt` to:

```
-r requirements.txt
pytest
respx
pillow
ruff
mypy
bandit
pip-audit
pre-commit
```

- [ ] **Step 2: Install into the existing venv**

Run: `cd backend && source venv/bin/activate && pip install -r requirements-dev.txt`
Expected: ruff, mypy, bandit, pip-audit, pre-commit install without errors (pydantic is already a transitive dependency via `pydantic-settings` in `requirements.txt`, needed for the mypy plugin in Step 3).

- [ ] **Step 3: Create `backend/pyproject.toml`**

```toml
[tool.ruff]
target-version = "py313"
exclude = ["venv", ".pytest_cache"]

[tool.ruff.lint]
ignore = ["B008"]

[tool.mypy]
ignore_missing_imports = true
plugins = ["pydantic.mypy"]

[tool.bandit]
exclude_dirs = ["tests", "venv"]
```

`B008` is ignored because it flags FastAPI's idiomatic `Depends(...)` in argument defaults (56 of the 103 baseline ruff findings) — endorsed by FastAPI's own docs, not a real bug.

- [ ] **Step 4: Verify the config loads and shows the expected (still non-zero) baseline**

Run: `cd backend && source venv/bin/activate && ruff check app --statistics`
Expected: `Found 47 errors` (down from 103 pre-`pyproject.toml`), listing `I001` (17), `RUF012` (12), `DTZ003` (9), `F821` (5), `RUF022` (1), `RUF100` (1), `SIM103` (1), `UP035` (1). These are fixed in Tasks 2–7.

Run: `mypy app`
Expected: `Found 29 errors in 12 files` (down from 38 pre-`pyproject.toml` — the pydantic plugin and `ignore_missing_imports` already resolve `config.py`'s `Settings()` call-arg errors and the boto3/botocore stub warnings for free). These 29 are fixed in Tasks 2–5.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements-dev.txt backend/pyproject.toml
git commit -m "chore(backend): add ruff/mypy/bandit/pip-audit tooling and config"
```

---

## Task 2: Fix mypy — `app/main.py` name collision and model forward references

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/diagnostic.py`
- Modify: `backend/app/models/candidate_profile.py`
- Modify: `backend/app/models/application.py`
- Modify: `backend/app/models/personalized_document.py`

**Interfaces:**
- Consumes: `backend/pyproject.toml` from Task 1.
- Produces: no new symbols; fixes 9 mypy errors in `main.py` (all downstream of one name collision) and 5 `name-defined` errors in the model files (SQLAlchemy `Mapped["ClassName"]` string forward references with no matching import).

- [ ] **Step 1: Fix the `app` name collision in `main.py`**

`import app.models` binds the name `app` (the top-level package) in `main.py`'s namespace; the very next statement, `app = FastAPI(...)`, then reassigns that same name. mypy infers `app`'s type from the *first* binding (`Module`) and flags every later use (`add_middleware`, `include_router` ×6, `get`) as "Module has no attribute ...". Fix: bind a different local name.

In `backend/app/main.py`, change:
```python
import app.models  # noqa: F401 register models on Base
```
to:
```python
from app import models  # noqa: F401 register models on Base
```
(Same import side effect — `app/models/__init__.py` still runs, registering every model on `Base` — just without binding the name `app`.)

- [ ] **Step 2: Verify `main.py` is clean**

Run: `mypy app/main.py`
Expected: no `main.py` errors (mypy will still show unrelated errors from files it transitively imports — ignore those for this step).

- [ ] **Step 3: Add `TYPE_CHECKING` imports to the 5 model files**

Each of these SQLAlchemy models references another model only inside a string forward reference (`Mapped["Diagnostic"]` / `Mapped["User"]`) to avoid a circular import at runtime. mypy can't resolve the string unless the name is *also* importable under `TYPE_CHECKING` (never executed at runtime, so no circularity).

In `backend/app/models/user.py`, add after the existing imports (before `class User(Base):`):
```python
from typing import TYPE_CHECKING
```
(add to the top, alongside `from datetime import datetime`) and:
```python
if TYPE_CHECKING:
    from app.models.diagnostic import Diagnostic
```
right after `from app.database import Base`.

In `backend/app/models/diagnostic.py`, same pattern:
```python
from typing import TYPE_CHECKING
```
and
```python
if TYPE_CHECKING:
    from app.models.user import User
```

In `backend/app/models/candidate_profile.py`, same pattern:
```python
from typing import TYPE_CHECKING
```
and
```python
if TYPE_CHECKING:
    from app.models.user import User
```

In `backend/app/models/application.py`, same pattern:
```python
from typing import TYPE_CHECKING
```
and
```python
if TYPE_CHECKING:
    from app.models.diagnostic import Diagnostic
```

In `backend/app/models/personalized_document.py`, same pattern:
```python
from typing import TYPE_CHECKING
```
and
```python
if TYPE_CHECKING:
    from app.models.diagnostic import Diagnostic
```

- [ ] **Step 4: Verify**

Run: `mypy app/main.py app/models`
Expected: no errors reported for `main.py` or any file under `app/models/`.

Run: `pytest -q`
Expected: `314 passed` (these are pure typing/import additions, no runtime behavior change — `TYPE_CHECKING` blocks never execute).

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/models/user.py backend/app/models/diagnostic.py backend/app/models/candidate_profile.py backend/app/models/application.py backend/app/models/personalized_document.py
git commit -m "fix(backend): resolve mypy name-defined/attr-defined errors in main.py and models"
```

---

## Task 3: Fix mypy — job search client typing (`Protocol`s)

**Files:**
- Modify: `backend/app/job_search/schemas.py`
- Modify: `backend/app/job_search/aggregator.py`
- Modify: `backend/app/job_search/background_discovery.py`
- Modify: `backend/app/routers/job_search.py`

**Interfaces:**
- Consumes: `backend/pyproject.toml` from Task 1.
- Produces: `SearchClient` and `SluggableSearchClient` (both `typing.Protocol`, in `app/job_search/schemas.py`) — later tasks/files that type a job-search client variable use these two names.

`get_job_search_clients()` (`app/job_search/dependencies.py`) returns `dict[str, object]` mixing two genuinely different call shapes: France Travail/Adzuna/La Bonne Alternance clients expose `search(criteria)`, Greenhouse/Lever clients expose `search(criteria, company_slugs)`. This task adds two `Protocol`s (one per shape) and narrows to them with `cast`/local-variable typing at each point a client is pulled out of the dict — the dict itself stays `dict[str, object]` since its values are genuinely heterogeneous.

- [ ] **Step 1: Add the two protocols to `schemas.py`**

In `backend/app/job_search/schemas.py`, change the top import:
```python
from pydantic import BaseModel
```
to:
```python
from typing import Protocol

from pydantic import BaseModel
```

Then append at the end of the file (after the existing `JobListing` class):
```python


class SearchClient(Protocol):
    """Structural type for the France Travail/Adzuna/La Bonne Alternance
    clients: single-criteria search, no company slug."""

    def search(self, criteria: SearchCriteria) -> list[JobListing]: ...


class SluggableSearchClient(Protocol):
    """Structural type for the Greenhouse/Lever clients: search scoped to a
    specific set of company slugs."""

    def search(self, criteria: SearchCriteria, company_slugs: list[str]) -> list[JobListing]: ...
```

- [ ] **Step 2: Type `aggregator.search_jobs`'s `clients` parameter**

In `backend/app/job_search/aggregator.py`, change:
```python
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria
```
to:
```python
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchClient, SearchCriteria
```

Then change:
```python
def search_jobs(criteria: SearchCriteria, clients: dict[str, object]) -> tuple[list[JobListing], list[str]]:
```
to:
```python
def search_jobs(criteria: SearchCriteria, clients: dict[str, SearchClient]) -> tuple[list[JobListing], list[str]]:
```

- [ ] **Step 3: Type `background_discovery.run_discovery`'s client parameters**

`run_discovery` only ever calls `.search(criteria, [slug])` on whichever of `greenhouse_client`/`lever_client` it picks — it never needs the concrete `GreenhouseJobBoardClient`/`LeverJobBoardClient` classes, so retype to the shared Protocol instead.

In `backend/app/job_search/background_discovery.py`, change:
```python
from app.job_search.company_cache import save_mapping
from app.job_search.discovery import detect_company_ats
from app.job_search.errors import JobSearchSourceError
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.lever import LeverJobBoardClient
from app.job_search.schemas import JobListing, SearchCriteria
```
to:
```python
from app.job_search.company_cache import save_mapping
from app.job_search.discovery import detect_company_ats
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria, SluggableSearchClient
```

Then change the `run_discovery` signature:
```python
def run_discovery(
    search_id: str,
    db_session_factory: Callable[[], Session],
    unknown_companies: list[str],
    criteria: SearchCriteria,
    greenhouse_client: GreenhouseJobBoardClient,
    lever_client: LeverJobBoardClient,
) -> None:
```
to:
```python
def run_discovery(
    search_id: str,
    db_session_factory: Callable[[], Session],
    unknown_companies: list[str],
    criteria: SearchCriteria,
    greenhouse_client: SluggableSearchClient,
    lever_client: SluggableSearchClient,
) -> None:
```

Then, inside `run_discovery`'s loop, `result.slug` is `str | None` on the `DetectionResult` dataclass (`app/job_search/discovery.py`) but is only used after `if result.source is None: continue` — by construction (every call site in `discovery.py` sets `source` and `slug` together, never one without the other), `slug` is guaranteed non-`None` at that point, but mypy can't see that invariant across the two independent `Optional` fields. Add an `assert` right there. Change:
```python
            save_mapping(db, company_name, result.source, result.slug)

            if result.source is None:
                continue

            client = greenhouse_client if result.source == "greenhouse" else lever_client
            try:
                listings = client.search(criteria, [result.slug])
```
to:
```python
            save_mapping(db, company_name, result.source, result.slug)

            if result.source is None:
                continue
            assert result.slug is not None  # DetectionResult always sets slug alongside source

            client = greenhouse_client if result.source == "greenhouse" else lever_client
            try:
                listings = client.search(criteria, [result.slug])
```

- [ ] **Step 4: Narrow client types in `routers/job_search.py`**

In `backend/app/routers/job_search.py`, add `cast` to the typing import at the top:
```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
```
to:
```python
from typing import cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
```

Change the schemas import:
```python
from app.job_search.schemas import JobListing, SearchCriteria
```
to:
```python
from app.job_search.schemas import JobListing, SearchClient, SearchCriteria, SluggableSearchClient
```

In `_fetch_known_company_listings`, cast the pulled-out client at the point it's used (keeps the function's own parameter as `dict[str, object]`, matching what callers actually pass):
```python
def _fetch_known_company_listings(
    clients: dict[str, object], criteria: SearchCriteria, source: str, slug: str
) -> list[JobListing]:
    client = clients[source]
    try:
        return client.search(criteria, [slug])
```
to:
```python
def _fetch_known_company_listings(
    clients: dict[str, object], criteria: SearchCriteria, source: str, slug: str
) -> list[JobListing]:
    client = cast(SluggableSearchClient, clients[source])
    try:
        return client.search(criteria, [slug])
```

In `search()`, where `primary_clients` is built for `search_jobs` (Step 2's new parameter type), cast each value:
```python
    primary_clients = {
        "france_travail": clients["france_travail"],
        "adzuna": clients["adzuna"],
        "la_bonne_alternance": clients["la_bonne_alternance"],
    }
```
to:
```python
    primary_clients: dict[str, SearchClient] = {
        "france_travail": cast(SearchClient, clients["france_travail"]),
        "adzuna": cast(SearchClient, clients["adzuna"]),
        "la_bonne_alternance": cast(SearchClient, clients["la_bonne_alternance"]),
    }
```

A few lines later, `mapping.slug` (nullable on the `CompanyAtsMapping` model, same "always set alongside `source`" invariant as Step 3) is passed into `_fetch_known_company_listings`, which expects `str`. Change:
```python
        elif mapping.source is not None:
            known_listings.extend(
                _fetch_known_company_listings(clients, criteria, mapping.source, mapping.slug)
            )
```
to:
```python
        elif mapping.source is not None:
            assert mapping.slug is not None  # CompanyAtsMapping always sets slug alongside source
            known_listings.extend(
                _fetch_known_company_listings(clients, criteria, mapping.source, mapping.slug)
            )
```

Finally, where `clients["greenhouse"]`/`clients["lever"]` are passed to `background_tasks.add_task(run_discovery, ...)` (Step 3's new parameter types), cast both:
```python
            unknown_companies,
            criteria,
            clients["greenhouse"],
            clients["lever"],
        )
```
to:
```python
            unknown_companies,
            criteria,
            cast(SluggableSearchClient, clients["greenhouse"]),
            cast(SluggableSearchClient, clients["lever"]),
        )
```

- [ ] **Step 5: Verify**

Run: `mypy app/job_search app/routers/job_search.py`
Expected: no errors in `app/job_search/schemas.py`, `aggregator.py`, `background_discovery.py`, or `app/routers/job_search.py`.

Run: `pytest -q`
Expected: `314 passed` (pure typing changes — `Protocol`s are structural/erased at runtime, `cast()` is a no-op at runtime, the two new `assert`s only restate an invariant that already held).

- [ ] **Step 6: Commit**

```bash
git add backend/app/job_search/schemas.py backend/app/job_search/aggregator.py backend/app/job_search/background_discovery.py backend/app/routers/job_search.py
git commit -m "fix(backend): type job-search clients with Protocols instead of dict[str, object]"
```

---

## Task 4: Fix mypy — `ats_adapters/base.py` BeautifulSoup typing

**Files:**
- Modify: `backend/app/ats_adapters/base.py`

**Interfaces:**
- Consumes: `backend/pyproject.toml` from Task 1.
- Produces: no new symbols; fixes 5 mypy errors (all in `HtmlFormAdapter.discover_form`), stemming from bs4's `Tag.get(...)` returning `str | AttributeValueList | None` (a list is only realistically possible for multi-valued attributes like `class`, never for `action`/`name`/`type`/`id`/`value` — but mypy doesn't know that, so each read needs an explicit `isinstance` narrowing).

- [ ] **Step 1: Add the `ClassVar` import (also needed by Task 5, added here since this file is already being edited)**

In `backend/app/ats_adapters/base.py`, change:
```python
from urllib.parse import urljoin, urlsplit

import httpx
```
to:
```python
from typing import ClassVar
from urllib.parse import urljoin, urlsplit

import httpx
```

- [ ] **Step 2: Narrow `discover_form`'s bs4 reads**

Change:
```python
        submit_url = urljoin(offer_url, form.get("action") or offer_url)

        hidden_fields: dict[str, str] = {}
        fields: list[FormField] = []

        for tag in form.find_all(["input", "select", "textarea"]):
            name = tag.get("name")
            if not name:
                continue
            tag_type = tag.get("type", "text" if tag.name == "input" else tag.name)

            if tag_type == "hidden":
                hidden_fields[name] = tag.get("value", "")
                continue
            if tag_type == "file":
                continue  # resume/cover letter - handled separately by submit()

            label_tag = form.find("label", attrs={"for": tag.get("id")}) if tag.get("id") else None
            label = label_tag.get_text(strip=True) if label_tag else name
```
to:
```python
        action = form.get("action") or offer_url
        submit_url = urljoin(offer_url, action if isinstance(action, str) else offer_url)

        hidden_fields: dict[str, str] = {}
        fields: list[FormField] = []

        for tag in form.find_all(["input", "select", "textarea"]):
            name = tag.get("name")
            if not isinstance(name, str) or not name:
                continue
            tag_type_raw = tag.get("type", "text" if tag.name == "input" else tag.name)
            tag_type = tag_type_raw if isinstance(tag_type_raw, str) else "text"

            if tag_type == "hidden":
                value_raw = tag.get("value", "")
                hidden_fields[name] = value_raw if isinstance(value_raw, str) else ""
                continue
            if tag_type == "file":
                continue  # resume/cover letter - handled separately by submit()

            tag_id = tag.get("id")
            label_tag = form.find("label", attrs={"for": tag_id}) if isinstance(tag_id, str) and tag_id else None
            label = label_tag.get_text(strip=True) if label_tag else name
```

This resolves all 5 remaining mypy errors in the file: the `urljoin` type-var error and a downstream `DiscoveredForm(submit_url=...)` arg-type error both stemmed from `action`'s unnarrowed type; the `name`-key `dict[str, str]` index/assignment errors and a `_prefill_from_profile(name, ...)` arg-type error stemmed from `name`'s unnarrowed type (fixed once, at the `continue`-guard, and inherited by every later use of `name` including `label`'s fallback branch); `attrs={"for": tag.get("id")}` needed the same narrowing as `name`.

- [ ] **Step 3: Verify**

Run: `mypy app/ats_adapters/base.py`
Expected: no errors.

Run: `pytest -q -k ats_adapters`
Expected: all `ats_adapters` tests pass (pure narrowing — every `isinstance` branch's fallback matches the original implicit behavior: `action`/`name`/`tag_type`/`value`/`tag_id` are always plain strings in practice for these specific HTML attributes, so the fallback branches are unreachable in real usage and existing tests exercise the same code paths as before).

- [ ] **Step 4: Commit**

```bash
git add backend/app/ats_adapters/base.py
git commit -m "fix(backend): narrow bs4 attribute types in HtmlFormAdapter.discover_form"
```

---

## Task 5: Fix mypy — `cv_parser/docx_parser.py` and `routers/applications.py`

**Files:**
- Modify: `backend/app/cv_parser/docx_parser.py`
- Modify: `backend/app/routers/applications.py`

**Interfaces:**
- Consumes: `backend/pyproject.toml` from Task 1.
- Produces: no new symbols; fixes the last 3 mypy errors outside `ats_adapters`/`job_search`/`main.py`/models (already handled in Tasks 2–4).

- [ ] **Step 1: Fix the `docx.api.Document` type annotation**

`python-docx` exposes `docx.Document` as a *factory function* (constructs and returns a `docx.document.Document` instance) — using it as a type annotation is a well-known python-docx gotcha. The real class lives at `docx.document.Document`.

In `backend/app/cv_parser/docx_parser.py`, change:
```python
import io

from docx import Document
from docx.oxml.ns import qn

from app.cv_parser.models import CVParseResult
from app.cv_parser.sections import detect_sections


def _has_multi_column(document: Document) -> bool:
```
to:
```python
import io

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn

from app.cv_parser.models import CVParseResult
from app.cv_parser.sections import detect_sections


def _has_multi_column(document: DocxDocument) -> bool:
```

(`Document` — the factory — is still used unchanged at its call site, `Document(io.BytesIO(file_bytes))`, further down in the same file.)

- [ ] **Step 2: Add narrowing asserts in `routers/applications.py`**

Two call sites query `profile = db.query(CandidateProfile)....first()` (typed `CandidateProfile | None`), then call `missing_required_profile_fields(profile)` and raise a 422 `if missing:`. `missing_required_profile_fields(None)` (see `app/applications/service.py:116-118`) always returns a non-empty list (`["full_name", "phone", "work_authorization"]`), so the 422 branch always fires before `profile` is used again when `profile is None` — but mypy can't see across that function call. Add an `assert` right after each `if missing: raise ...` block.

There are two occurrences of this exact pattern in `backend/app/routers/applications.py` (in `get_prefilled_form` and in `confirm_application` / the submit endpoint). For **each** occurrence, change:
```python
    missing = missing_required_profile_fields(profile)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Complétez votre profil avant de continuer: {', '.join(missing)}",
        )
```
to:
```python
    missing = missing_required_profile_fields(profile)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Complétez votre profil avant de continuer: {', '.join(missing)}",
        )
    assert profile is not None  # missing_required_profile_fields(None) always returns non-empty
```

Use `replace_all`-style editing (both occurrences are byte-identical) or apply the edit twice if your editor requires unique matches — check with `grep -n "missing_required_profile_fields(profile)" backend/app/routers/applications.py` first to confirm you've found both (expect 2 matches).

- [ ] **Step 3: Verify**

Run: `mypy app`
Expected: `Success: no issues found in 84 source files` — this is the last task fixing mypy errors; the backend should now be **fully clean**.

Run: `pytest -q`
Expected: `314 passed`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/cv_parser/docx_parser.py backend/app/routers/applications.py
git commit -m "fix(backend): resolve remaining mypy errors (docx typing, profile narrowing)"
```

---

## Task 6: Fix ruff — deprecated `datetime.utcnow()` (DTZ003)

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/time.py`
- Modify: `backend/app/job_search/background_discovery.py`
- Modify: `backend/app/rate_limit/limiter.py`
- Modify: `backend/app/job_search/company_cache.py`
- Modify: `backend/app/job_search/seed_companies.py`
- Modify: `backend/app/auth/security.py`
- Modify: `backend/app/routers/applications.py`

**Interfaces:**
- Produces: `utcnow() -> datetime` in `app/utils/time.py` — a naive-UTC "now", byte-for-byte equivalent to the deprecated `datetime.utcnow()` it replaces (every `DateTime` column and comparison in this codebase is naive; switching to timezone-aware would break those comparisons, so this is deliberately *not* a timezone migration).

- [ ] **Step 1: Create the shared helper**

Create `backend/app/utils/__init__.py` (empty file).

Create `backend/app/utils/time.py`:
```python
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC "now", matching the deprecated `datetime.utcnow()` this
    replaces byte-for-byte - every `DateTime` column and comparison in this
    codebase stores/expects naive values, so switching to a timezone-aware
    return here would break comparisons against those columns."""
    return datetime.now(UTC).replace(tzinfo=None)
```

- [ ] **Step 2: `background_discovery.py` (2 call sites, one is a `field(default_factory=...)`)**

Change:
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
from app.job_search.schemas import JobListing, SearchCriteria, SluggableSearchClient
```
to:
```python
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.job_search.company_cache import save_mapping
from app.job_search.discovery import detect_company_ats
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria, SluggableSearchClient
from app.utils.time import utcnow
```
(`Callable` moves from `typing` to `collections.abc` at the same time — a separate ruff finding, `UP035`, fixed here since this import block is already being touched; see Task 7 for the rest of the auto-fixable findings.)

Then change:
```python
    new_listings: list[JobListing] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
```
to:
```python
    new_listings: list[JobListing] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)
```

And change:
```python
def _purge_expired() -> None:
    cutoff = datetime.utcnow() - _STATE_TTL
```
to:
```python
def _purge_expired() -> None:
    cutoff = utcnow() - _STATE_TTL
```

- [ ] **Step 3: `rate_limit/limiter.py` (4 identical call sites)**

Change:
```python
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.diagnostic import Diagnostic
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.user import User
```
to:
```python
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.diagnostic import Diagnostic
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.user import User
from app.utils.time import utcnow
```

Then replace all 4 occurrences of:
```python
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
```
with:
```python
    one_hour_ago = utcnow() - timedelta(hours=1)
```
(one in each of `check_rate_limit`, `check_personalization_rate_limit`, `check_job_search_rate_limit`, `check_prefilled_form_rate_limit`).

- [ ] **Step 4: `job_search/company_cache.py`**

`datetime` is only used for this one call in the file — remove the import entirely rather than leaving it unused. Change:
```python
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.job_search.discovery import normalize_company_name
from app.models.company_ats_mapping import CompanyAtsMapping
```
to:
```python
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.job_search.discovery import normalize_company_name
from app.models.company_ats_mapping import CompanyAtsMapping
from app.utils.time import utcnow
```

Then change:
```python
    db.add(CompanyAtsMapping(company_name=normalized, source=source, slug=slug, checked_at=datetime.utcnow()))
```
to:
```python
    db.add(CompanyAtsMapping(company_name=normalized, source=source, slug=slug, checked_at=utcnow()))
```

- [ ] **Step 5: `job_search/seed_companies.py`**

Same "only use in the file" situation. Change:
```python
from datetime import datetime

from sqlalchemy.orm import Session

from app.job_search.company_cache import get_cached_mapping, save_mapping
from app.job_search.discovery import normalize_company_name
```
to:
```python
from sqlalchemy.orm import Session

from app.job_search.company_cache import get_cached_mapping, save_mapping
from app.job_search.discovery import normalize_company_name
from app.utils.time import utcnow
```

Then change:
```python
            mapping.checked_at = datetime.utcnow()
```
to:
```python
            mapping.checked_at = utcnow()
```

- [ ] **Step 6: `auth/security.py`**

Change:
```python
from datetime import datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings
```
to:
```python
from datetime import timedelta

import bcrypt
import jwt

from app.config import get_settings
from app.utils.time import utcnow
```

Then change:
```python
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
```
to:
```python
    expire = utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
```

- [ ] **Step 7: `routers/applications.py`**

`datetime` is only used for this one call in the file. Remove:
```python
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
```
(becomes just `import logging` followed by the `fastapi` import, i.e. delete the `from datetime import datetime` line), and add the new import near the other `app.*` imports — after `from app.storage.dependencies import get_object_storage`:
```python
from app.storage.dependencies import get_object_storage
from app.utils.time import utcnow
```

Then change:
```python
    application.submitted_at = datetime.utcnow()
```
to:
```python
    application.submitted_at = utcnow()
```

- [ ] **Step 8: Verify**

Run: `cd backend && source venv/bin/activate && ruff check app --select DTZ003`
Expected: no output beyond ruff's normal "all clear" (0 `DTZ003` findings).

Run: `pytest -q`
Expected: `314 passed`, and the two `DeprecationWarning: datetime.datetime.utcnow() is deprecated` warnings previously visible in `rate_limit/limiter.py` and `routers/applications.py` test output no longer appear.

- [ ] **Step 9: Commit**

```bash
git add backend/app/utils backend/app/job_search/background_discovery.py backend/app/rate_limit/limiter.py backend/app/job_search/company_cache.py backend/app/job_search/seed_companies.py backend/app/auth/security.py backend/app/routers/applications.py
git commit -m "fix(backend): replace deprecated datetime.utcnow() with a naive-UTC helper"
```

---

## Task 7: Fix ruff — `ClassVar` (RUF012), `SIM103`, and remaining auto-fixes; run `ruff format`

**Files:**
- Modify: `backend/app/ats_adapters/base.py`
- Modify: `backend/app/ats_adapters/greenhouse.py`
- Modify: `backend/app/ats_adapters/lever.py`
- Modify: `backend/app/job_search/aggregator.py`
- Modify: (auto-fixed) up to all files under `backend/app/`

**Interfaces:**
- Consumes: `backend/pyproject.toml` from Task 1; `ClassVar` already imported into `base.py` by Task 4 Step 1.

- [ ] **Step 1: Annotate the mutable class-attribute defaults with `ClassVar`**

`HtmlFormAdapter`'s four class attributes are per-subclass *specialization* constants (each `GreenhouseAdapter`/`LeverAdapter` subclass overrides them wholesale, never mutates them in place) — exactly what `ClassVar` is for. ruff flags plain mutable defaults on a class body because, without the annotation, a bare `dict`/`list` default at class scope is indistinguishable from an (accidental) shared-mutable-instance-state bug.

In `backend/app/ats_adapters/base.py`, change:
```python
    standard_field_aliases: dict[str, list[str]] = {}
    resume_field_names: list[str] = []
    cover_letter_field_names: list[str] = []
    allowed_host_suffixes: list[str] = []
```
to:
```python
    standard_field_aliases: ClassVar[dict[str, list[str]]] = {}
    resume_field_names: ClassVar[list[str]] = []
    cover_letter_field_names: ClassVar[list[str]] = []
    allowed_host_suffixes: ClassVar[list[str]] = []
```

In `backend/app/ats_adapters/greenhouse.py`, change:
```python
from app.ats_adapters.base import HtmlFormAdapter


class GreenhouseAdapter(HtmlFormAdapter):
    standard_field_aliases = {
        "first_name": ["first_name"],
        "last_name": ["last_name"],
        "email": ["email"],
        "phone": ["phone"],
        "linkedin": ["linkedin"],
        "portfolio": ["website", "portfolio"],
    }
    resume_field_names = ["job_application[resume]"]
    cover_letter_field_names = ["job_application[cover_letter]"]
    # Covers the job board hosts (boards.greenhouse.io,
    # job-boards.greenhouse.io) and the submission API host
    # (boards-api.greenhouse.io) alike.
    allowed_host_suffixes = ["greenhouse.io"]
```
to:
```python
from typing import ClassVar

from app.ats_adapters.base import HtmlFormAdapter


class GreenhouseAdapter(HtmlFormAdapter):
    standard_field_aliases: ClassVar[dict[str, list[str]]] = {
        "first_name": ["first_name"],
        "last_name": ["last_name"],
        "email": ["email"],
        "phone": ["phone"],
        "linkedin": ["linkedin"],
        "portfolio": ["website", "portfolio"],
    }
    resume_field_names: ClassVar[list[str]] = ["job_application[resume]"]
    cover_letter_field_names: ClassVar[list[str]] = ["job_application[cover_letter]"]
    # Covers the job board hosts (boards.greenhouse.io,
    # job-boards.greenhouse.io) and the submission API host
    # (boards-api.greenhouse.io) alike.
    allowed_host_suffixes: ClassVar[list[str]] = ["greenhouse.io"]
```

In `backend/app/ats_adapters/lever.py`, change:
```python
from app.ats_adapters.base import HtmlFormAdapter


class LeverAdapter(HtmlFormAdapter):
    standard_field_aliases = {
        "full_name": ["name"],
        "email": ["email"],
        "phone": ["phone"],
        "linkedin": ["linkedin"],
        "portfolio": ["portfolio", "website"],
    }
    resume_field_names = ["resume"]
    cover_letter_field_names = ["coverLetter"]
    allowed_host_suffixes = ["lever.co"]
```
to:
```python
from typing import ClassVar

from app.ats_adapters.base import HtmlFormAdapter


class LeverAdapter(HtmlFormAdapter):
    standard_field_aliases: ClassVar[dict[str, list[str]]] = {
        "full_name": ["name"],
        "email": ["email"],
        "phone": ["phone"],
        "linkedin": ["linkedin"],
        "portfolio": ["portfolio", "website"],
    }
    resume_field_names: ClassVar[list[str]] = ["resume"]
    cover_letter_field_names: ClassVar[list[str]] = ["coverLetter"]
    allowed_host_suffixes: ClassVar[list[str]] = ["lever.co"]
```

- [ ] **Step 2: Fix `SIM103` in `aggregator.py`**

`_passes_filters` ends with an `if ...: return False` immediately followed by `return True` — ruff's `SIM103` suggests inlining that as a single negated return. Change:
```python
def _passes_filters(listing: JobListing, criteria: SearchCriteria) -> bool:
    if criteria.exclude_keywords and _matches_any(
        [listing.title, listing.snippet], criteria.exclude_keywords
    ):
        return False
    if criteria.remote and not _matches_any([listing.location, listing.snippet], REMOTE_INDICATORS):
        return False
    return True
```
to:
```python
def _passes_filters(listing: JobListing, criteria: SearchCriteria) -> bool:
    if criteria.exclude_keywords and _matches_any(
        [listing.title, listing.snippet], criteria.exclude_keywords
    ):
        return False
    return not (criteria.remote and not _matches_any([listing.location, listing.snippet], REMOTE_INDICATORS))
```

(The first early-return guard is untouched; only the second `if ...: return False` / `return True` pair collapses. Logically identical for all three cases: exclude-match — unchanged; `remote` true and no remote match — `not (True and True)` = `False`; `remote` true and a remote match, or `remote` falsy — `not (... and False)` / `not (False and ...)` = `True`.)

- [ ] **Step 3: Auto-fix the remaining mechanical findings**

These three are pure ruff auto-fixes with no manual judgment involved: `I001` (17 occurrences, import sorting), `RUF022` (1, unsorted `__all__` in `app/models/__init__.py`), `RUF100` (1, a `# noqa: F401` in `main.py` that's no longer needed once ruff's rule selection covers it — resolved incidentally by earlier edits, verify it's gone rather than fixing by hand).

Run: `cd backend && source venv/bin/activate && ruff check app --fix`
Expected: `Found 22 errors (20 fixed, ...)` reporting fixes for `I001`/`RUF022`/`RUF100`, leaving only the `RUF012`/`SIM103` findings you just fixed by hand in Steps 1–2 (confirm those now show 0 remaining too — if any residual `RUF012`/`SIM103` shows up, re-check Steps 1–2 were applied to the right file).

- [ ] **Step 4: Run `ruff format` across the whole backend**

The codebase has never been passed through ruff's formatter — this reformats ~42 files (line-wrapping only, no logic changes). This is a separate, purely mechanical step from the fixes above, kept in its own commit so the diff is easy to skim (whitespace-only) versus the preceding logic fixes.

Run: `ruff format app`
Expected: `XX files reformatted, YY files left unchanged`.

- [ ] **Step 5: Verify full backend cleanliness**

Run: `ruff check app`
Expected: `All checks passed!`

Run: `ruff format --check app`
Expected: `NN files already formatted` (no remaining diffs).

Run: `mypy app`
Expected: `Success: no issues found in 84 source files`.

Run: `pytest -q`
Expected: `314 passed` — this confirms the entire backend (Tasks 2–7) is now fully clean under both `ruff check` and `mypy`, with zero test regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/app
git commit -m "style(backend): apply ClassVar annotations, SIM103 fix, ruff auto-fixes, and ruff format"
```

---

## Task 8: Frontend — ESLint config, `tsc` fix, and the two lint findings

**Files:**
- Create: `frontend/.eslintrc.json`
- Modify: `frontend/package.json`
- Modify: `frontend/components/DiagnosticReportView.tsx`
- Modify: `frontend/components/OfferInput.tsx`
- Modify: `frontend/lib/api.test.ts`

**Interfaces:**
- Produces: `npm run lint` and `npm run typecheck` scripts in `frontend/package.json`, used by Task 9's CI workflow.

- [ ] **Step 1: Add ESLint and its Next.js config to `package.json`**

In `frontend/package.json`, change:
```json
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  },
```
to:
```json
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "lint": "eslint . --max-warnings=0",
    "typecheck": "tsc --noEmit"
  },
```

And add to `devDependencies` (alphabetical position, between `autoprefixer` and `jsdom`):
```json
    "eslint": "^8.57.1",
    "eslint-config-next": "^14.2.35",
```
(`14.2.35` matches the installed `next` version — check `npm ls next` if this plan is executed after a `next` upgrade, and adjust to match.)

Run: `cd frontend && npm install`
Expected: installs cleanly, `package-lock.json` updates.

- [ ] **Step 2: Create the ESLint config**

Create `frontend/.eslintrc.json`:
```json
{
  "extends": ["next/core-web-vitals", "next/typescript"]
}
```

- [ ] **Step 3: Run ESLint and fix the two findings it reports**

Run: `npx eslint .`
Expected: 2 errors, both `react/no-unescaped-entities` — a bare `'` inside JSX text (not inside a plain string attribute, where it's fine as-is).

In `frontend/components/DiagnosticReportView.tsx`, change:
```
Correspondance à l'offre
```
to:
```
Correspondance à l&apos;offre
```
(inside the `<p>...</p>` JSX text — do not touch any `'` inside a `"..."` string attribute value elsewhere in the file, e.g. `placeholder="..."`, since `&apos;` is an HTML entity that only decodes inside JSX children, not inside a JS string literal).

In `frontend/components/OfferInput.tsx`, change the JSX text:
```
URL de l'offre
```
to:
```
URL de l&apos;offre
```
Leave the nearby `placeholder="Collez ici le texte de l'offre d'emploi"` attribute untouched — it's a plain string, not JSX text, and was not flagged by ESLint.

- [ ] **Step 4: Verify ESLint is clean**

Run: `npx eslint .`
Expected: no output (0 errors, 0 warnings).

- [ ] **Step 5: Fix the one `tsc --noEmit` finding**

Run: `npx tsc --noEmit`
Expected: 1 error, `lib/api.test.ts(117,...): error TS2352: Conversion of type '{ ok: true; status: number; json: () => Promise<never>; }' to type 'Response' may be a mistake...` — a test-only mock object cast directly to `Response`, missing most of the real interface's properties.

In `frontend/lib/api.test.ts`, change:
```typescript
    vi.mocked(fetch).mockResolvedValue({ ok: true, status: 204, json: async () => { throw new Error("no body"); } } as Response);
```
to:
```typescript
    vi.mocked(fetch).mockResolvedValue({ ok: true, status: 204, json: async () => { throw new Error("no body"); } } as unknown as Response);
```
(Standard "cast through `unknown`" escape hatch for a deliberately-partial test mock — zero runtime change, `as Response` and `as unknown as Response` compile to the same JS.)

- [ ] **Step 6: Verify everything frontend-side is clean**

Run: `npx tsc --noEmit`
Expected: no output.

Run: `npx eslint .`
Expected: no output.

Run: `npx vitest run`
Expected: `Test Files 27 passed (27)`, `Tests 144 passed (144)`.

- [ ] **Step 7: Commit**

```bash
git add frontend/.eslintrc.json frontend/package.json frontend/package-lock.json frontend/components/DiagnosticReportView.tsx frontend/components/OfferInput.tsx frontend/lib/api.test.ts
git commit -m "feat(frontend): add ESLint config, fix the two lint findings and one tsc error"
```

---

## Task 9: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `backend/pyproject.toml`, `backend/requirements-dev.txt` (Task 1); `frontend/package.json` `lint`/`typecheck`/`test` scripts (Task 8). Both must already be green (Tasks 1–8 complete) before this task, or the workflow's first run will fail on pre-existing findings it isn't meant to catch.

- [ ] **Step 1: Create the workflow file**

Create `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: ruff check
        run: ruff check .
      - name: ruff format --check
        run: ruff format --check .
      - name: mypy
        run: mypy app
      - name: bandit (report only, non-blocking)
        run: bandit -r app -c pyproject.toml
        continue-on-error: true
      - name: pip-audit (report only, non-blocking)
        run: pip-audit -r requirements.txt
        continue-on-error: true
      - name: pytest
        run: pytest -q

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json
      - name: Install dependencies
        run: npm ci
      - name: eslint
        run: npm run lint
      - name: tsc --noEmit
        run: npm run typecheck
      - name: vitest
        run: npm test
```

Notes on choices already validated locally:
- No `DATABASE_URL`/`JWT_SECRET`/`ANTHROPIC_API_KEY` secrets are configured — `backend/tests/conftest.py` already sets safe defaults via `os.environ.setdefault(...)` before any test imports the app, and `pytest` uses an isolated in-memory SQLite engine (see `db_session` fixture), never the configured `DATABASE_URL`. No CI secrets are required for this workflow to pass.
- `bandit`/`pip-audit` use `continue-on-error: true` — the step still runs and its output is visible in the job log, but a non-zero exit doesn't fail the job. This is the "avertir d'abord" half of the design; removing `continue-on-error: true` from both steps (once the first report is reviewed) is the documented follow-up, not part of this plan.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow for backend and frontend"
```

(This task's real verification — confirming the workflow actually runs and passes in GitHub Actions — happens in Task 11, after Task 10 lands and everything is pushed together.)

---

## Task 10: pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`

**Interfaces:**
- Consumes: tools installed into `backend/venv` by Task 1 (`ruff`, `mypy`, `bandit`, `pip-audit`, `pre-commit` itself).

- [ ] **Step 1: Create the pre-commit config**

Create `.pre-commit-config.yaml` (repo root):
```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check (backend)
        entry: bash -c 'cd backend && venv/bin/ruff check --fix app'
        language: system
        files: ^backend/
        pass_filenames: false

      - id: ruff-format
        name: ruff format (backend)
        entry: bash -c 'cd backend && venv/bin/ruff format app'
        language: system
        files: ^backend/
        pass_filenames: false

      - id: mypy
        name: mypy (backend)
        entry: bash -c 'cd backend && venv/bin/mypy app'
        language: system
        files: ^backend/
        pass_filenames: false

      - id: bandit
        name: bandit (backend, rapport non bloquant pour l'instant)
        entry: bash -c 'cd backend && venv/bin/bandit -r app -c pyproject.toml || true'
        language: system
        files: ^backend/
        pass_filenames: false
        verbose: true

      - id: pip-audit
        name: pip-audit (backend, rapport non bloquant pour l'instant)
        entry: bash -c 'cd backend && venv/bin/pip-audit -r requirements.txt || true'
        language: system
        files: ^backend/
        pass_filenames: false
        verbose: true
```

`language: system` + `venv/bin/<tool>` (rather than pre-commit's usual isolated per-hook environments) reuses `backend/venv` directly — required here because the `mypy` hook loads the `pydantic.mypy` plugin, which needs the project's actual `pydantic` installation to introspect, not just an empty isolated env with `mypy` alone.

- [ ] **Step 2: Install the hook**

Run: `source backend/venv/bin/activate && pre-commit install`
Expected: `pre-commit installed at .git/hooks/pre-commit`.

- [ ] **Step 3: Verify it blocks a deliberate violation**

Stage all of this plan's changes first (Tasks 1–9 should already be committed individually per their own Step "Commit" — this step is a smoke test of the *hook*, not of the accumulated diff):

```bash
echo "import os" > backend/app/_scratch_violation.py
git add backend/app/_scratch_violation.py
pre-commit run
```
Expected: `ruff check (backend)` reports `Failed` (`files were modified by this hook` — the unused `import os` gets auto-removed by `--fix`, which pre-commit treats as a failure so you notice and re-stage). This confirms the hook stops a commit containing a lint violation.

Clean up the smoke test:
```bash
rm backend/app/_scratch_violation.py
git reset backend/app/_scratch_violation.py 2>/dev/null || true
```

- [ ] **Step 4: Verify it passes cleanly (and shows bandit/pip-audit output) on the real, already-fixed codebase**

```bash
git add -A -- backend frontend .github .pre-commit-config.yaml
pre-commit run
```
Expected: `ruff check`, `ruff format`, `mypy` all `Passed`; `bandit` and `pip-audit` both `Passed` (non-blocking, per Task 1's `pyproject.toml` config and this task's `|| true`) while still printing their full report — review that report now (bandit should show only the 1 pre-existing low-severity `B105` false positive on `france_travail.py`'s OAuth URL constant, plus one `B101` "assert used" finding per `assert` added in Tasks 3 and 5 — expected and consistent with the "non-blocking, review later" design, not a regression to fix in this plan).

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit hooks for ruff/mypy/bandit/pip-audit"
```

---

## Task 11: Push and verify CI end-to-end

**Files:** none (verification-only task).

**Interfaces:** none.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin <branch-name>
```

- [ ] **Step 2: Verify GitHub Actions runs both jobs**

Open the repo's Actions tab (`https://github.com/Marlin241/Search/actions`) and confirm:
- The `CI` workflow triggered on the push.
- `backend` job: `ruff check`, `ruff format --check`, `mypy`, `pytest` all green; `bandit` and `pip-audit` steps show as passed-with-warnings (yellow, not red) if they report anything, per `continue-on-error: true`.
- `frontend` job: `eslint`, `tsc --noEmit`, `vitest` all green.

- [ ] **Step 3: Review the first bandit/pip-audit report**

From the `backend` job's `bandit`/`pip-audit` step logs, confirm the findings match what Task 10 Step 4 showed locally (1 `B105` false positive, a handful of `B101` on the `assert`s added in this plan, 0 `pip-audit` vulnerabilities). Decide whether to accept these as-is or address them — this decision, and flipping `continue-on-error: true` off for both steps in `.github/workflows/ci.yml` (and removing `|| true` from the two hooks in `.pre-commit-config.yaml`), is the explicit follow-up documented in the spec's "Prochaines étapes" and is **out of scope for this plan**.

This is the plan's final task — no commit here, this is verification of the work committed across Tasks 1–10.
