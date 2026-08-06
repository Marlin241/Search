# Automatisation de candidature — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend for sous-projet 2 (automatisation de candidature) per `docs/superpowers/specs/2026-08-06-automatisation-candidature-design.md`: search job offers via official APIs, let the user select which ones to pursue, generate a diagnostic + CV/lettre for each (reusing the existing sous-projet 1/3 pipelines), and either auto-submit (Greenhouse/Lever, via direct HTTP adapters) or hand off to the user in "assisted" mode.

**Architecture:** Three new modules — `app/job_search/` (read-only clients: France Travail, Adzuna, Greenhouse, Lever job board APIs, fanned out by an aggregator), `app/ats_adapters/` (write adapters: Greenhouse/Lever form discovery + LLM-answered custom fields + HTTP submission), `app/applications/` (orchestration: dedup, reuse of the existing diagnostic pipeline against a stored reference CV, and the submit/assisted flow) — plus a new `CandidateProfile` model holding contact info and the parsed reference CV. No new external infra (no browser automation, no scheduler); everything is synchronous request/response like the existing diagnostic and personalization flows.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, `httpx` (already a dependency, used for all new HTTP clients — France Travail, Adzuna, Greenhouse, Lever), `anthropic` SDK (custom-field answering), `respx` (HTTP mocking in tests, already a dev dependency), pytest.

## Global Constraints

- Search sources for V1: France Travail API, Adzuna API, Greenhouse job board API, Lever job board API only — no LinkedIn/Indeed scraping, no search-result scraping of any kind.
- Search runs on-demand/synchronously (no background scheduler, no recurring search).
- Auto-submit is only available for offers with `ats_type` set to `greenhouse` or `lever`, via direct HTTP adapters (no headless browser — Playwright stays out of scope for this plan).
- Selecting offers in search results is a frontend-only, unpersisted action — an `Application` row (and its `Diagnostic`) is only created once the user asks to generate a diagnostic for a specific offer.
- A `Diagnostic` for a job-search offer is generated against `CandidateProfile.cv_text` and its stored structural metadata — never a fresh upload — so `CandidateProfile.cv_text` must be set before any `Application` can be created (422 otherwise).
- Auto-submit is blocked (not silently downgraded) until all of `CandidateProfile`'s required fields (`full_name`, `phone`, `work_authorization`) are filled in.
- Custom form fields are answered by an LLM but are always returned to the user for review before submission — an adapter never submits a field it could not confidently fill; it leaves it blank and marked instead.
- Submission failures never retry automatically (unlike the diagnostic/personalization retry-once pattern) — a failed `Application.status = echec_soumission` is left for the user to see, never silently resubmitted.
- Deduplication: a `(user_id, offer_url)` unique constraint on `Application` — creating a second `Application` for the same URL is rejected before any LLM call.
- `DELETE /diagnostics` (existing RGPD purge) must also bulk-delete the requesting user's `Application` rows, mirroring how it already explicitly deletes `PersonalizedDocument` rows (bulk `.delete()` queries bypass SQLAlchemy ORM cascades and the test suite's SQLite doesn't enforce FK-level `ondelete=CASCADE`, so this cannot be left implicit).
- No third-party user account credentials (LinkedIn, Indeed, Greenhouse, Lever...) are ever stored. France Travail/Adzuna API keys are application-level secrets in `Settings`, exactly like `anthropic_api_key`.

**Implementation note on Greenhouse/Lever markup:** the exact field names and form structure used by the `GreenhouseAdapter`/`LeverAdapter` tasks below are written against each platform's well-documented, generic embed-form conventions (a single `<form>` with named `<input>`/`<select>`/`<textarea>` elements and `<label for=...>` pairing), not against a byte-for-byte capture of a live page — this repo has no network access to verify one. Both adapters are built to be tolerant of exact field-name differences (see the `_STANDARD_FIELD_ALIASES` matching in each), but per the spec's testing section, a real end-to-end submission against one live Greenhouse offer and one live Lever offer is a **mandatory manual step before deploying auto-submit to production** (Task 15's final step) — treat any mismatch found there as a bug in the adapter's field-name table, not a design flaw.

---

### Task 1: Data model — `CandidateProfile`

**Files:**
- Create: `backend/app/models/candidate_profile.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/test_candidate_profile.py`

**Interfaces:**
- Produces: `CandidateProfile` ORM model — fields `id`, `user_id` (unique FK), `full_name: str`, `phone: str`, `address: str | None`, `linkedin_url: str | None`, `portfolio_url: str | None`, `work_authorization: str`, `salary_expectation: str | None`, `cv_text: str | None`, `cv_filename: str | None`, `cv_has_tables: bool | None`, `cv_has_multi_column: bool | None`, `cv_has_images: bool | None`, `cv_detected_sections: list[str] | None`, `created_at`, `updated_at`

- [ ] **Step 1: Write the failing tests**

`backend/tests/models/test_candidate_profile.py`:
```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.candidate_profile import CandidateProfile
from app.models.user import User


def _make_user(db_session) -> User:
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    return user


def test_create_candidate_profile_with_contact_fields(db_session):
    user = _make_user(db_session)

    profile = CandidateProfile(
        user_id=user.id,
        full_name="Jane Doe",
        phone="0612345678",
        work_authorization="Autorisée à travailler en France/UE",
    )
    db_session.add(profile)
    db_session.commit()

    fetched = db_session.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    assert fetched.full_name == "Jane Doe"
    assert fetched.address is None
    assert fetched.cv_text is None
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


def test_cv_fields_store_parsed_reference_cv(db_session):
    user = _make_user(db_session)

    profile = CandidateProfile(
        user_id=user.id,
        full_name="Jane Doe",
        phone="0612345678",
        work_authorization="Autorisée à travailler en France/UE",
        cv_text="Jane Doe\nExpérience...",
        cv_filename="cv.pdf",
        cv_has_tables=False,
        cv_has_multi_column=False,
        cv_has_images=False,
        cv_detected_sections=["experience", "education", "skills"],
    )
    db_session.add(profile)
    db_session.commit()

    fetched = db_session.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    assert fetched.cv_text.startswith("Jane Doe")
    assert fetched.cv_detected_sections == ["experience", "education", "skills"]


def test_unique_constraint_on_user_id(db_session):
    user = _make_user(db_session)
    db_session.add(
        CandidateProfile(user_id=user.id, full_name="Jane", phone="0600000000", work_authorization="FR/UE")
    )
    db_session.commit()

    db_session.add(
        CandidateProfile(user_id=user.id, full_name="Jane 2", phone="0611111111", work_authorization="FR/UE")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/models/test_candidate_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.candidate_profile'`

- [ ] **Step 3: Implement the model**

`backend/app/models/candidate_profile.py`:
```python
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    work_authorization: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    salary_expectation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cv_has_tables: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cv_has_multi_column: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cv_has_images: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cv_detected_sections: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship()
```

Modify `backend/app/models/__init__.py`:
```python
from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.candidate_profile import CandidateProfile

__all__ = [
    "User",
    "Diagnostic",
    "PersonalizedDocument",
    "PersonalizationRequestLog",
    "CandidateProfile",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/models/test_candidate_profile.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/candidate_profile.py backend/app/models/__init__.py backend/tests/models/test_candidate_profile.py
git commit -m "feat: add CandidateProfile model"
```

---

### Task 2: Data model — `Application`

**Files:**
- Create: `backend/app/models/application.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/test_application.py`

**Interfaces:**
- Consumes: `Diagnostic` (existing, `app.models.diagnostic`)
- Produces: `Application` ORM model — fields `id`, `user_id`, `diagnostic_id` (FK, `ondelete=CASCADE`), `offer_url: str`, `source: str`, `company_name: str`, `job_title: str`, `ats_type: str | None`, `status: str`, `error_message: str | None`, `submitted_at: datetime | None`, `created_at`, `updated_at`; unique constraint on `(user_id, offer_url)`
- Produces: status string constants `APPLICATION_STATUS_EN_COURS = "en_cours"`, `APPLICATION_STATUS_SOUMISE_AUTO = "soumise_auto"`, `APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT = "a_soumettre_manuellement"`, `APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE = "soumise_manuelle_confirmee"`, `APPLICATION_STATUS_ECHEC_SOUMISSION = "echec_soumission"`

- [ ] **Step 1: Write the failing tests**

`backend/tests/models/test_application.py`:
```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.application import APPLICATION_STATUS_EN_COURS, Application
from app.models.diagnostic import Diagnostic
from app.models.user import User


def _make_diagnostic(db_session) -> Diagnostic:
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    diagnostic = Diagnostic(
        user_id=user.id,
        cv_text="cv",
        offer_text="offer",
        overall_score=1,
        structural_score=1,
        structural_issues=[],
        semantic_score=1,
        missing_keywords=[],
        recommendations=[],
    )
    db_session.add(diagnostic)
    db_session.commit()
    return diagnostic


def test_create_application_linked_to_diagnostic(db_session):
    diagnostic = _make_diagnostic(db_session)

    application = Application(
        user_id=diagnostic.user_id,
        diagnostic_id=diagnostic.id,
        offer_url="https://boards.greenhouse.io/acme/jobs/123",
        source="greenhouse",
        company_name="Acme",
        job_title="Développeuse Full Stack",
        ats_type="greenhouse",
        status=APPLICATION_STATUS_EN_COURS,
    )
    db_session.add(application)
    db_session.commit()

    fetched = db_session.query(Application).filter(Application.diagnostic_id == diagnostic.id).first()
    assert fetched.status == APPLICATION_STATUS_EN_COURS
    assert fetched.submitted_at is None
    assert fetched.error_message is None


def test_unique_constraint_on_user_id_and_offer_url(db_session):
    diagnostic = _make_diagnostic(db_session)
    db_session.add(
        Application(
            user_id=diagnostic.user_id,
            diagnostic_id=diagnostic.id,
            offer_url="https://example.com/job/1",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            status=APPLICATION_STATUS_EN_COURS,
        )
    )
    db_session.commit()

    diagnostic_2 = _make_diagnostic(db_session)
    db_session.add(
        Application(
            user_id=diagnostic.user_id,
            diagnostic_id=diagnostic_2.id,
            offer_url="https://example.com/job/1",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            status=APPLICATION_STATUS_EN_COURS,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_diagnostic_cascades_to_application(db_session):
    diagnostic = _make_diagnostic(db_session)
    application = Application(
        user_id=diagnostic.user_id,
        diagnostic_id=diagnostic.id,
        offer_url="https://example.com/job/2",
        source="manual",
        company_name="Acme",
        job_title="Dev",
        ats_type=None,
        status=APPLICATION_STATUS_EN_COURS,
    )
    db_session.add(application)
    db_session.commit()
    application_id = application.id

    db_session.delete(diagnostic)
    db_session.commit()

    assert db_session.query(Application).filter(Application.id == application_id).first() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/models/test_application.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.application'`

- [ ] **Step 3: Implement the model**

`backend/app/models/application.py`:
```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

APPLICATION_STATUS_EN_COURS = "en_cours"
APPLICATION_STATUS_SOUMISE_AUTO = "soumise_auto"
APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT = "a_soumettre_manuellement"
APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE = "soumise_manuelle_confirmee"
APPLICATION_STATUS_ECHEC_SOUMISSION = "echec_soumission"


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "offer_url", name="uq_application_user_offer_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostics.id", ondelete="CASCADE"), nullable=False)
    offer_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    ats_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=APPLICATION_STATUS_EN_COURS)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    diagnostic: Mapped["Diagnostic"] = relationship()
```

Note: SQLAlchemy's ORM-level `cascade` isn't declared on `Diagnostic` for `Application` (no `relationship(back_populates=...)` on the `Diagnostic` side) — the cascade in `test_deleting_diagnostic_cascades_to_application` above works because SQLite enforces `ondelete="CASCADE"` at the FK level for a single `db.delete(instance)` call (unlike the bulk `.delete()` queries used by the `DELETE /diagnostics` endpoint, which is why Task 18 must delete `Application` rows explicitly there too).

Modify `backend/app/models/__init__.py`:
```python
from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.candidate_profile import CandidateProfile
from app.models.application import Application

__all__ = [
    "User",
    "Diagnostic",
    "PersonalizedDocument",
    "PersonalizationRequestLog",
    "CandidateProfile",
    "Application",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/models/test_application.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/application.py backend/app/models/__init__.py backend/tests/models/test_application.py
git commit -m "feat: add Application model"
```

---

### Task 3: `CandidateProfile` schemas and router (CRUD + reference CV upload)

**Files:**
- Create: `backend/app/schemas/candidate_profile.py`
- Create: `backend/app/routers/candidate_profile.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/routers/test_candidate_profile.py`

**Interfaces:**
- Consumes: `CandidateProfile` (Task 1), `parse_cv`, `CVParsingError`, `MAX_CV_SIZE_BYTES` (existing, `app.cv_parser.parser`)
- Produces: `CandidateProfileIn(BaseModel)` — `full_name: str`, `phone: str`, `address: str | None`, `linkedin_url: str | None`, `portfolio_url: str | None`, `work_authorization: str`, `salary_expectation: str | None`
- Produces: `CandidateProfileOut(BaseModel)` — same fields plus `cv_filename: str | None`, `has_cv: bool`, `updated_at: datetime`
- Produces: routes `GET /profile`, `PUT /profile`, `POST /profile/cv`, all under `get_current_user`

- [ ] **Step 1: Write the failing tests**

`backend/tests/routers/test_candidate_profile.py`:
```python
import io

from docx import Document

from app.main import app


def _register_and_login(client, email: str = "jane@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": email, "password": "s3cret!1"})
    return login.json()["access_token"]


def _clean_cv_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    document.add_paragraph("Développeuse Full Stack chez Acme, 2020-2022")
    document.add_paragraph("Formation")
    document.add_paragraph("Master Informatique")
    document.add_paragraph("Compétences")
    document.add_paragraph("Python, Docker")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_get_profile_returns_404_when_not_yet_created(client):
    token = _register_and_login(client)
    response = client.get("/profile", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_put_profile_creates_then_updates(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    create = client.put(
        "/profile",
        headers=headers,
        json={
            "full_name": "Jane Doe",
            "phone": "0612345678",
            "work_authorization": "Autorisée à travailler en France/UE",
        },
    )
    assert create.status_code == 200
    assert create.json()["full_name"] == "Jane Doe"
    assert create.json()["has_cv"] is False

    update = client.put(
        "/profile",
        headers=headers,
        json={
            "full_name": "Jane A. Doe",
            "phone": "0612345678",
            "work_authorization": "Autorisée à travailler en France/UE",
            "salary_expectation": "45-55k€",
        },
    )
    assert update.status_code == 200
    assert update.json()["full_name"] == "Jane A. Doe"
    assert update.json()["salary_expectation"] == "45-55k€"

    fetched = client.get("/profile", headers=headers)
    assert fetched.json()["full_name"] == "Jane A. Doe"


def test_upload_cv_parses_and_stores_reference_cv(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/profile",
        headers=headers,
        json={"full_name": "Jane Doe", "phone": "0612345678", "work_authorization": "FR/UE"},
    )

    response = client.post(
        "/profile/cv",
        headers=headers,
        files={
            "cv_file": (
                "cv.docx",
                _clean_cv_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_cv"] is True
    assert body["cv_filename"] == "cv.docx"


def test_upload_cv_rejects_unsupported_format(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/profile",
        headers=headers,
        json={"full_name": "Jane Doe", "phone": "0612345678", "work_authorization": "FR/UE"},
    )

    response = client.post(
        "/profile/cv",
        headers=headers,
        files={"cv_file": ("cv.txt", b"plain text resume", "text/plain")},
    )

    assert response.status_code == 422


def test_upload_cv_before_put_creates_profile_implicitly(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/profile/cv",
        headers=headers,
        files={
            "cv_file": (
                "cv.docx",
                _clean_cv_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["has_cv"] is True
    assert response.json()["full_name"] == ""


def test_profile_endpoints_require_auth(client):
    assert client.get("/profile").status_code == 401
    assert client.put("/profile", json={"full_name": "x", "phone": "x", "work_authorization": "x"}).status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/routers/test_candidate_profile.py -v`
Expected: FAIL with `404 Not Found` at collection time / `ModuleNotFoundError` for `app.routers.candidate_profile` once imported by `main.py` — first confirm it fails, the exact error depends on which step is missing.

- [ ] **Step 3: Implement schemas and router**

`backend/app/schemas/candidate_profile.py`:
```python
from datetime import datetime

from pydantic import BaseModel


class CandidateProfileIn(BaseModel):
    full_name: str
    phone: str
    address: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    work_authorization: str
    salary_expectation: str | None = None


class CandidateProfileOut(BaseModel):
    full_name: str
    phone: str
    address: str | None
    linkedin_url: str | None
    portfolio_url: str | None
    work_authorization: str
    salary_expectation: str | None
    cv_filename: str | None
    has_cv: bool
    updated_at: datetime
```

`backend/app/routers/candidate_profile.py`:
```python
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.cv_parser.parser import MAX_CV_SIZE_BYTES, CVParsingError, parse_cv
from app.database import get_db
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.schemas.candidate_profile import CandidateProfileIn, CandidateProfileOut

router = APIRouter(prefix="/profile", tags=["candidate_profile"])


def _to_out(profile: CandidateProfile) -> CandidateProfileOut:
    return CandidateProfileOut(
        full_name=profile.full_name,
        phone=profile.phone,
        address=profile.address,
        linkedin_url=profile.linkedin_url,
        portfolio_url=profile.portfolio_url,
        work_authorization=profile.work_authorization,
        salary_expectation=profile.salary_expectation,
        cv_filename=profile.cv_filename,
        has_cv=profile.cv_text is not None,
        updated_at=profile.updated_at,
    )


def _get_profile(db: Session, user_id: int) -> CandidateProfile | None:
    return db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()


def _get_or_create_profile(db: Session, user_id: int) -> CandidateProfile:
    profile = _get_profile(db, user_id)
    if profile is None:
        profile = CandidateProfile(user_id=user_id, full_name="", phone="", work_authorization="")
        db.add(profile)
    return profile


@router.get("", response_model=CandidateProfileOut)
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateProfileOut:
    profile = _get_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profil non renseigné.")
    return _to_out(profile)


@router.put("", response_model=CandidateProfileOut)
def upsert_profile(
    payload: CandidateProfileIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateProfileOut:
    profile = _get_or_create_profile(db, current_user.id)
    profile.full_name = payload.full_name
    profile.phone = payload.phone
    profile.address = payload.address
    profile.linkedin_url = payload.linkedin_url
    profile.portfolio_url = payload.portfolio_url
    profile.work_authorization = payload.work_authorization
    profile.salary_expectation = payload.salary_expectation
    db.commit()
    db.refresh(profile)
    return _to_out(profile)


@router.post("/cv", response_model=CandidateProfileOut)
def upload_reference_cv(
    cv_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateProfileOut:
    if cv_file.size is not None and cv_file.size > MAX_CV_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier dépasse la taille maximale autorisée (5 Mo).",
        )

    try:
        cv_bytes = cv_file.file.read()
        parsed = parse_cv(cv_bytes, cv_file.filename or "")
    except CVParsingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    profile = _get_or_create_profile(db, current_user.id)
    profile.cv_text = parsed.text
    profile.cv_filename = cv_file.filename
    profile.cv_has_tables = parsed.has_tables
    profile.cv_has_multi_column = parsed.has_multi_column
    profile.cv_has_images = parsed.has_images
    profile.cv_detected_sections = sorted(parsed.detected_sections)
    db.commit()
    db.refresh(profile)
    return _to_out(profile)
```

Modify `backend/app/main.py`:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app import database
from app.routers import auth, candidate_profile, diagnostics, personalization
import app.models  # noqa: F401 register models on Base

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.Base.metadata.create_all(bind=database.engine)
    yield


app = FastAPI(title="ATS Diagnostic API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(diagnostics.router)
app.include_router(personalization.router)
app.include_router(candidate_profile.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/routers/test_candidate_profile.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/candidate_profile.py backend/app/routers/candidate_profile.py backend/app/main.py backend/tests/routers/test_candidate_profile.py
git commit -m "feat: add candidate profile CRUD and reference CV upload"
```

---

### Task 4: `job_search` schemas and error type

**Files:**
- Create: `backend/app/job_search/__init__.py`
- Create: `backend/app/job_search/schemas.py`
- Create: `backend/app/job_search/errors.py`
- Test: `backend/tests/job_search/__init__.py`
- Test: `backend/tests/job_search/test_schemas.py`

**Interfaces:**
- Produces: `SearchCriteria(BaseModel)` — `keywords: str`, `location: str | None`, `contract_type: str | None`, `remote: bool | None`, `exclude_keywords: list[str] = []`, `followed_companies: list[str] = []`
- Produces: `JobListing(BaseModel)` — `title: str`, `company: str`, `location: str | None`, `snippet: str`, `url: str`, `source: str`, `ats_type: str | None`
- Produces: `JobSearchSourceError(Exception)`

- [ ] **Step 1: Write the failing tests**

`backend/tests/job_search/__init__.py`:
```python
```

`backend/tests/job_search/test_schemas.py`:
```python
from app.job_search.schemas import JobListing, SearchCriteria


def test_search_criteria_defaults():
    criteria = SearchCriteria(keywords="développeur python")
    assert criteria.location is None
    assert criteria.exclude_keywords == []
    assert criteria.followed_companies == []


def test_job_listing_requires_core_fields():
    listing = JobListing(
        title="Développeur Python",
        company="Acme",
        location="Paris",
        snippet="Nous cherchons...",
        url="https://example.com/job/1",
        source="adzuna",
        ats_type=None,
    )
    assert listing.ats_type is None
    assert listing.source == "adzuna"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/job_search/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.job_search'`

- [ ] **Step 3: Implement schemas and error type**

`backend/app/job_search/__init__.py`:
```python
```

`backend/app/job_search/schemas.py`:
```python
from pydantic import BaseModel


class SearchCriteria(BaseModel):
    keywords: str
    location: str | None = None
    contract_type: str | None = None
    remote: bool | None = None
    exclude_keywords: list[str] = []
    followed_companies: list[str] = []


class JobListing(BaseModel):
    title: str
    company: str
    location: str | None
    snippet: str
    url: str
    source: str
    ats_type: str | None
```

`backend/app/job_search/errors.py`:
```python
class JobSearchSourceError(Exception):
    """Raised by a single job_search client when its source is unreachable
    or returns something the client cannot parse. Caught by the aggregator
    (Task 9) to omit just that source from results rather than failing the
    whole search."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/job_search/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/__init__.py backend/app/job_search/schemas.py backend/app/job_search/errors.py backend/tests/job_search/__init__.py backend/tests/job_search/test_schemas.py
git commit -m "feat: add job_search schemas and source error type"
```

---

### Task 5: France Travail client

**Files:**
- Create: `backend/app/job_search/france_travail.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/job_search/test_france_travail.py`

**Interfaces:**
- Consumes: `SearchCriteria`, `JobListing`, `JobSearchSourceError` (Task 4)
- Produces: `FranceTravailClient(client_id: str, client_secret: str, http_client: httpx.Client | None = None)` with `.search(criteria: SearchCriteria) -> list[JobListing]`
- Produces: `Settings.france_travail_client_id: str = ""`, `Settings.france_travail_client_secret: str = ""`

France Travail (ex-Pôle Emploi) exposes a free, public "API Offres d'emploi" at `api.francetravail.io`, authenticated via OAuth2 client-credentials against `entreprise.pole-emploi.fr`. Field names below (`resultats`, `intitule`, `entreprise.nom`, `lieuTravail.libelle`, `origineOffre.urlOrigine`) follow the documented v2 response shape; this client has not been run against the live API from this environment, so **verify field names against the current francetravail.io documentation before relying on this in production** — a mismatch here fails closed (an empty/malformed field, not a crash), since every field access below uses `.get(...)` with a safe default.

- [ ] **Step 1: Write the failing tests**

`backend/tests/job_search/test_france_travail.py`:
```python
import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.france_travail import TOKEN_URL, SEARCH_URL, FranceTravailClient
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 1499}))
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "resultats": [
                    {
                        "intitule": "Développeur Python",
                        "entreprise": {"nom": "Acme"},
                        "lieuTravail": {"libelle": "Paris"},
                        "description": "Nous recherchons un développeur Python expérimenté.",
                        "origineOffre": {"urlOrigine": "https://candidat.francetravail.fr/offres/123"},
                    }
                ]
            },
        )
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    listings = client.search(SearchCriteria(keywords="python"))

    assert len(listings) == 1
    assert listings[0].title == "Développeur Python"
    assert listings[0].company == "Acme"
    assert listings[0].source == "france_travail"
    assert listings[0].ats_type is None


@respx.mock
def test_search_raises_on_auth_failure():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))

    client = FranceTravailClient(client_id="bad", client_secret="bad")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_search_failure():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok123"}))
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(500))

    client = FranceTravailClient(client_id="id", client_secret="secret")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_invalid_json():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok123"}))
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text="not json"))

    client = FranceTravailClient(client_id="id", client_secret="secret")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/job_search/test_france_travail.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.job_search.france_travail'`

- [ ] **Step 3: Implement the client**

`backend/app/job_search/france_travail.py`:
```python
import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria

TOKEN_URL = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


class FranceTravailClient:
    def __init__(self, client_id: str, client_secret: str, http_client: httpx.Client | None = None):
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http_client or httpx.Client(timeout=10.0)

    def _get_access_token(self) -> str:
        try:
            response = self._http.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": "api_offresdemploiv2 o2dsoffre",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(f"France Travail: échec de l'authentification: {exc}") from exc

        try:
            return response.json()["access_token"]
        except (ValueError, KeyError) as exc:
            raise JobSearchSourceError("France Travail: réponse d'authentification invalide.") from exc

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        # No token caching in this version: search is on-demand and
        # rate-limited (Task 9), so re-authenticating on every call trades a
        # small amount of latency for not having to manage token expiry.
        token = self._get_access_token()

        params: dict[str, str] = {"motsCles": criteria.keywords}
        if criteria.location:
            params["commune"] = criteria.location
        if criteria.contract_type:
            params["typeContrat"] = criteria.contract_type

        try:
            response = self._http.get(SEARCH_URL, params=params, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(f"France Travail: échec de la recherche: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise JobSearchSourceError("France Travail: réponse invalide (pas du JSON).") from exc

        return [
            JobListing(
                title=offre.get("intitule", ""),
                company=(offre.get("entreprise") or {}).get("nom", ""),
                location=(offre.get("lieuTravail") or {}).get("libelle"),
                snippet=(offre.get("description") or "")[:500],
                url=(offre.get("origineOffre") or {}).get("urlOrigine", ""),
                source="france_travail",
                ats_type=None,
            )
            for offre in payload.get("resultats", [])
        ]
```

Modify `backend/app/config.py`:
```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    anthropic_api_key: str
    cors_origins: list[str] = ["http://localhost:3000"]
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "personalization"
    france_travail_client_id: str = ""
    france_travail_client_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Defaults are empty strings (not required) so the existing test suite and any developer machine without France Travail credentials configured keeps working; `FranceTravailClient.search` called with empty credentials will simply fail with a `JobSearchSourceError` at the auth step in production, which the aggregator (Task 9) already treats as "source unavailable" rather than crashing the whole search.

Modify `backend/.env.example` (append):
```
FRANCE_TRAVAIL_CLIENT_ID=
FRANCE_TRAVAIL_CLIENT_SECRET=
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/job_search/test_france_travail.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/france_travail.py backend/app/config.py backend/.env.example backend/tests/job_search/test_france_travail.py
git commit -m "feat: add France Travail job search client"
```

---

### Task 6: Adzuna client

**Files:**
- Create: `backend/app/job_search/adzuna.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/job_search/test_adzuna.py`

**Interfaces:**
- Consumes: `SearchCriteria`, `JobListing`, `JobSearchSourceError` (Task 4)
- Produces: `AdzunaClient(app_id: str, app_key: str, country: str = "fr", http_client: httpx.Client | None = None)` with `.search(criteria: SearchCriteria) -> list[JobListing]`
- Produces: `Settings.adzuna_app_id: str = ""`, `Settings.adzuna_app_key: str = ""`, `Settings.adzuna_country: str = "fr"`

Same verification caveat as Task 5: field names (`results`, `company.display_name`, `location.display_name`, `redirect_url`) follow Adzuna's documented public API shape but have not been exercised against the live service from this environment.

- [ ] **Step 1: Write the failing tests**

`backend/tests/job_search/test_adzuna.py`:
```python
import httpx
import pytest
import respx

from app.job_search.adzuna import AdzunaClient
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import SearchCriteria

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/1"


@respx.mock
def test_search_returns_normalized_listings():
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Développeur Python",
                        "company": {"display_name": "Acme"},
                        "location": {"display_name": "Paris"},
                        "description": "Nous recherchons...",
                        "redirect_url": "https://www.adzuna.fr/land/ad/123",
                    }
                ]
            },
        )
    )

    client = AdzunaClient(app_id="id", app_key="key")
    listings = client.search(SearchCriteria(keywords="python"))

    assert len(listings) == 1
    assert listings[0].company == "Acme"
    assert listings[0].source == "adzuna"


@respx.mock
def test_search_raises_on_http_error():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(403))

    client = AdzunaClient(app_id="bad", app_key="bad")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_invalid_json():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text="not json"))

    client = AdzunaClient(app_id="id", app_key="key")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/job_search/test_adzuna.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.job_search.adzuna'`

- [ ] **Step 3: Implement the client**

`backend/app/job_search/adzuna.py`:
```python
import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria


class AdzunaClient:
    def __init__(self, app_id: str, app_key: str, country: str = "fr", http_client: httpx.Client | None = None):
        self._app_id = app_id
        self._app_key = app_key
        self._country = country
        self._http = http_client or httpx.Client(timeout=10.0)

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        url = f"https://api.adzuna.com/v1/api/jobs/{self._country}/search/1"
        params = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "what": criteria.keywords,
            "content-type": "application/json",
        }
        if criteria.location:
            params["where"] = criteria.location

        try:
            response = self._http.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(f"Adzuna: échec de la recherche: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise JobSearchSourceError("Adzuna: réponse invalide (pas du JSON).") from exc

        return [
            JobListing(
                title=result.get("title", ""),
                company=(result.get("company") or {}).get("display_name", ""),
                location=(result.get("location") or {}).get("display_name"),
                snippet=(result.get("description") or "")[:500],
                url=result.get("redirect_url", ""),
                source="adzuna",
                ats_type=None,
            )
            for result in payload.get("results", [])
        ]
```

Modify `backend/app/config.py` — add three fields to `Settings`, right after `france_travail_client_secret`:
```python
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = "fr"
```

Modify `backend/.env.example` (append):
```
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
ADZUNA_COUNTRY=fr
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/job_search/test_adzuna.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/adzuna.py backend/app/config.py backend/.env.example backend/tests/job_search/test_adzuna.py
git commit -m "feat: add Adzuna job search client"
```

---

### Task 7: Greenhouse job board listing client

**Files:**
- Create: `backend/app/job_search/greenhouse.py`
- Test: `backend/tests/job_search/test_greenhouse.py`

**Interfaces:**
- Consumes: `SearchCriteria`, `JobListing`, `JobSearchSourceError` (Task 4)
- Produces: `GreenhouseJobBoardClient(http_client: httpx.Client | None = None)` with `.search(criteria: SearchCriteria) -> list[JobListing]` — searches only `criteria.followed_companies` (Greenhouse's public job board API has no cross-company keyword search)

`criteria.keywords` is applied as a simple case-insensitive substring filter on the job title (Greenhouse's board API returns a company's full job list, not a filtered one). If a followed company's board request fails, this client raises immediately (stop-fast) rather than trying to continue with the remaining companies — the aggregator (Task 9) then marks all of Greenhouse unavailable for that search. A single mistyped company slug is a user configuration error to notice and fix, not a case to build partial-failure handling for in V1.

- [ ] **Step 1: Write the failing tests**

`backend/tests/job_search/test_greenhouse.py`:
```python
import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings_for_followed_companies():
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
    listings = client.search(SearchCriteria(keywords="python", followed_companies=["acme"]))

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
    listings = client.search(SearchCriteria(keywords="", followed_companies=["acme"]))

    assert len(listings) == 1


@respx.mock
def test_search_raises_on_http_error():
    respx.get("https://boards-api.greenhouse.io/v1/boards/unknown-co/jobs").mock(return_value=httpx.Response(404))

    client = GreenhouseJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python", followed_companies=["unknown-co"]))


def test_search_with_no_followed_companies_returns_empty_list():
    client = GreenhouseJobBoardClient()
    assert client.search(SearchCriteria(keywords="python", followed_companies=[])) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/job_search/test_greenhouse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.job_search.greenhouse'`

- [ ] **Step 3: Implement the client**

`backend/app/job_search/greenhouse.py`:
```python
import httpx
from bs4 import BeautifulSoup

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria


def _strip_html(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


class GreenhouseJobBoardClient:
    def __init__(self, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(timeout=10.0)

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        listings: list[JobListing] = []
        keyword = criteria.keywords.lower()

        for company_slug in criteria.followed_companies:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
            try:
                response = self._http.get(url, params={"content": "true"})
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise JobSearchSourceError(f"Greenhouse ({company_slug}): échec de la recherche: {exc}") from exc

            try:
                payload = response.json()
            except ValueError as exc:
                raise JobSearchSourceError(f"Greenhouse ({company_slug}): réponse invalide (pas du JSON).") from exc

            for job in payload.get("jobs", []):
                title = job.get("title", "")
                if keyword and keyword not in title.lower():
                    continue
                listings.append(
                    JobListing(
                        title=title,
                        company=company_slug,
                        location=(job.get("location") or {}).get("name"),
                        snippet=_strip_html(job.get("content", ""))[:500],
                        url=job.get("absolute_url", ""),
                        source="greenhouse",
                        ats_type="greenhouse",
                    )
                )
        return listings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/job_search/test_greenhouse.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/greenhouse.py backend/tests/job_search/test_greenhouse.py
git commit -m "feat: add Greenhouse job board listing client"
```

---

### Task 8: Lever job board listing client

**Files:**
- Create: `backend/app/job_search/lever.py`
- Test: `backend/tests/job_search/test_lever.py`

**Interfaces:**
- Consumes: `SearchCriteria`, `JobListing`, `JobSearchSourceError` (Task 4)
- Produces: `LeverJobBoardClient(http_client: httpx.Client | None = None)` with `.search(criteria: SearchCriteria) -> list[JobListing]` — same followed-companies-only, stop-fast-on-error shape as `GreenhouseJobBoardClient` (Task 7), Lever's public postings API has no cross-company keyword search either

- [ ] **Step 1: Write the failing tests**

`backend/tests/job_search/test_lever.py`:
```python
import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.lever import LeverJobBoardClient
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings_for_followed_companies():
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
    listings = client.search(SearchCriteria(keywords="python", followed_companies=["acme"]))

    assert len(listings) == 1
    assert listings[0].title == "Développeur Python"
    assert listings[0].ats_type == "lever"
    assert listings[0].location == "Paris"


@respx.mock
def test_search_raises_on_http_error():
    respx.get("https://api.lever.co/v0/postings/unknown-co").mock(return_value=httpx.Response(404))

    client = LeverJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python", followed_companies=["unknown-co"]))


def test_search_with_no_followed_companies_returns_empty_list():
    client = LeverJobBoardClient()
    assert client.search(SearchCriteria(keywords="python", followed_companies=[])) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/job_search/test_lever.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.job_search.lever'`

- [ ] **Step 3: Implement the client**

`backend/app/job_search/lever.py`:
```python
import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria


class LeverJobBoardClient:
    def __init__(self, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(timeout=10.0)

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        listings: list[JobListing] = []
        keyword = criteria.keywords.lower()

        for company_slug in criteria.followed_companies:
            url = f"https://api.lever.co/v0/postings/{company_slug}"
            try:
                response = self._http.get(url, params={"mode": "json"})
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise JobSearchSourceError(f"Lever ({company_slug}): échec de la recherche: {exc}") from exc

            try:
                postings = response.json()
            except ValueError as exc:
                raise JobSearchSourceError(f"Lever ({company_slug}): réponse invalide (pas du JSON).") from exc

            for posting in postings:
                title = posting.get("text", "")
                if keyword and keyword not in title.lower():
                    continue
                categories = posting.get("categories") or {}
                listings.append(
                    JobListing(
                        title=title,
                        company=company_slug,
                        location=categories.get("location"),
                        snippet=(posting.get("descriptionPlain") or "")[:500],
                        url=posting.get("hostedUrl", ""),
                        source="lever",
                        ats_type="lever",
                    )
                )
        return listings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/job_search/test_lever.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/lever.py backend/tests/job_search/test_lever.py
git commit -m "feat: add Lever job board listing client"
```

---

### Task 9: Search aggregator, rate limit, and router

**Files:**
- Create: `backend/app/models/job_search_request_log.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/job_search/aggregator.py`
- Create: `backend/app/job_search/dependencies.py`
- Modify: `backend/app/rate_limit/limiter.py`
- Create: `backend/app/schemas/job_search.py`
- Create: `backend/app/routers/job_search.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/models/test_job_search_request_log.py`
- Test: `backend/tests/job_search/test_aggregator.py`
- Test: `backend/tests/rate_limit/test_limiter.py`
- Test: `backend/tests/routers/test_job_search.py`

**Interfaces:**
- Consumes: `SearchCriteria`, `JobListing`, `JobSearchSourceError` (Task 4); `FranceTravailClient` (Task 5); `AdzunaClient` (Task 6); `GreenhouseJobBoardClient` (Task 7); `LeverJobBoardClient` (Task 8)
- Produces: `JobSearchRequestLog` ORM model — `id`, `user_id`, `created_at`
- Produces: `MAX_SEARCHES_PER_HOUR: int`, `check_job_search_rate_limit(db: Session, user_id: int) -> None` (raises `RateLimitExceeded`)
- Produces: `search_jobs(criteria: SearchCriteria, clients: dict[str, object]) -> tuple[list[JobListing], list[str]]` (listings, unavailable source names) — each client in `clients` must expose `.search(criteria) -> list[JobListing]`
- Produces: `get_job_search_clients() -> dict[str, object]` (lru_cached dependency provider, keys `"france_travail"`, `"adzuna"`, `"greenhouse"`, `"lever"`)
- Produces: `JobSearchResponse(BaseModel)` — `listings: list[JobListing]`, `unavailable_sources: list[str]`
- Produces: route `POST /job-search/search`, body = `SearchCriteria`, under `get_current_user`

- [ ] **Step 1: Write the failing tests**

`backend/tests/models/test_job_search_request_log.py`:
```python
from app.models.job_search_request_log import JobSearchRequestLog
from app.models.user import User


def test_create_job_search_request_log_linked_to_user(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(JobSearchRequestLog(user_id=user.id))
    db_session.commit()

    fetched = db_session.query(JobSearchRequestLog).filter(JobSearchRequestLog.user_id == user.id).first()
    assert fetched.created_at is not None
```

`backend/tests/job_search/test_aggregator.py`:
```python
import pytest

from app.job_search.aggregator import search_jobs
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria

_LISTING = JobListing(
    title="Développeur Python",
    company="Acme",
    location="Paris",
    snippet="...",
    url="https://example.com/1",
    source="fake",
    ats_type=None,
)


class WorkingClient:
    def search(self, criteria):
        return [_LISTING]


class FailingClient:
    def search(self, criteria):
        raise JobSearchSourceError("boom")


def test_search_jobs_merges_results_from_all_sources():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python"), {"source_a": WorkingClient(), "source_b": WorkingClient()}
    )
    assert len(listings) == 2
    assert unavailable == []


def test_search_jobs_omits_failing_source_without_failing_the_whole_search():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python"), {"source_a": WorkingClient(), "source_b": FailingClient()}
    )
    assert len(listings) == 1
    assert unavailable == ["source_b"]


def test_search_jobs_with_all_sources_failing_returns_empty_listings():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python"), {"source_a": FailingClient(), "source_b": FailingClient()}
    )
    assert listings == []
    assert set(unavailable) == {"source_a", "source_b"}
```

Append to `backend/tests/rate_limit/test_limiter.py`:
```python
from app.models.job_search_request_log import JobSearchRequestLog
from app.rate_limit.limiter import MAX_SEARCHES_PER_HOUR, check_job_search_rate_limit


def _add_job_search_logs(db_session, user_id: int, count: int) -> None:
    for _ in range(count):
        db_session.add(JobSearchRequestLog(user_id=user_id))
    db_session.commit()


def test_job_search_allows_under_limit(db_session):
    user = _make_user(db_session)
    _add_job_search_logs(db_session, user.id, MAX_SEARCHES_PER_HOUR - 1)
    check_job_search_rate_limit(db_session, user.id)  # should not raise


def test_job_search_blocks_at_limit(db_session):
    user = _make_user(db_session)
    _add_job_search_logs(db_session, user.id, MAX_SEARCHES_PER_HOUR)
    import pytest

    with pytest.raises(RateLimitExceeded):
        check_job_search_rate_limit(db_session, user.id)
```

`backend/tests/routers/test_job_search.py`:
```python
from app.job_search.dependencies import get_job_search_clients
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing
from app.main import app
from app.rate_limit.limiter import MAX_SEARCHES_PER_HOUR


def _register_and_login(client, email: str = "jane@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": email, "password": "s3cret!1"})
    return login.json()["access_token"]


class FakeWorkingClient:
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


def test_search_returns_listings_and_unavailable_sources(client):
    app.dependency_overrides[get_job_search_clients] = lambda: {
        "france_travail": FakeWorkingClient(),
        "adzuna": FakeFailingClient(),
    }
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


def test_search_requires_auth(client):
    app.dependency_overrides[get_job_search_clients] = lambda: {"france_travail": FakeWorkingClient()}
    response = client.post("/job-search/search", json={"keywords": "python"})
    assert response.status_code == 401


def test_search_rate_limited_after_max_per_hour(client):
    app.dependency_overrides[get_job_search_clients] = lambda: {"france_travail": FakeWorkingClient()}
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(MAX_SEARCHES_PER_HOUR):
        response = client.post("/job-search/search", headers=headers, json={"keywords": "python"})
        assert response.status_code == 200

    response = client.post("/job-search/search", headers=headers, json={"keywords": "python"})
    assert response.status_code == 429
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/models/test_job_search_request_log.py tests/job_search/test_aggregator.py tests/rate_limit/test_limiter.py tests/routers/test_job_search.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.job_search_request_log'`

- [ ] **Step 3: Implement everything**

`backend/app/models/job_search_request_log.py`:
```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobSearchRequestLog(Base):
    """Append-only log of job searches, used only to enforce the search
    rate limit (app.rate_limit.limiter.check_job_search_rate_limit) — this
    protects France Travail/Adzuna's free-tier quotas, independently of the
    diagnostic/personalization LLM-cost rate limits."""

    __tablename__ = "job_search_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

Modify `backend/app/models/__init__.py`:
```python
from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.candidate_profile import CandidateProfile
from app.models.application import Application
from app.models.job_search_request_log import JobSearchRequestLog

__all__ = [
    "User",
    "Diagnostic",
    "PersonalizedDocument",
    "PersonalizationRequestLog",
    "CandidateProfile",
    "Application",
    "JobSearchRequestLog",
]
```

`backend/app/job_search/aggregator.py`:
```python
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria


def search_jobs(criteria: SearchCriteria, clients: dict[str, object]) -> tuple[list[JobListing], list[str]]:
    listings: list[JobListing] = []
    unavailable_sources: list[str] = []
    for source_name, source_client in clients.items():
        try:
            listings.extend(source_client.search(criteria))
        except JobSearchSourceError:
            unavailable_sources.append(source_name)
    return listings, unavailable_sources
```

`backend/app/job_search/dependencies.py`:
```python
from functools import lru_cache

from app.config import get_settings
from app.job_search.adzuna import AdzunaClient
from app.job_search.france_travail import FranceTravailClient
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.lever import LeverJobBoardClient


@lru_cache
def get_job_search_clients() -> dict[str, object]:
    settings = get_settings()
    return {
        "france_travail": FranceTravailClient(
            client_id=settings.france_travail_client_id,
            client_secret=settings.france_travail_client_secret,
        ),
        "adzuna": AdzunaClient(
            app_id=settings.adzuna_app_id,
            app_key=settings.adzuna_app_key,
            country=settings.adzuna_country,
        ),
        "greenhouse": GreenhouseJobBoardClient(),
        "lever": LeverJobBoardClient(),
    }
```

Modify `backend/app/rate_limit/limiter.py` — append (the file already has `MAX_DIAGNOSTICS_PER_HOUR`, `MAX_PERSONALIZATIONS_PER_HOUR`, `check_rate_limit`, `check_personalization_rate_limit`, `lock_user_for_rate_limit`, `RateLimitExceeded`):
```python
from app.models.job_search_request_log import JobSearchRequestLog

MAX_SEARCHES_PER_HOUR = 20


def check_job_search_rate_limit(db: Session, user_id: int) -> None:
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count()).select_from(JobSearchRequestLog).where(
            JobSearchRequestLog.user_id == user_id,
            JobSearchRequestLog.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_SEARCHES_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_SEARCHES_PER_HOUR} recherches par heure atteinte. Réessaie plus tard."
        )
```
(`Session`, `datetime`, `timedelta`, `select`, `func` are already imported at the top of this file by the existing code — no new imports needed beyond `JobSearchRequestLog`.)

`backend/app/schemas/job_search.py`:
```python
from pydantic import BaseModel

from app.job_search.schemas import JobListing


class JobSearchResponse(BaseModel):
    listings: list[JobListing]
    unavailable_sources: list[str]
```

`backend/app/routers/job_search.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.job_search.aggregator import search_jobs
from app.job_search.dependencies import get_job_search_clients
from app.job_search.schemas import SearchCriteria
from app.models.job_search_request_log import JobSearchRequestLog
from app.models.user import User
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_job_search_rate_limit,
    lock_user_for_rate_limit,
)
from app.schemas.job_search import JobSearchResponse

router = APIRouter(prefix="/job-search", tags=["job_search"])


@router.post("/search", response_model=JobSearchResponse)
def search(
    criteria: SearchCriteria,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clients: dict[str, object] = Depends(get_job_search_clients),
) -> JobSearchResponse:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_job_search_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    listings, unavailable_sources = search_jobs(criteria, clients)

    db.add(JobSearchRequestLog(user_id=current_user.id))
    db.commit()

    return JobSearchResponse(listings=listings, unavailable_sources=unavailable_sources)
```

Modify `backend/app/main.py`:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app import database
from app.routers import auth, candidate_profile, diagnostics, job_search, personalization
import app.models  # noqa: F401 register models on Base

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.Base.metadata.create_all(bind=database.engine)
    yield


app = FastAPI(title="ATS Diagnostic API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(diagnostics.router)
app.include_router(personalization.router)
app.include_router(candidate_profile.router)
app.include_router(job_search.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/models/test_job_search_request_log.py tests/job_search/test_aggregator.py tests/rate_limit/test_limiter.py tests/routers/test_job_search.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/job_search_request_log.py backend/app/models/__init__.py backend/app/job_search/aggregator.py backend/app/job_search/dependencies.py backend/app/rate_limit/limiter.py backend/app/schemas/job_search.py backend/app/routers/job_search.py backend/app/main.py backend/tests/models/test_job_search_request_log.py backend/tests/job_search/test_aggregator.py backend/tests/rate_limit/test_limiter.py backend/tests/routers/test_job_search.py
git commit -m "feat: add job search aggregator, rate limit, and endpoint"
```

---

### Task 10: Applications service — create from a selected offer

**Files:**
- Create: `backend/app/applications/__init__.py`
- Create: `backend/app/applications/service.py`
- Test: `backend/tests/applications/__init__.py`
- Test: `backend/tests/applications/test_service.py`

**Interfaces:**
- Consumes: `Application`, `APPLICATION_STATUS_EN_COURS` (Task 2); `CandidateProfile` (Task 1); `get_offer_text`, `OfferIngestionError` (existing, `app.offer_ingestion.ingestion`); `evaluate_structure` (existing, `app.rules_engine.rules`); `CVParseResult` (existing, `app.cv_parser.models`); `build_diagnostic_report` (existing, `app.aggregator.aggregator`); `SemanticAnalyzer`, `LLMAnalysisError` (existing, `app.llm_analyzer.analyzer`); `Diagnostic` (existing, `app.models.diagnostic`)
- Produces: `ApplicationCreationError(Exception)`, `DuplicateApplicationError(ApplicationCreationError)`, `MissingReferenceCvError(ApplicationCreationError)`
- Produces: `create_application(db: Session, user_id: int, offer_url: str, offer_text_override: str | None, source: str, company_name: str, job_title: str, ats_type: str | None, analyzer: SemanticAnalyzer) -> Application`

Dedup and the reference-CV check both happen **before** the offer is fetched and **before** the LLM is called, so a duplicate or unconfigured-profile request never costs a network call or an LLM call.

- [ ] **Step 1: Write the failing tests**

`backend/tests/applications/__init__.py`:
```python
```

`backend/tests/applications/test_service.py`:
```python
import pytest

from app.applications.service import (
    ApplicationCreationError,
    DuplicateApplicationError,
    MissingReferenceCvError,
    create_application,
)
from app.llm_analyzer.analyzer import LLMAnalysisError, SemanticReport
from app.models.application import Application
from app.models.candidate_profile import CandidateProfile
from app.models.diagnostic import Diagnostic
from app.models.user import User


class FakeAnalyzer:
    def __init__(self, report=None, error=None):
        self._report = report or SemanticReport(score=70, missing_keywords=["Docker"], recommendations=["Add Docker"])
        self._error = error
        self.calls = 0

    def analyze(self, cv_text, offer_text):
        self.calls += 1
        if self._error:
            raise self._error
        return self._report


def _make_user_with_profile(db_session, cv_text: str = "Jane Doe\nExpérience\nDéveloppeuse") -> User:
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    profile = CandidateProfile(
        user_id=user.id,
        full_name="Jane Doe",
        phone="0600000000",
        work_authorization="FR/UE",
        cv_text=cv_text,
        cv_has_tables=False,
        cv_has_multi_column=False,
        cv_has_images=False,
        cv_detected_sections=["experience"],
    )
    db_session.add(profile)
    db_session.commit()
    return user


def test_create_application_success(db_session):
    user = _make_user_with_profile(db_session)
    analyzer = FakeAnalyzer()

    application = create_application(
        db_session,
        user_id=user.id,
        offer_url="https://example.com/job/1",
        offer_text_override="Nous recherchons un développeur Python avec Docker.",
        source="manual",
        company_name="Acme",
        job_title="Développeur Python",
        ats_type=None,
        analyzer=analyzer,
    )

    assert application.status == "en_cours"
    assert application.offer_url == "https://example.com/job/1"
    diagnostic = db_session.query(Diagnostic).filter(Diagnostic.id == application.diagnostic_id).first()
    assert diagnostic is not None
    assert diagnostic.cv_text.startswith("Jane Doe")
    assert diagnostic.missing_keywords == ["Docker"]
    assert analyzer.calls == 1


def test_create_application_raises_without_reference_cv(db_session):
    user = User(email="noprofile@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    with pytest.raises(MissingReferenceCvError):
        create_application(
            db_session,
            user_id=user.id,
            offer_url="https://example.com/job/1",
            offer_text_override="Offre.",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            analyzer=FakeAnalyzer(),
        )


def test_create_application_raises_on_duplicate_offer_url(db_session):
    user = _make_user_with_profile(db_session)
    analyzer = FakeAnalyzer()
    create_application(
        db_session,
        user_id=user.id,
        offer_url="https://example.com/job/1",
        offer_text_override="Offre.",
        source="manual",
        company_name="Acme",
        job_title="Dev",
        ats_type=None,
        analyzer=analyzer,
    )

    with pytest.raises(DuplicateApplicationError):
        create_application(
            db_session,
            user_id=user.id,
            offer_url="https://example.com/job/1",
            offer_text_override="Offre.",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            analyzer=analyzer,
        )
    assert analyzer.calls == 1  # second attempt never reached the LLM call


def test_create_application_wraps_llm_analysis_error_and_does_not_persist(db_session):
    user = _make_user_with_profile(db_session)
    analyzer = FakeAnalyzer(error=LLMAnalysisError("boom"))

    with pytest.raises(ApplicationCreationError):
        create_application(
            db_session,
            user_id=user.id,
            offer_url="https://example.com/job/1",
            offer_text_override="Offre.",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            analyzer=analyzer,
        )
    assert db_session.query(Application).count() == 0
    assert db_session.query(Diagnostic).count() == 0


def test_create_application_wraps_offer_ingestion_error(db_session):
    user = _make_user_with_profile(db_session)

    with pytest.raises(ApplicationCreationError):
        create_application(
            db_session,
            user_id=user.id,
            offer_url="file:///etc/passwd",  # rejected by scrape_offer's URL validation, no network call
            offer_text_override=None,
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            analyzer=FakeAnalyzer(),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/applications/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.applications'`

- [ ] **Step 3: Implement the service**

`backend/app/applications/__init__.py`:
```python
```

`backend/app/applications/service.py`:
```python
from sqlalchemy.orm import Session

from app.aggregator.aggregator import build_diagnostic_report
from app.cv_parser.models import CVParseResult
from app.llm_analyzer.analyzer import LLMAnalysisError, SemanticAnalyzer
from app.models.application import APPLICATION_STATUS_EN_COURS, Application
from app.models.candidate_profile import CandidateProfile
from app.models.diagnostic import Diagnostic
from app.offer_ingestion.ingestion import OfferIngestionError, get_offer_text
from app.rules_engine.rules import evaluate_structure


class ApplicationCreationError(Exception):
    pass


class DuplicateApplicationError(ApplicationCreationError):
    pass


class MissingReferenceCvError(ApplicationCreationError):
    pass


def create_application(
    db: Session,
    user_id: int,
    offer_url: str,
    offer_text_override: str | None,
    source: str,
    company_name: str,
    job_title: str,
    ats_type: str | None,
    analyzer: SemanticAnalyzer,
) -> Application:
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if profile is None or not profile.cv_text:
        raise MissingReferenceCvError(
            "Merci d'uploader votre CV de référence sur votre profil avant de lancer une candidature."
        )

    existing = (
        db.query(Application)
        .filter(Application.user_id == user_id, Application.offer_url == offer_url)
        .first()
    )
    if existing is not None:
        raise DuplicateApplicationError("Vous avez déjà une candidature enregistrée pour cette offre.")

    try:
        offer_text = get_offer_text(offer_text_override, offer_url)
    except OfferIngestionError as exc:
        raise ApplicationCreationError(str(exc)) from exc

    parse_result = CVParseResult(
        text=profile.cv_text,
        has_tables=bool(profile.cv_has_tables),
        has_multi_column=bool(profile.cv_has_multi_column),
        has_images=bool(profile.cv_has_images),
        detected_sections=set(profile.cv_detected_sections or []),
    )
    structural = evaluate_structure(parse_result)

    try:
        semantic = analyzer.analyze(profile.cv_text, offer_text)
    except LLMAnalysisError as exc:
        raise ApplicationCreationError(str(exc)) from exc

    report = build_diagnostic_report(structural, semantic)

    diagnostic = Diagnostic(
        user_id=user_id,
        cv_text=profile.cv_text,
        offer_text=offer_text,
        overall_score=report.overall_score,
        structural_score=report.structural_score,
        structural_issues=report.structural_issues,
        semantic_score=report.semantic_score,
        missing_keywords=report.missing_keywords,
        recommendations=report.recommendations,
    )
    db.add(diagnostic)
    db.flush()  # assigns diagnostic.id without committing, so Application can reference it

    application = Application(
        user_id=user_id,
        diagnostic_id=diagnostic.id,
        offer_url=offer_url,
        source=source,
        company_name=company_name,
        job_title=job_title,
        ats_type=ats_type,
        status=APPLICATION_STATUS_EN_COURS,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/applications/test_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/applications/__init__.py backend/app/applications/service.py backend/tests/applications/__init__.py backend/tests/applications/test_service.py
git commit -m "feat: add applications service to create diagnostics from selected offers"
```

---

### Task 11: Applications router — create, list, get

**Files:**
- Create: `backend/app/schemas/application.py`
- Create: `backend/app/routers/applications.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/routers/test_applications.py`

**Interfaces:**
- Consumes: `create_application`, `ApplicationCreationError`, `DuplicateApplicationError`, `MissingReferenceCvError` (Task 10); `Application` (Task 2); `check_rate_limit`, `lock_user_for_rate_limit`, `RateLimitExceeded` (existing, `app.rate_limit.limiter` — the same diagnostic-creation limit from sous-projet 1, reused as-is: a job-search-triggered diagnostic is still a diagnostic and consumes the same hourly quota, no separate counter)
- Produces: `ApplicationCreateIn(BaseModel)` — `offer_url: str`, `offer_text: str | None = None`, `source: str`, `company_name: str`, `job_title: str`, `ats_type: str | None = None`
- Produces: `ApplicationOut(BaseModel)` — `id: int`, `diagnostic_id: int`, `offer_url: str`, `source: str`, `company_name: str`, `job_title: str`, `ats_type: str | None`, `status: str`, `error_message: str | None`, `submitted_at: datetime | None`, `created_at: datetime`, `updated_at: datetime`
- Produces: routes `POST /applications`, `GET /applications`, `GET /applications/{id}`, all under `get_current_user`

Reusing `check_rate_limit`/`lock_user_for_rate_limit` here (rather than adding a new counter) means the existing `MAX_DIAGNOSTICS_PER_HOUR` limit from sous-projet 1 now also bounds how many `Application`s a user can create per hour — an intentional simplification: both paths ultimately create one `Diagnostic` row, so one shared quota protects the same LLM cost regardless of which flow triggered it.

- [ ] **Step 1: Write the failing tests**

`backend/tests/routers/test_applications.py`:
```python
from app.llm_analyzer.analyzer import SemanticReport
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.main import app
from app.rate_limit.limiter import MAX_DIAGNOSTICS_PER_HOUR


class FakeAnalyzer:
    def analyze(self, cv_text, offer_text):
        return SemanticReport(score=70, missing_keywords=["Docker"], recommendations=["Add Docker"])


def _register_and_login(client, email: str = "jane@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": email, "password": "s3cret!1"})
    return login.json()["access_token"]


def _setup_profile(client, headers: dict) -> None:
    client.put(
        "/profile",
        headers=headers,
        json={"full_name": "Jane Doe", "phone": "0600000000", "work_authorization": "FR/UE"},
    )
    import io

    from docx import Document

    document = Document()
    document.add_paragraph("Expérience")
    document.add_paragraph("Développeuse Python")
    buffer = io.BytesIO()
    document.save(buffer)
    client.post(
        "/profile/cv",
        headers=headers,
        files={
            "cv_file": (
                "cv.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )


def test_create_list_and_get_application(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile(client, headers)

    create = client.post(
        "/applications",
        headers=headers,
        json={
            "offer_url": "https://example.com/job/1",
            "offer_text": "Nous recherchons un développeur Python avec Docker.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Développeur Python",
        },
    )
    assert create.status_code == 201
    body = create.json()
    assert body["status"] == "en_cours"
    application_id = body["id"]

    listing = client.get("/applications", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    detail = client.get(f"/applications/{application_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["company_name"] == "Acme"


def test_create_application_without_profile_cv_returns_422(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/applications",
        headers=headers,
        json={
            "offer_url": "https://example.com/job/1",
            "offer_text": "Offre.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Dev",
        },
    )
    assert response.status_code == 422


def test_create_duplicate_application_returns_409(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile(client, headers)

    payload = {
        "offer_url": "https://example.com/job/1",
        "offer_text": "Offre.",
        "source": "manual",
        "company_name": "Acme",
        "job_title": "Dev",
    }
    first = client.post("/applications", headers=headers, json=payload)
    assert first.status_code == 201

    second = client.post("/applications", headers=headers, json=payload)
    assert second.status_code == 409


def test_get_application_not_owned_returns_404(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    owner_token = _register_and_login(client, "owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    _setup_profile(client, owner_headers)
    created = client.post(
        "/applications",
        headers=owner_headers,
        json={
            "offer_url": "https://example.com/job/1",
            "offer_text": "Offre.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Dev",
        },
    )
    application_id = created.json()["id"]

    attacker_token = _register_and_login(client, "attacker@example.com")
    attacker_headers = {"Authorization": f"Bearer {attacker_token}"}
    response = client.get(f"/applications/{application_id}", headers=attacker_headers)
    assert response.status_code == 404


def test_create_application_rate_limited_after_max_per_hour(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile(client, headers)

    for i in range(MAX_DIAGNOSTICS_PER_HOUR):
        response = client.post(
            "/applications",
            headers=headers,
            json={
                "offer_url": f"https://example.com/job/{i}",
                "offer_text": "Offre.",
                "source": "manual",
                "company_name": "Acme",
                "job_title": "Dev",
            },
        )
        assert response.status_code == 201

    response = client.post(
        "/applications",
        headers=headers,
        json={
            "offer_url": "https://example.com/job/last",
            "offer_text": "Offre.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Dev",
        },
    )
    assert response.status_code == 429
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/routers/test_applications.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.routers.applications'`

- [ ] **Step 3: Implement schemas and router**

`backend/app/schemas/application.py`:
```python
from datetime import datetime

from pydantic import BaseModel


class ApplicationCreateIn(BaseModel):
    offer_url: str
    offer_text: str | None = None
    source: str
    company_name: str
    job_title: str
    ats_type: str | None = None


class ApplicationOut(BaseModel):
    id: int
    diagnostic_id: int
    offer_url: str
    source: str
    company_name: str
    job_title: str
    ats_type: str | None
    status: str
    error_message: str | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

`backend/app/routers/applications.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.applications.service import (
    ApplicationCreationError,
    DuplicateApplicationError,
    MissingReferenceCvError,
    create_application,
)
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.llm_analyzer.analyzer import SemanticAnalyzer
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.models.application import Application
from app.models.user import User
from app.rate_limit.limiter import RateLimitExceeded, check_rate_limit, lock_user_for_rate_limit
from app.schemas.application import ApplicationCreateIn, ApplicationOut

router = APIRouter(prefix="/applications", tags=["applications"])


def _to_out(application: Application) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        diagnostic_id=application.diagnostic_id,
        offer_url=application.offer_url,
        source=application.source,
        company_name=application.company_name,
        job_title=application.job_title,
        ats_type=application.ats_type,
        status=application.status,
        error_message=application.error_message,
        submitted_at=application.submitted_at,
        created_at=application.created_at,
        updated_at=application.updated_at,
    )


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create(
    payload: ApplicationCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analyzer: SemanticAnalyzer = Depends(get_semantic_analyzer),
) -> ApplicationOut:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    try:
        application = create_application(
            db,
            user_id=current_user.id,
            offer_url=payload.offer_url,
            offer_text_override=payload.offer_text,
            source=payload.source,
            company_name=payload.company_name,
            job_title=payload.job_title,
            ats_type=payload.ats_type,
            analyzer=analyzer,
        )
    except MissingReferenceCvError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except DuplicateApplicationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ApplicationCreationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return _to_out(application)


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ApplicationOut]:
    applications = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return [_to_out(a) for a in applications]


def get_owned_application(db: Session, application_id: int, user_id: int) -> Application:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == user_id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature introuvable.")
    return application


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationOut:
    return _to_out(get_owned_application(db, application_id, current_user.id))
```

`get_owned_application` is a module-level function (not prefixed `_`) because Task 17 imports it directly to reuse the same ownership check for the prefilled-form/submit/mark-sent-manually endpoints it adds to this router.

Modify `backend/app/main.py` — add `applications` to the `app.routers` import and `app.include_router(applications.router)` alongside the other routers:
```python
from app.routers import auth, applications, candidate_profile, diagnostics, job_search, personalization
```
```python
app.include_router(applications.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/routers/test_applications.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/application.py backend/app/routers/applications.py backend/app/main.py backend/tests/routers/test_applications.py
git commit -m "feat: add applications create/list/get endpoints"
```

---

### Task 12: `ats_adapters` schemas, errors, and generic HTML form adapter base

**Files:**
- Create: `backend/app/ats_adapters/__init__.py`
- Create: `backend/app/ats_adapters/schemas.py`
- Create: `backend/app/ats_adapters/errors.py`
- Create: `backend/app/ats_adapters/base.py`
- Test: `backend/tests/ats_adapters/__init__.py`
- Test: `backend/tests/ats_adapters/test_base.py`

**Interfaces:**
- Consumes: `CandidateProfile` (Task 1)
- Produces: `FormField(BaseModel)` — `name: str`, `label: str`, `field_type: str`, `required: bool`, `options: list[str] | None = None`, `value: str | None = None`, `is_custom: bool = False`
- Produces: `DiscoveredForm(BaseModel)` — `submit_url: str`, `fields: list[FormField]`, `hidden_fields: dict[str, str] = {}`
- Produces: `ATSAdapterError(Exception)`
- Produces: `HtmlFormAdapter` base class — subclasses set `standard_field_aliases: dict[str, list[str]]`, `resume_field_names: list[str]`, `cover_letter_field_names: list[str]`; exposes `.discover_form(offer_url: str, profile: CandidateProfile, email: str) -> DiscoveredForm` and `.submit(filled_form: DiscoveredForm, cv_pdf: bytes, lettre_pdf: bytes) -> None`

Greenhouse and Lever both embed a single standard HTML `<form>` on their application page — this base class parses that form generically (splitting hidden fields, file inputs, and remaining fields into "standard" vs "custom" via a per-platform alias table) and posts a multipart submission back to it. `GreenhouseAdapter`/`LeverAdapter` (Tasks 14/15) are thin subclasses that only supply their platform's field-name aliases.

- [ ] **Step 1: Write the failing tests**

`backend/tests/ats_adapters/__init__.py`:
```python
```

`backend/tests/ats_adapters/test_base.py`:
```python
import httpx
import pytest
import respx

from app.ats_adapters.base import HtmlFormAdapter
from app.ats_adapters.errors import ATSAdapterError
from app.ats_adapters.schemas import DiscoveredForm, FormField
from app.models.candidate_profile import CandidateProfile

_SAMPLE_FORM_HTML = """
<html><body>
<form action="/submit" method="post">
  <input type="hidden" name="csrf_token" value="tok-abc" />
  <label for="fname">First name</label>
  <input type="text" name="first_name" id="fname" required />
  <label for="lname">Last name</label>
  <input type="text" name="last_name" id="lname" />
  <label for="email_field">Email</label>
  <input type="email" name="email" id="email_field" required />
  <input type="file" name="resume" />
  <label for="why">Why this role?</label>
  <textarea name="custom_why" id="why"></textarea>
</form>
</body></html>
"""


class _TestAdapter(HtmlFormAdapter):
    standard_field_aliases = {
        "first_name": ["first_name"],
        "last_name": ["last_name"],
        "email": ["email"],
    }
    resume_field_names = ["resume"]
    cover_letter_field_names = ["cover_letter"]


def _profile() -> CandidateProfile:
    return CandidateProfile(user_id=1, full_name="Jane Doe", phone="0600000000", work_authorization="FR/UE")


@respx.mock
def test_discover_form_splits_standard_and_custom_fields():
    respx.get("https://example.com/apply").mock(return_value=httpx.Response(200, text=_SAMPLE_FORM_HTML))

    form = _TestAdapter().discover_form("https://example.com/apply", _profile(), email="jane@example.com")

    assert form.submit_url == "https://example.com/submit"
    assert form.hidden_fields == {"csrf_token": "tok-abc"}
    field_names = {f.name for f in form.fields}
    assert field_names == {"first_name", "last_name", "email", "custom_why"}
    assert "resume" not in field_names  # file inputs are never fillable text fields

    first_name_field = next(f for f in form.fields if f.name == "first_name")
    assert first_name_field.value == "Jane"
    assert first_name_field.is_custom is False
    assert first_name_field.required is True

    email_field = next(f for f in form.fields if f.name == "email")
    assert email_field.value == "jane@example.com"

    custom_field = next(f for f in form.fields if f.name == "custom_why")
    assert custom_field.is_custom is True
    assert custom_field.label == "Why this role?"


@respx.mock
def test_discover_form_raises_when_no_form_present():
    respx.get("https://example.com/apply").mock(
        return_value=httpx.Response(200, text="<html><body>no form</body></html>")
    )
    with pytest.raises(ATSAdapterError):
        _TestAdapter().discover_form("https://example.com/apply", _profile(), email="jane@example.com")


@respx.mock
def test_discover_form_raises_on_http_error():
    respx.get("https://example.com/apply").mock(return_value=httpx.Response(404))
    with pytest.raises(ATSAdapterError):
        _TestAdapter().discover_form("https://example.com/apply", _profile(), email="jane@example.com")


@respx.mock
def test_submit_posts_hidden_and_filled_fields():
    route = respx.post("https://example.com/submit").mock(return_value=httpx.Response(200))

    filled = DiscoveredForm(
        submit_url="https://example.com/submit",
        hidden_fields={"csrf_token": "tok-abc"},
        fields=[
            FormField(name="first_name", label="First name", field_type="text", required=True, value="Jane"),
            FormField(
                name="custom_why", label="Why this role?", field_type="textarea", required=False,
                value="", is_custom=True,
            ),
        ],
    )

    _TestAdapter().submit(filled, cv_pdf=b"%PDF-cv", lettre_pdf=b"%PDF-lettre")

    assert route.called
    sent_body = route.calls[0].request.content
    assert b"tok-abc" in sent_body
    assert b"Jane" in sent_body


@respx.mock
def test_submit_raises_on_http_error():
    respx.post("https://example.com/submit").mock(return_value=httpx.Response(500))
    filled = DiscoveredForm(submit_url="https://example.com/submit", hidden_fields={}, fields=[])

    with pytest.raises(ATSAdapterError):
        _TestAdapter().submit(filled, cv_pdf=b"%PDF", lettre_pdf=b"%PDF")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/ats_adapters/test_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ats_adapters'`

- [ ] **Step 3: Implement schemas, errors, and the base adapter**

`backend/app/ats_adapters/__init__.py`:
```python
```

`backend/app/ats_adapters/schemas.py`:
```python
from pydantic import BaseModel


class FormField(BaseModel):
    name: str
    label: str
    field_type: str
    required: bool
    options: list[str] | None = None
    value: str | None = None
    is_custom: bool = False


class DiscoveredForm(BaseModel):
    submit_url: str
    fields: list[FormField]
    hidden_fields: dict[str, str] = {}
```

`backend/app/ats_adapters/errors.py`:
```python
class ATSAdapterError(Exception):
    pass
```

`backend/app/ats_adapters/base.py`:
```python
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.ats_adapters.errors import ATSAdapterError
from app.ats_adapters.schemas import DiscoveredForm, FormField
from app.models.candidate_profile import CandidateProfile


class HtmlFormAdapter:
    """Generic adapter for ATS platforms (Greenhouse, Lever) that embed a
    single standard HTML application form on the offer's page.

    Subclasses set three class attributes to specialize this for their
    platform's field naming convention - no other code is platform-specific:

    - `standard_field_aliases`: maps a CandidateProfile concept
      ("first_name", "email", ...) to a list of substrings to match against
      the HTML field's `name` attribute (case-insensitive).
    - `resume_field_names` / `cover_letter_field_names`: the file input
      `name` attribute(s) the CV/lettre PDFs are attached under on submit.
    """

    standard_field_aliases: dict[str, list[str]] = {}
    resume_field_names: list[str] = []
    cover_letter_field_names: list[str] = []

    def __init__(self, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(timeout=15.0)

    def discover_form(self, offer_url: str, profile: CandidateProfile, email: str) -> DiscoveredForm:
        try:
            response = self._http.get(offer_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ATSAdapterError(f"Impossible de charger le formulaire de candidature: {exc}") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.find("form")
        if form is None:
            raise ATSAdapterError("Aucun formulaire de candidature trouvé sur cette page.")

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

            options = [opt.get_text(strip=True) for opt in tag.find_all("option")] if tag.name == "select" else None

            value, is_standard = self._prefill_from_profile(name, profile, email)

            fields.append(
                FormField(
                    name=name,
                    label=label,
                    field_type=tag_type,
                    required=tag.has_attr("required"),
                    options=options,
                    value=value,
                    is_custom=not is_standard,
                )
            )

        return DiscoveredForm(submit_url=submit_url, fields=fields, hidden_fields=hidden_fields)

    def _prefill_from_profile(
        self, field_name: str, profile: CandidateProfile, email: str
    ) -> tuple[str | None, bool]:
        name_parts = profile.full_name.split(" ") if profile.full_name else []
        profile_values = {
            "full_name": profile.full_name or None,
            "first_name": name_parts[0] if name_parts else None,
            "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else None,
            "email": email,
            "phone": profile.phone or None,
            "address": profile.address,
            "linkedin": profile.linkedin_url,
            "portfolio": profile.portfolio_url,
        }
        lowered_field_name = field_name.lower()
        for concept, aliases in self.standard_field_aliases.items():
            if any(alias in lowered_field_name for alias in aliases):
                return profile_values.get(concept), True
        return None, False

    def submit(self, filled_form: DiscoveredForm, cv_pdf: bytes, lettre_pdf: bytes) -> None:
        data = dict(filled_form.hidden_fields)
        for field in filled_form.fields:
            if field.value:
                data[field.name] = field.value

        files: dict[str, tuple[str, bytes, str]] = {}
        if self.resume_field_names:
            files[self.resume_field_names[0]] = ("cv.pdf", cv_pdf, "application/pdf")
        if self.cover_letter_field_names:
            files[self.cover_letter_field_names[0]] = ("lettre.pdf", lettre_pdf, "application/pdf")

        try:
            response = self._http.post(filled_form.submit_url, data=data, files=files)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ATSAdapterError(f"Échec de la soumission de la candidature: {exc}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/ats_adapters/test_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ats_adapters backend/tests/ats_adapters/__init__.py backend/tests/ats_adapters/test_base.py
git commit -m "feat: add generic HTML application form adapter for Greenhouse/Lever"
```

---

### Task 13: Custom field answerer (Claude)

**Files:**
- Create: `backend/app/ats_adapters/custom_fields.py`
- Create: `backend/app/ats_adapters/dependencies.py`
- Test: `backend/tests/ats_adapters/test_custom_fields.py`
- Test: `backend/tests/ats_adapters/test_dependencies.py`

**Interfaces:**
- Consumes: `FormField` (Task 12)
- Produces: `CustomFieldAnsweringError(Exception)`
- Produces: `CustomFieldAnswerer.answer(custom_fields: list[FormField], cv_text: str, offer_text: str) -> dict[str, str]` (maps `field_name -> answer`, only for fields the LLM answered with confidence — unconfident/missing fields are simply absent from the returned dict, left for the user to fill manually in the review step)
- Produces: `get_custom_field_answerer() -> CustomFieldAnswerer` (lru_cached dependency provider)

- [ ] **Step 1: Write the failing tests**

`backend/tests/ats_adapters/test_custom_fields.py`:
```python
from types import SimpleNamespace

import anthropic
import pytest

from app.ats_adapters.custom_fields import CustomFieldAnsweringError, CustomFieldAnswerer
from app.ats_adapters.schemas import FormField


def _fake_tool_use_response(input_payload: dict):
    block = SimpleNamespace(type="tool_use", input=input_payload)
    return SimpleNamespace(content=[block])


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


_FIELDS = [
    FormField(name="custom_why", label="Why this role?", field_type="textarea", required=False, is_custom=True),
    FormField(name="custom_salary", label="Salary expectations", field_type="text", required=False, is_custom=True),
]


def test_answer_returns_only_confident_answers():
    client = FakeClient(
        [
            _fake_tool_use_response(
                {
                    "answers": [
                        {"field_name": "custom_why", "answer": "Mon expérience Python correspond au poste.", "confident": True},
                        {"field_name": "custom_salary", "answer": "", "confident": False},
                    ]
                }
            )
        ]
    )
    answerer = CustomFieldAnswerer(client)

    answers = answerer.answer(_FIELDS, "cv text", "offer text")

    assert answers == {"custom_why": "Mon expérience Python correspond au poste."}


def test_answer_with_no_custom_fields_skips_the_llm_call():
    client = FakeClient([])
    answerer = CustomFieldAnswerer(client)

    assert answerer.answer([], "cv text", "offer text") == {}
    assert client.messages.calls == []


def test_answer_retries_once_on_invalid_payload_then_succeeds():
    client = FakeClient(
        [
            _fake_tool_use_response({"answers": [{"field_name": "x"}]}),
            _fake_tool_use_response({"answers": [{"field_name": "custom_why", "answer": "OK", "confident": True}]}),
        ]
    )
    answerer = CustomFieldAnswerer(client)

    answers = answerer.answer(_FIELDS, "cv text", "offer text")
    assert answers == {"custom_why": "OK"}
    assert len(client.messages.calls) == 2


def test_answer_raises_after_two_failures():
    client = FakeClient([_fake_tool_use_response({"answers": [{"field_name": "x"}]})] * 2)
    answerer = CustomFieldAnswerer(client)

    with pytest.raises(CustomFieldAnsweringError):
        answerer.answer(_FIELDS, "cv text", "offer text")


def test_answer_retries_on_api_error():
    client = FakeClient(
        [
            anthropic.APIConnectionError(request=SimpleNamespace()),
            _fake_tool_use_response({"answers": [{"field_name": "custom_why", "answer": "OK", "confident": True}]}),
        ]
    )
    answerer = CustomFieldAnswerer(client)

    answers = answerer.answer(_FIELDS, "cv text", "offer text")
    assert answers == {"custom_why": "OK"}
```

`backend/tests/ats_adapters/test_dependencies.py`:
```python
from app.ats_adapters.dependencies import get_custom_field_answerer


def test_custom_field_answerer_client_has_bounded_timeout_and_no_sdk_retries():
    get_custom_field_answerer.cache_clear()
    answerer = get_custom_field_answerer()
    client = answerer._client

    assert client.timeout == 30.0
    assert client.max_retries == 0

    get_custom_field_answerer.cache_clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/ats_adapters/test_custom_fields.py tests/ats_adapters/test_dependencies.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ats_adapters.custom_fields'`

- [ ] **Step 3: Implement the answerer and dependencies**

`backend/app/ats_adapters/custom_fields.py`:
```python
import anthropic
from pydantic import BaseModel, ValidationError

from app.ats_adapters.schemas import FormField

_MAX_ATTEMPTS = 2

_CUSTOM_FIELDS_TOOL = {
    "name": "submit_custom_field_answers",
    "description": "Submit answers to a job application form's custom questions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_name": {"type": "string"},
                        "answer": {"type": "string"},
                        "confident": {
                            "type": "boolean",
                            "description": "False if the question cannot be answered with confidence from the CV/offer alone (e.g. a personal choice not derivable from the data) - in that case, answer should be empty.",
                        },
                    },
                    "required": ["field_name", "answer", "confident"],
                },
            }
        },
        "required": ["answers"],
    },
}


class CustomFieldAnsweringError(Exception):
    pass


class _CustomFieldAnswer(BaseModel):
    field_name: str
    answer: str
    confident: bool


class _CustomFieldAnswers(BaseModel):
    answers: list[_CustomFieldAnswer]


class CustomFieldAnswerer:
    def __init__(self, client, model: str = "claude-sonnet-5"):
        self._client = client
        self._model = model

    def answer(self, custom_fields: list[FormField], cv_text: str, offer_text: str) -> dict[str, str]:
        if not custom_fields:
            return {}

        fields_description = "\n".join(
            f"- name={f.name!r} label={f.label!r} options={f.options}" for f in custom_fields
        )
        prompt = (
            "A candidate is applying to this job offer using this CV. Answer "
            "each custom application question below on their behalf, using "
            "only information present in the CV and the offer - never invent "
            "experience or facts not present in the CV. If a question cannot "
            "be answered with confidence from the CV/offer alone (e.g. it "
            "asks for a personal choice like specific salary negotiation not "
            "derivable from the data), set confident=false and leave answer "
            "empty rather than guessing. Respond in the same language as the "
            "CV.\n\n"
            f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}\n\nQuestions:\n{fields_description}"
        )

        last_error: Exception | None = None
        for _ in range(_MAX_ATTEMPTS):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    tools=[_CUSTOM_FIELDS_TOOL],
                    tool_choice={"type": "tool", "name": _CUSTOM_FIELDS_TOOL["name"]},
                    messages=[{"role": "user", "content": prompt}],
                )
                tool_use = next((block for block in response.content if block.type == "tool_use"), None)
                if tool_use is None:
                    raise CustomFieldAnsweringError("No tool_use block in Claude response")
                parsed = _CustomFieldAnswers.model_validate(tool_use.input)
                return {a.field_name: a.answer for a in parsed.answers if a.confident and a.answer.strip()}
            except (ValidationError, CustomFieldAnsweringError, anthropic.APIError) as exc:
                last_error = exc
                continue
        raise CustomFieldAnsweringError(f"Custom field answering failed after retries: {last_error}")
```

`backend/app/ats_adapters/dependencies.py`:
```python
from functools import lru_cache

import anthropic

from app.config import get_settings
from app.ats_adapters.custom_fields import CustomFieldAnswerer


@lru_cache
def get_custom_field_answerer() -> CustomFieldAnswerer:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=30.0, max_retries=0)
    return CustomFieldAnswerer(client)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/ats_adapters/test_custom_fields.py tests/ats_adapters/test_dependencies.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ats_adapters/custom_fields.py backend/app/ats_adapters/dependencies.py backend/tests/ats_adapters/test_custom_fields.py backend/tests/ats_adapters/test_dependencies.py
git commit -m "feat: add LLM custom application field answerer"
```

---

### Task 14: `GreenhouseAdapter`

**Files:**
- Create: `backend/app/ats_adapters/greenhouse.py`
- Test: `backend/tests/ats_adapters/test_greenhouse.py`

**Interfaces:**
- Consumes: `HtmlFormAdapter` (Task 12)
- Produces: `GreenhouseAdapter(HtmlFormAdapter)` — no new methods, only the alias tables specialized for Greenhouse's `job_application[...]` bracket-style field naming

- [ ] **Step 1: Write the failing tests**

`backend/tests/ats_adapters/test_greenhouse.py`:
```python
import httpx
import respx

from app.ats_adapters.greenhouse import GreenhouseAdapter
from app.ats_adapters.schemas import DiscoveredForm
from app.models.candidate_profile import CandidateProfile

_SAMPLE_HTML = """
<html><body>
<form action="https://boards-api.greenhouse.io/v1/boards/acme/jobs/123" method="post">
  <input type="hidden" name="authenticity_token" value="tok-gh" />
  <label for="first_name">First Name</label>
  <input type="text" name="job_application[first_name]" id="first_name" required />
  <label for="last_name">Last Name</label>
  <input type="text" name="job_application[last_name]" id="last_name" required />
  <label for="email">Email</label>
  <input type="email" name="job_application[email]" id="email" required />
  <label for="phone">Phone</label>
  <input type="tel" name="job_application[phone]" id="phone" />
  <input type="file" name="job_application[resume]" />
  <label for="q1">Why do you want to work here?</label>
  <textarea name="job_application[answers_attributes][0][text_value]" id="q1"></textarea>
</form>
</body></html>
"""


def _profile() -> CandidateProfile:
    return CandidateProfile(user_id=1, full_name="Jane Doe", phone="0612345678", work_authorization="FR/UE")


@respx.mock
def test_discover_form_maps_greenhouse_field_names():
    respx.get("https://boards.greenhouse.io/acme/jobs/123").mock(return_value=httpx.Response(200, text=_SAMPLE_HTML))

    form = GreenhouseAdapter().discover_form(
        "https://boards.greenhouse.io/acme/jobs/123", _profile(), email="jane@example.com"
    )

    first_name = next(f for f in form.fields if f.name == "job_application[first_name]")
    assert first_name.value == "Jane"
    assert first_name.is_custom is False

    email_field = next(f for f in form.fields if f.name == "job_application[email]")
    assert email_field.value == "jane@example.com"

    custom = next(f for f in form.fields if f.is_custom)
    assert custom.name == "job_application[answers_attributes][0][text_value]"
    assert "Why" in custom.label

    assert form.hidden_fields == {"authenticity_token": "tok-gh"}
    assert form.submit_url == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/123"


@respx.mock
def test_submit_attaches_cv_and_lettre_under_greenhouse_field_names():
    route = respx.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/123").mock(
        return_value=httpx.Response(200)
    )

    filled = DiscoveredForm(
        submit_url="https://boards-api.greenhouse.io/v1/boards/acme/jobs/123",
        hidden_fields={"authenticity_token": "tok-gh"},
        fields=[],
    )

    GreenhouseAdapter().submit(filled, cv_pdf=b"%PDF-cv", lettre_pdf=b"%PDF-lettre")

    assert route.called
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/ats_adapters/test_greenhouse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ats_adapters.greenhouse'`

- [ ] **Step 3: Implement the adapter**

`backend/app/ats_adapters/greenhouse.py`:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/ats_adapters/test_greenhouse.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ats_adapters/greenhouse.py backend/tests/ats_adapters/test_greenhouse.py
git commit -m "feat: add GreenhouseAdapter"
```

---

### Task 15: `LeverAdapter`

**Files:**
- Create: `backend/app/ats_adapters/lever.py`
- Test: `backend/tests/ats_adapters/test_lever.py`

**Interfaces:**
- Consumes: `HtmlFormAdapter` (Task 12)
- Produces: `LeverAdapter(HtmlFormAdapter)` — alias tables specialized for Lever's flat field naming (a single `name` field for full name, rather than Greenhouse's split `first_name`/`last_name`)

- [ ] **Step 1: Write the failing tests**

`backend/tests/ats_adapters/test_lever.py`:
```python
import httpx
import respx

from app.ats_adapters.lever import LeverAdapter
from app.ats_adapters.schemas import DiscoveredForm
from app.models.candidate_profile import CandidateProfile

_SAMPLE_HTML = """
<html><body>
<form action="https://jobs.lever.co/acme/abc123/apply" method="post">
  <input type="hidden" name="token" value="tok-lever" />
  <label for="name">Full Name</label>
  <input type="text" name="name" id="name" required />
  <label for="email">Email</label>
  <input type="email" name="email" id="email" required />
  <label for="phone">Phone</label>
  <input type="tel" name="phone" id="phone" />
  <input type="file" name="resume" />
  <label for="urls_LinkedIn">LinkedIn</label>
  <input type="text" name="urls[LinkedIn]" id="urls_LinkedIn" />
  <label for="custom1">What interests you about this role?</label>
  <textarea name="customQuestion0" id="custom1"></textarea>
</form>
</body></html>
"""


def _profile() -> CandidateProfile:
    return CandidateProfile(
        user_id=1, full_name="Jane Doe", phone="0612345678", work_authorization="FR/UE",
        linkedin_url="https://linkedin.com/in/janedoe",
    )


@respx.mock
def test_discover_form_maps_lever_field_names():
    respx.get("https://jobs.lever.co/acme/abc123").mock(return_value=httpx.Response(200, text=_SAMPLE_HTML))

    form = LeverAdapter().discover_form(
        "https://jobs.lever.co/acme/abc123", _profile(), email="jane@example.com"
    )

    name_field = next(f for f in form.fields if f.name == "name")
    assert name_field.value == "Jane Doe"  # full name, not just first name
    assert name_field.is_custom is False

    linkedin_field = next(f for f in form.fields if f.name == "urls[LinkedIn]")
    assert linkedin_field.value == "https://linkedin.com/in/janedoe"

    custom = next(f for f in form.fields if f.is_custom)
    assert custom.name == "customQuestion0"
    assert "interests" in custom.label

    assert form.hidden_fields == {"token": "tok-lever"}
    assert form.submit_url == "https://jobs.lever.co/acme/abc123/apply"


@respx.mock
def test_submit_attaches_cv_and_lettre_under_lever_field_names():
    route = respx.post("https://jobs.lever.co/acme/abc123/apply").mock(return_value=httpx.Response(200))

    filled = DiscoveredForm(
        submit_url="https://jobs.lever.co/acme/abc123/apply",
        hidden_fields={"token": "tok-lever"},
        fields=[],
    )

    LeverAdapter().submit(filled, cv_pdf=b"%PDF-cv", lettre_pdf=b"%PDF-lettre")

    assert route.called
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/ats_adapters/test_lever.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ats_adapters.lever'`

- [ ] **Step 3: Implement the adapter**

`backend/app/ats_adapters/lever.py`:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/ats_adapters/test_lever.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ats_adapters/lever.py backend/tests/ats_adapters/test_lever.py
git commit -m "feat: add LeverAdapter"
```

- [ ] **Step 6: Mandatory manual verification (before this auto-submit path ever reaches production)**

Per the spec's testing section, run `GreenhouseAdapter` and `LeverAdapter` once each against a real, currently-open job posting on each platform (pick a low-stakes one — a role you're genuinely willing to apply to, or a company's test/demo posting if one is available), using a throwaway `CandidateProfile` and a generated CV/lettre pair. Confirm:
1. `discover_form` finds the real `<form>` and correctly splits standard vs. custom fields (the alias tables above are best-effort, written without live access to either platform — expect to need to adjust `standard_field_aliases` after this step)
2. The hidden fields captured include whatever CSRF/session token the real page uses
3. `submit` returns success and the application genuinely appears on the employer's side (or, at minimum, no error) — do **not** enable auto-submit for other users until this has been confirmed on both platforms

This step cannot be automated or delegated to the test suite — it requires a live network call against a real third-party service and a human judgment call about which real posting is safe to use for it.

---

### Task 16: `ats_adapters` registry

**Files:**
- Create: `backend/app/ats_adapters/registry.py`
- Test: `backend/tests/ats_adapters/test_registry.py`

**Interfaces:**
- Consumes: `GreenhouseAdapter` (Task 14), `LeverAdapter` (Task 15)
- Produces: `get_ats_adapter(ats_type: str | None) -> HtmlFormAdapter | None` — returns `None` for any `ats_type` not in `{"greenhouse", "lever"}` (including `None` itself), so callers can use the return value directly to decide auto-submit vs. assisted mode without a separate lookup-then-check step

- [ ] **Step 1: Write the failing tests**

`backend/tests/ats_adapters/test_registry.py`:
```python
from app.ats_adapters.greenhouse import GreenhouseAdapter
from app.ats_adapters.lever import LeverAdapter
from app.ats_adapters.registry import get_ats_adapter


def test_get_ats_adapter_returns_greenhouse_adapter():
    assert isinstance(get_ats_adapter("greenhouse"), GreenhouseAdapter)


def test_get_ats_adapter_returns_lever_adapter():
    assert isinstance(get_ats_adapter("lever"), LeverAdapter)


def test_get_ats_adapter_returns_none_for_unsupported_type():
    assert get_ats_adapter("workday") is None
    assert get_ats_adapter(None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/ats_adapters/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ats_adapters.registry'`

- [ ] **Step 3: Implement the registry**

`backend/app/ats_adapters/registry.py`:
```python
from functools import lru_cache

from app.ats_adapters.base import HtmlFormAdapter
from app.ats_adapters.greenhouse import GreenhouseAdapter
from app.ats_adapters.lever import LeverAdapter

_ADAPTERS: dict[str, type[HtmlFormAdapter]] = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
}


@lru_cache
def _adapter_instance(ats_type: str) -> HtmlFormAdapter:
    # Cached (one instance per ats_type, for the app's lifetime) rather than
    # constructed fresh on every call: each adapter holds its own httpx.Client
    # internally (Task 12), and get_ats_adapter is called directly - not
    # through a per-request FastAPI Depends - from Task 17's router on every
    # prefilled-form/confirm request, so a fresh instance per call would leak
    # an unclosed httpx.Client per request. This mirrors the lru_cache
    # singleton pattern already used for get_object_storage/get_semantic_analyzer.
    return _ADAPTERS[ats_type]()


def get_ats_adapter(ats_type: str | None) -> HtmlFormAdapter | None:
    if ats_type not in _ADAPTERS:
        return None
    return _adapter_instance(ats_type)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/ats_adapters/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ats_adapters/registry.py backend/tests/ats_adapters/test_registry.py
git commit -m "feat: add ats_adapters registry keyed by ats_type"
```

---

### Task 17: Submit orchestration — prefilled-form preview, confirm, mark-sent-manually

**Files:**
- Modify: `backend/app/applications/service.py`
- Modify: `backend/app/schemas/application.py`
- Modify: `backend/app/routers/applications.py`
- Test: `backend/tests/routers/test_applications_submit.py`

**Interfaces:**
- Consumes: `get_ats_adapter` (Task 16); `CustomFieldAnswerer`, `CustomFieldAnsweringError`, `get_custom_field_answerer` (Task 13); `ATSAdapterError`, `FormField`, `DiscoveredForm` (Task 12); `PersonalizedDocument` (existing, `app.models.personalized_document`); `ObjectStorage`, `ObjectStorageError`, `get_object_storage` (existing, `app.storage`)
- Produces: `missing_required_profile_fields(profile: CandidateProfile | None) -> list[str]` (added to `app.applications.service`)
- Produces: `PrefilledFormOut(BaseModel)` — `fields: list[FormField]`
- Produces: `ConfirmApplicationIn(BaseModel)` — `fields: list[FormField] | None = None`
- Produces: routes `GET /applications/{id}/prefilled-form`, `POST /applications/{id}/confirm`, `POST /applications/{id}/mark-sent`

Flow for an `ats_type`-eligible application: `GET .../prefilled-form` calls the adapter's `discover_form` against the live offer page, then `CustomFieldAnswerer.answer` for any custom fields it found (a `CustomFieldAnsweringError` here is caught and swallowed — the fields are simply returned unfilled rather than failing the whole preview, per the spec: an LLM failure on custom questions must never block the user from reviewing and finishing the form by hand). The user reviews/edits the returned fields client-side, then `POST .../confirm` re-runs `discover_form` (fresh CSRF/session token — the one from the `GET` may be stale by the time the user finishes reviewing) with the client's edited values merged in, downloads the CV/lettre PDFs already generated by the personalization endpoints (sous-projet 3), and calls `adapter.submit`. A `POST .../confirm` on a non-`ats_type` application skips all of this and just flips the status to `a_soumettre_manuellement` — there is nothing to submit automatically.

- [ ] **Step 1: Write the failing tests**

`backend/tests/routers/test_applications_submit.py`:
```python
import io

import httpx
import respx
from docx import Document

from app.ats_adapters.custom_fields import CustomFieldAnswerer
from app.ats_adapters.dependencies import get_custom_field_answerer
from app.llm_analyzer.analyzer import SemanticReport
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.main import app
from app.personalization.dependencies import get_cover_letter_generator, get_cv_rewriter
from app.personalization.schemas import CoverLetter, CvExperienceEntry, RewrittenCv
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage

_GREENHOUSE_FORM_HTML = """
<html><body>
<form action="https://boards-api.greenhouse.io/v1/boards/acme/jobs/123" method="post">
  <input type="hidden" name="authenticity_token" value="tok-gh" />
  <label for="first_name">First Name</label>
  <input type="text" name="job_application[first_name]" id="first_name" required />
  <label for="email">Email</label>
  <input type="email" name="job_application[email]" id="email" required />
  <input type="file" name="job_application[resume]" />
  <label for="q1">Why do you want to work here?</label>
  <textarea name="job_application[answers_attributes][0][text_value]" id="q1"></textarea>
</form>
</body></html>
"""


class FakeAnalyzer:
    def analyze(self, cv_text, offer_text):
        return SemanticReport(score=70, missing_keywords=["Docker"], recommendations=["Add Docker"])


class FakeCvRewriter:
    def rewrite(self, cv_text, offer_text, missing_keywords, recommendations):
        return RewrittenCv(
            summary="Résumé.",
            experience=[CvExperienceEntry(title="Dev", company="Acme", dates="2020-2022", bullets=["A conçu des API."])],
            education=["Master"],
            skills=["Python"],
        )


class FakeCoverLetterGenerator:
    def generate(self, cv_text, offer_text, missing_keywords, recommendations):
        return CoverLetter(
            greeting="Madame, Monsieur,",
            body_paragraphs=["Je candidate à ce poste."],
            closing_formula="Cordialement,",
            signature="Jane Doe",
        )


class FakeCustomFieldAnswerer(CustomFieldAnswerer):
    def __init__(self):
        pass

    def answer(self, custom_fields, cv_text, offer_text):
        return {f.name: "Réponse générée." for f in custom_fields}


class FakeObjectStorage(ObjectStorage):
    def __init__(self):
        self._objects: dict[str, bytes] = {}

    def upload(self, key, content):
        self._objects[key] = content

    def download(self, key):
        if key not in self._objects:
            raise ObjectStorageError(f"missing {key}")
        return self._objects[key]

    def delete(self, key):
        self._objects.pop(key, None)


def _register_and_login(client, email: str = "jane@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": email, "password": "s3cret!1"})
    return login.json()["access_token"]


def _cv_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Expérience")
    document.add_paragraph("Développeuse Python")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _setup_profile(client, headers: dict) -> None:
    client.put(
        "/profile", headers=headers,
        json={"full_name": "Jane Doe", "phone": "0612345678", "work_authorization": "FR/UE"},
    )
    client.post(
        "/profile/cv", headers=headers,
        files={"cv_file": ("cv.docx", _cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )


def _setup_ready_ats_application(client, headers: dict) -> int:
    _setup_profile(client, headers)
    created = client.post(
        "/applications", headers=headers,
        json={
            "offer_url": "https://boards.greenhouse.io/acme/jobs/123",
            "offer_text": "Nous recherchons un développeur Python.",
            "source": "greenhouse",
            "company_name": "Acme",
            "job_title": "Développeur Python",
            "ats_type": "greenhouse",
        },
    )
    application_id = created.json()["id"]
    diagnostic_id = created.json()["diagnostic_id"]
    client.post(f"/diagnostics/{diagnostic_id}/cv", headers=headers)
    client.post(f"/diagnostics/{diagnostic_id}/lettre", headers=headers)
    return application_id


def _override_common_dependencies() -> None:
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    app.dependency_overrides[get_cv_rewriter] = lambda: FakeCvRewriter()
    app.dependency_overrides[get_cover_letter_generator] = lambda: FakeCoverLetterGenerator()
    app.dependency_overrides[get_object_storage] = lambda: FakeObjectStorage()
    app.dependency_overrides[get_custom_field_answerer] = lambda: FakeCustomFieldAnswerer()


@respx.mock
def test_get_prefilled_form_returns_standard_and_llm_answered_custom_fields(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    application_id = _setup_ready_ats_application(client, headers)
    respx.get("https://boards.greenhouse.io/acme/jobs/123").mock(return_value=httpx.Response(200, text=_GREENHOUSE_FORM_HTML))

    response = client.get(f"/applications/{application_id}/prefilled-form", headers=headers)

    assert response.status_code == 200
    fields = response.json()["fields"]
    first_name = next(f for f in fields if f["name"] == "job_application[first_name]")
    assert first_name["value"] == "Jane"
    custom = next(f for f in fields if f["is_custom"])
    assert custom["value"] == "Réponse générée."


def test_get_prefilled_form_returns_409_for_non_ats_offer(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile(client, headers)
    created = client.post(
        "/applications", headers=headers,
        json={
            "offer_url": "https://www.linkedin.com/jobs/view/123",
            "offer_text": "Offre.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Dev",
        },
    )
    response = client.get(f"/applications/{created.json()['id']}/prefilled-form", headers=headers)
    assert response.status_code == 409


@respx.mock
def test_confirm_application_auto_submits_for_ats_offer(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    application_id = _setup_ready_ats_application(client, headers)
    respx.get("https://boards.greenhouse.io/acme/jobs/123").mock(return_value=httpx.Response(200, text=_GREENHOUSE_FORM_HTML))
    submit_route = respx.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/123").mock(return_value=httpx.Response(200))

    prefilled = client.get(f"/applications/{application_id}/prefilled-form", headers=headers).json()
    response = client.post(f"/applications/{application_id}/confirm", headers=headers, json={"fields": prefilled["fields"]})

    assert response.status_code == 200
    assert response.json()["status"] == "soumise_auto"
    assert submit_route.called


@respx.mock
def test_confirm_application_records_failure_status_on_submission_error(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    application_id = _setup_ready_ats_application(client, headers)
    respx.get("https://boards.greenhouse.io/acme/jobs/123").mock(return_value=httpx.Response(200, text=_GREENHOUSE_FORM_HTML))
    respx.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/123").mock(return_value=httpx.Response(500))

    prefilled = client.get(f"/applications/{application_id}/prefilled-form", headers=headers).json()
    response = client.post(f"/applications/{application_id}/confirm", headers=headers, json={"fields": prefilled["fields"]})

    assert response.status_code == 503
    detail = client.get(f"/applications/{application_id}", headers=headers).json()
    assert detail["status"] == "echec_soumission"
    assert detail["error_message"] is not None


def test_confirm_application_without_ats_type_moves_to_assisted_status(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile(client, headers)
    created = client.post(
        "/applications", headers=headers,
        json={
            "offer_url": "https://www.linkedin.com/jobs/view/123",
            "offer_text": "Offre.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Dev",
        },
    )
    application_id = created.json()["id"]

    response = client.post(f"/applications/{application_id}/confirm", headers=headers, json={})

    assert response.status_code == 200
    assert response.json()["status"] == "a_soumettre_manuellement"


def test_mark_sent_manually_transitions_status(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile(client, headers)
    created = client.post(
        "/applications", headers=headers,
        json={
            "offer_url": "https://www.linkedin.com/jobs/view/123",
            "offer_text": "Offre.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Dev",
        },
    )
    application_id = created.json()["id"]
    client.post(f"/applications/{application_id}/confirm", headers=headers, json={})

    response = client.post(f"/applications/{application_id}/mark-sent", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "soumise_manuelle_confirmee"


def test_mark_sent_manually_rejects_wrong_state(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    application_id = _setup_ready_ats_application(client, headers)  # still "en_cours", never confirmed

    response = client.post(f"/applications/{application_id}/mark-sent", headers=headers)
    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/routers/test_applications_submit.py -v`
Expected: FAIL with `404 Not Found` on `/applications/{id}/prefilled-form` (route doesn't exist yet)

- [ ] **Step 3: Implement the endpoints**

Modify `backend/app/applications/service.py` — append:
```python
def missing_required_profile_fields(profile: CandidateProfile | None) -> list[str]:
    if profile is None:
        return ["full_name", "phone", "work_authorization"]
    missing = []
    if not profile.full_name:
        missing.append("full_name")
    if not profile.phone:
        missing.append("phone")
    if not profile.work_authorization:
        missing.append("work_authorization")
    return missing
```

Modify `backend/app/schemas/application.py` — append:
```python
from app.ats_adapters.schemas import FormField


class PrefilledFormOut(BaseModel):
    fields: list[FormField]


class ConfirmApplicationIn(BaseModel):
    fields: list[FormField] | None = None
```

Modify `backend/app/routers/applications.py` — add imports and three new routes at the end of the file:
```python
from datetime import datetime

from app.applications.service import missing_required_profile_fields
from app.ats_adapters.custom_fields import CustomFieldAnsweringError
from app.ats_adapters.dependencies import get_custom_field_answerer
from app.ats_adapters.errors import ATSAdapterError
from app.ats_adapters.registry import get_ats_adapter
from app.models.application import (
    APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
    APPLICATION_STATUS_ECHEC_SOUMISSION,
    APPLICATION_STATUS_EN_COURS,
    APPLICATION_STATUS_SOUMISE_AUTO,
    APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE,
)
from app.models.candidate_profile import CandidateProfile
from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
from app.schemas.application import ConfirmApplicationIn, PrefilledFormOut
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage


@router.get("/{application_id}/prefilled-form", response_model=PrefilledFormOut)
def get_prefilled_form(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    custom_field_answerer=Depends(get_custom_field_answerer),
) -> PrefilledFormOut:
    application = get_owned_application(db, application_id, current_user.id)
    if application.ats_type is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette offre n'est pas éligible à la soumission automatique.",
        )

    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    missing = missing_required_profile_fields(profile)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Complétez votre profil avant de continuer: {', '.join(missing)}",
        )

    adapter = get_ats_adapter(application.ats_type)
    try:
        form = adapter.discover_form(application.offer_url, profile, current_user.email)
    except ATSAdapterError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    diagnostic = db.query(Diagnostic).filter(Diagnostic.id == application.diagnostic_id).first()
    custom_fields = [f for f in form.fields if f.is_custom]
    try:
        answers = custom_field_answerer.answer(custom_fields, diagnostic.cv_text, diagnostic.offer_text)
    except CustomFieldAnsweringError:
        # Non-fatal: the preview is still returned, with custom fields left
        # blank for the user to fill in manually during review.
        answers = {}

    filled_fields = [f.model_copy(update={"value": answers.get(f.name, f.value)}) for f in form.fields]
    return PrefilledFormOut(fields=filled_fields)


def _get_ready_personalized_documents(db: Session, diagnostic_id: int) -> tuple[PersonalizedDocument, PersonalizedDocument] | None:
    cv_document = (
        db.query(PersonalizedDocument)
        .filter(PersonalizedDocument.diagnostic_id == diagnostic_id, PersonalizedDocument.kind == "cv")
        .first()
    )
    lettre_document = (
        db.query(PersonalizedDocument)
        .filter(PersonalizedDocument.diagnostic_id == diagnostic_id, PersonalizedDocument.kind == "lettre")
        .first()
    )
    if cv_document is None or lettre_document is None:
        return None
    return cv_document, lettre_document


@router.post("/{application_id}/confirm", response_model=ApplicationOut)
def confirm_application(
    application_id: int,
    payload: ConfirmApplicationIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> ApplicationOut:
    application = get_owned_application(db, application_id, current_user.id)
    if application.status != APPLICATION_STATUS_EN_COURS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette candidature a déjà été traitée.")

    if application.ats_type is None:
        application.status = APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT
        db.commit()
        db.refresh(application)
        return _to_out(application)

    if payload.fields is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Les champs du formulaire pré-rempli sont requis pour la soumission automatique.",
        )

    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    missing = missing_required_profile_fields(profile)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Complétez votre profil avant de continuer: {', '.join(missing)}",
        )

    documents = _get_ready_personalized_documents(db, application.diagnostic_id)
    if documents is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Générez le CV et la lettre de motivation avant de confirmer la candidature.",
        )
    cv_document, lettre_document = documents

    adapter = get_ats_adapter(application.ats_type)
    try:
        # Re-discovered rather than reusing the GET .../prefilled-form
        # result: the hidden CSRF/session token there may no longer be
        # valid by the time the user finishes reviewing the form.
        discovered = adapter.discover_form(application.offer_url, profile, current_user.email)
        edited_values = {f.name: f.value for f in payload.fields}
        filled_fields = [
            f.model_copy(update={"value": edited_values.get(f.name, f.value)}) for f in discovered.fields
        ]
        filled_form = discovered.model_copy(update={"fields": filled_fields})

        cv_pdf = storage.download(cv_document.storage_key)
        lettre_pdf = storage.download(lettre_document.storage_key)
        adapter.submit(filled_form, cv_pdf, lettre_pdf)
    except (ATSAdapterError, ObjectStorageError) as exc:
        # No retry: a failed submission is surfaced to the user, never
        # silently resubmitted (which could result in a duplicate
        # application if the first attempt actually went through upstream).
        application.status = APPLICATION_STATUS_ECHEC_SOUMISSION
        application.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    application.status = APPLICATION_STATUS_SOUMISE_AUTO
    application.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(application)
    return _to_out(application)


@router.post("/{application_id}/mark-sent", response_model=ApplicationOut)
def mark_sent_manually(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationOut:
    application = get_owned_application(db, application_id, current_user.id)
    if application.status != APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cette candidature n'est pas en attente d'envoi manuel."
        )
    application.status = APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE
    db.commit()
    db.refresh(application)
    return _to_out(application)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/routers/test_applications_submit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/applications/service.py backend/app/schemas/application.py backend/app/routers/applications.py backend/tests/routers/test_applications_submit.py
git commit -m "feat: add prefilled-form preview, confirm, and mark-sent-manually endpoints"
```

---

### Task 18: RGPD — purge `Application` rows on `DELETE /diagnostics`

**Files:**
- Modify: `backend/app/routers/diagnostics.py`
- Modify: `backend/tests/routers/test_diagnostics.py`

**Interfaces:**
- Consumes: `Application` (Task 2)

`DELETE /diagnostics` already bulk-deletes `PersonalizedDocument` rows explicitly rather than relying on `ondelete="CASCADE"`, because it uses SQLAlchemy bulk `.delete()` queries (which bypass ORM-level relationship cascades) and the test suite's SQLite doesn't enforce FK-level cascade by default. `Application` rows need the exact same explicit treatment, or a user's job-search history would survive an RGPD purge of their diagnostics.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/routers/test_diagnostics.py` (reuses `_register_and_login` and `_clean_cv_docx_bytes`, already defined earlier in this file):
```python
def test_delete_all_diagnostics_also_purges_applications(client, db_session):
    from app.models.application import APPLICATION_STATUS_EN_COURS, Application
    from app.models.user import User

    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/diagnostics",
        headers=headers,
        files={
            "cv_file": (
                "cv.docx", _clean_cv_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"offer_text": "Nous recherchons un développeur Python."},
    )
    diagnostic_id = create_response.json()["id"]

    user = db_session.query(User).filter(User.email == "jane@example.com").first()
    db_session.add(
        Application(
            user_id=user.id,
            diagnostic_id=diagnostic_id,
            offer_url="https://example.com/job/1",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            status=APPLICATION_STATUS_EN_COURS,
        )
    )
    db_session.commit()

    response = client.delete("/diagnostics", headers=headers)

    assert response.status_code == 204
    assert db_session.query(Application).count() == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/routers/test_diagnostics.py::test_delete_all_diagnostics_also_purges_applications -v`
Expected: FAIL — `Application` row still present after the purge (the `IntegrityError` this test would otherwise trigger, since `diagnostic_id` has `ondelete="CASCADE"` at the FK level but SQLite in this test suite doesn't enforce it, means the row simply survives the bulk delete instead)

- [ ] **Step 3: Update `delete_all_diagnostics`**

Modify `backend/app/routers/diagnostics.py` — add the import and update the function body:
```python
from app.models.application import Application
```

Replace the body of `delete_all_diagnostics`:
```python
@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> None:
    diagnostic_ids = [
        row[0] for row in db.query(Diagnostic.id).filter(Diagnostic.user_id == current_user.id).all()
    ]

    documents = (
        db.query(PersonalizedDocument)
        .filter(PersonalizedDocument.diagnostic_id.in_(diagnostic_ids))
        .all()
    )
    storage_keys = [document.storage_key for document in documents]

    # Application rows need the same explicit bulk deletion as
    # PersonalizedDocument above, and for the same reason: this endpoint
    # uses bulk `.delete()` queries, which bypass SQLAlchemy ORM-level
    # relationship cascades, and SQLite (used in the test suite) doesn't
    # enforce FK-level ondelete="CASCADE" unless PRAGMA foreign_keys=ON is
    # explicitly set. Deleted before PersonalizedDocument/Diagnostic so no
    # FK is ever left dangling mid-purge on backends that do enforce it.
    db.query(Application).filter(Application.diagnostic_id.in_(diagnostic_ids)).delete(synchronize_session=False)

    db.query(PersonalizedDocument).filter(PersonalizedDocument.diagnostic_id.in_(diagnostic_ids)).delete(
        synchronize_session=False
    )
    db.query(Diagnostic).filter(Diagnostic.user_id == current_user.id).delete()
    db.commit()

    for key in storage_keys:
        try:
            storage.delete(key)
        except ObjectStorageError:
            logger.warning("Failed to delete MinIO object %s during RGPD purge", key)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && pytest tests/routers/test_diagnostics.py -v`
Expected: PASS (full file, to confirm this change didn't regress the existing RGPD purge tests for `PersonalizedDocument`)

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: PASS — every task above lands in the same codebase; this is the final check that nothing earlier regressed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/diagnostics.py backend/tests/routers/test_diagnostics.py
git commit -m "fix: purge Application rows on RGPD diagnostic history deletion"
```

---

## Self-Review

**Spec coverage:**
- Search via France Travail/Adzuna/Greenhouse/Lever official APIs, no LinkedIn/Indeed scraping → Tasks 5–9
- On-demand search, no scheduler → Task 9 (`POST /job-search/search`, synchronous)
- Two-step validation (free selection, then diagnostic+personalization only for selected offers) → selection is frontend-only (no backend task needed for it); Task 10/11 is the "diagnostic for this one offer" step; CV/lettre generation reuses the existing sous-projet 3 endpoints unmodified
- Reuse of sous-projet 1/3 pipelines rather than duplication → Task 10 calls `evaluate_structure`/`SemanticAnalyzer`/`build_diagnostic_report` directly; personalization endpoints are untouched and reused as-is in Task 17's tests
- `CandidateProfile` with contact fields + reference CV → Tasks 1, 3
- Dedup via `(user_id, offer_url)` → Task 2 (constraint), Task 10 (checked before any LLM call)
- Auto-submit only for Greenhouse/Lever via direct HTTP adapters, no headless browser → Tasks 12, 14, 15
- Custom fields answered by LLM but always shown for review before submission → Task 17 (`GET .../prefilled-form` always returns the form for review; `POST .../confirm` is a separate, explicit step)
- No retry on submission failure → Task 17 (`confirm_application`, single attempt)
- Auto-submit blocked until required profile fields are filled → Task 17 (`missing_required_profile_fields`, checked in both `GET .../prefilled-form` and `POST .../confirm`)
- Assisted mode for non-ATS offers (LinkedIn/Indeed/custom) → Task 17 (`confirm_application` with `ats_type=None` → `a_soumettre_manuellement`), `mark-sent` endpoint
- RGPD purge extended to `Application` → Task 18
- No third-party user credentials stored → true throughout; the only secrets added are application-level (Tasks 5, 6)
- Rate limiting on search (protects free-tier API quotas) → Task 9
- Mandatory manual end-to-end test before enabling auto-submit in production → Task 15, Step 6

**Placeholder scan:** no `TBD`/`TODO`, no "add error handling" style steps — every step has real code and every error path names its exception type and HTTP status.

**Type consistency:** `Application.status` string constants (`APPLICATION_STATUS_*`, Task 2) are the same names imported and compared against in Tasks 17–18; `FormField`/`DiscoveredForm` (Task 12) are the same shapes threaded unchanged through `HtmlFormAdapter` (Task 12), `GreenhouseAdapter`/`LeverAdapter` (Tasks 14–15), and the router (Task 17); `CandidateProfile.cv_text`/`cv_has_tables`/`cv_has_multi_column`/`cv_has_images`/`cv_detected_sections` (Task 1) are read back with matching names in Task 10's `CVParseResult` reconstruction.

**Not covered by this plan (frontend):** the `/candidatures` search-and-select page, `/profil` page, and `/historique` extension are covered by a separate frontend plan, per the same backend/frontend split used for the diagnostic and personalization sous-projets.
