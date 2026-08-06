# Personnalisation (CV + lettre) — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend for generating an optimized CV and a tailored cover letter (both as PDFs) from an existing diagnostic, per `docs/superpowers/specs/2026-08-06-personnalisation-design.md`.

**Architecture:** New `app/personalization/` module (Claude Sonnet tool-use rewriting + deterministic anti-hallucination check + PDF rendering) and `app/storage/` module (MinIO/S3 client), wired into a new `app/routers/personalization.py` router. Reuses the existing `Diagnostic` row's `cv_text`/`offer_text`/`missing_keywords`/`recommendations` — no new user input is collected.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, `anthropic` SDK (Claude Sonnet 5, forced tool-use), `fpdf2` (PDF rendering), `boto3` (S3-compatible client against MinIO), pytest.

## Global Constraints

- LLM model for personalization: `claude-sonnet-5`, called via forced tool use, with exactly 1 retry on failure before raising an error (same pattern as the diagnostic's `SemanticAnalyzer`).
- CV rewriting prompt must explicitly forbid inventing experience, skills, employers, dates, or qualifications not already present in the original CV.
- Exactly one PDF template per document kind (`cv`, `lettre`) — no template choice, no DOCX export in this version.
- One "current" document per `(diagnostic_id, kind)` — regenerating overwrites the previous version (DB row upsert + MinIO object overwrite at the same key), no version history.
- Personalization rate limit: 10 generations per user per hour, CV and lettre combined — separate counter from the existing 10-diagnostics-per-hour limit.
- `DELETE /diagnostics` (existing RGPD purge endpoint) must also delete the user's `PersonalizedDocument` rows and their MinIO objects.
- Never block a personalization generation on the deterministic anti-hallucination check — it only sets a `needs_review` flag, it never rejects the LLM output.

---

### Task 1: Infrastructure — MinIO service, settings, dependencies

**Files:**
- Modify: `docker-compose.yml`
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Produces: `Settings.minio_endpoint: str`, `Settings.minio_access_key: str`, `Settings.minio_secret_key: str`, `Settings.minio_bucket: str` (all with local-dev defaults matching docker-compose, so existing `.env` files and the test suite keep working without changes)
- Produces: `boto3` and `fpdf2` available as production dependencies (`fpdf2` moves from dev-only to production — it already ships in `requirements-dev.txt` for test fixtures in the diagnostic sub-project)

This task has no application code of its own to unit-test — it's config/infrastructure. Verify it by running the existing full test suite (must stay green) and by confirming Docker Compose parses.

- [ ] **Step 1: Add the MinIO service and a one-shot bucket-creation service to `docker-compose.yml`**

Modify `docker-compose.yml` — add two new services (`minio`, `createbuckets`), a new volume, and update the `backend` service's `environment`/`depends_on`:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ats_diagnostic
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10
    ports:
      - "5432:5432"

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 5s
      retries: 10
    ports:
      - "9000:9000"
      - "9001:9001"

  createbuckets:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 minioadmin minioadmin &&
      mc mb --ignore-existing local/personalization
      "

  backend:
    build: ./backend
    env_file:
      - ./backend/.env
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/ats_diagnostic
      MINIO_ENDPOINT: http://minio:9000
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
      MINIO_BUCKET: personalization
    depends_on:
      db:
        condition: service_healthy
      createbuckets:
        condition: service_completed_successfully
    ports:
      - "8000:8000"

  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      - backend
    ports:
      - "3000:3000"

volumes:
  db_data:
  minio_data:
```

The bucket is created out-of-band by the `createbuckets` init container (a common MinIO Compose idiom), not by the FastAPI app at startup — this keeps the app's `boto3` client construction lazy (no network call), so it never blocks or fails app startup/tests when MinIO isn't reachable (e.g. the backend test suite, which never runs MinIO).

- [ ] **Step 2: Add `boto3` to production requirements, promote `fpdf2`**

`backend/requirements.txt` (append `boto3`, add `fpdf2`):
```
fastapi
uvicorn[standard]
sqlalchemy>=2.0
psycopg2-binary
pydantic>=2.0
pydantic-settings
email-validator
bcrypt
pyjwt
python-multipart
pdfplumber
python-docx
httpx
beautifulsoup4
anthropic
boto3
fpdf2
```

`backend/requirements-dev.txt` (remove `fpdf2` — now in `requirements.txt`, pulled in transitively via `-r requirements.txt`):
```
-r requirements.txt
pytest
respx
pillow
```

- [ ] **Step 3: Add MinIO settings with local-dev defaults**

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Defaults match the docker-compose values so local dev and the test suite work without any `.env` changes; production deployments override them via `backend/.env`.

- [ ] **Step 4: Document the new settings in `.env.example`**

Modify `backend/.env.example`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/ats_diagnostic
JWT_SECRET=change-me
ANTHROPIC_API_KEY=sk-ant-...
CORS_ORIGINS=["http://localhost:3000"]
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=personalization
```

- [ ] **Step 5: Install the new dependency and verify the existing suite is unaffected**

Run:
```bash
cd backend && pip install -r requirements-dev.txt && pytest -q
```
Expected: PASS (no test references the new settings yet, but this confirms `Settings()` still constructs cleanly with the new fields present and defaulted).

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml backend/requirements.txt backend/requirements-dev.txt backend/app/config.py backend/.env.example
git commit -m "chore: add MinIO service and settings for personalization"
```

---

### Task 2: Data model — `PersonalizedDocument` and `PersonalizationRequestLog`

**Files:**
- Create: `backend/app/models/personalized_document.py`
- Create: `backend/app/models/personalization_request_log.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/__init__.py` (already exists — no change needed)
- Test: `backend/tests/models/test_personalized_document.py`
- Test: `backend/tests/models/test_personalization_request_log.py`

**Interfaces:**
- Produces: `PersonalizedDocument` ORM model — fields `id`, `diagnostic_id`, `kind: str`, `storage_key: str`, `needs_review: bool`, `created_at`, `updated_at`; unique constraint on `(diagnostic_id, kind)`
- Produces: `PersonalizationRequestLog` ORM model — fields `id`, `user_id`, `created_at`

- [ ] **Step 1: Write the failing tests**

`backend/tests/models/test_personalized_document.py`:
```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
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


def test_create_personalized_document_linked_to_diagnostic(db_session):
    diagnostic = _make_diagnostic(db_session)

    document = PersonalizedDocument(
        diagnostic_id=diagnostic.id,
        kind="cv",
        storage_key="users/1/diagnostics/1/cv.pdf",
        needs_review=False,
    )
    db_session.add(document)
    db_session.commit()

    fetched = db_session.query(PersonalizedDocument).filter(PersonalizedDocument.diagnostic_id == diagnostic.id).first()
    assert fetched.kind == "cv"
    assert fetched.storage_key == "users/1/diagnostics/1/cv.pdf"
    assert fetched.needs_review is False
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


def test_unique_constraint_on_diagnostic_id_and_kind(db_session):
    diagnostic = _make_diagnostic(db_session)
    db_session.add(PersonalizedDocument(diagnostic_id=diagnostic.id, kind="cv", storage_key="key-1", needs_review=False))
    db_session.commit()

    db_session.add(PersonalizedDocument(diagnostic_id=diagnostic.id, kind="cv", storage_key="key-2", needs_review=False))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_same_diagnostic_can_have_one_cv_and_one_lettre(db_session):
    diagnostic = _make_diagnostic(db_session)
    db_session.add(PersonalizedDocument(diagnostic_id=diagnostic.id, kind="cv", storage_key="key-cv", needs_review=False))
    db_session.add(PersonalizedDocument(diagnostic_id=diagnostic.id, kind="lettre", storage_key="key-lettre", needs_review=False))
    db_session.commit()  # should not raise

    assert db_session.query(PersonalizedDocument).filter(PersonalizedDocument.diagnostic_id == diagnostic.id).count() == 2
```

`backend/tests/models/test_personalization_request_log.py`:
```python
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.user import User


def test_create_personalization_request_log_linked_to_user(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(PersonalizationRequestLog(user_id=user.id))
    db_session.commit()

    fetched = db_session.query(PersonalizationRequestLog).filter(PersonalizationRequestLog.user_id == user.id).first()
    assert fetched.created_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/models/test_personalized_document.py tests/models/test_personalization_request_log.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.personalized_document'`

- [ ] **Step 3: Implement the models**

`backend/app/models/personalized_document.py`:
```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PersonalizedDocument(Base):
    __tablename__ = "personalized_documents"
    __table_args__ = (
        UniqueConstraint("diagnostic_id", "kind", name="uq_personalized_document_diagnostic_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostics.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    diagnostic: Mapped["Diagnostic"] = relationship()
```

`backend/app/models/personalization_request_log.py`:
```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PersonalizationRequestLog(Base):
    """Append-only log of successful CV/lettre generations.

    Used only to enforce the personalization rate limit
    (app.rate_limit.limiter.check_personalization_rate_limit). Kept separate
    from PersonalizedDocument, which stores at most one row per
    (diagnostic, kind) and is overwritten on regeneration - a row count on
    that table would not reflect how many generations actually happened.
    """

    __tablename__ = "personalization_request_logs"

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

__all__ = ["User", "Diagnostic", "PersonalizedDocument", "PersonalizationRequestLog"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/models/test_personalized_document.py tests/models/test_personalization_request_log.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/personalized_document.py backend/app/models/personalization_request_log.py backend/app/models/__init__.py backend/tests/models/test_personalized_document.py backend/tests/models/test_personalization_request_log.py
git commit -m "feat: add PersonalizedDocument and PersonalizationRequestLog models"
```

---

### Task 3: Object storage client (MinIO/S3)

**Files:**
- Create: `backend/app/storage/__init__.py`
- Create: `backend/app/storage/client.py`
- Create: `backend/app/storage/dependencies.py`
- Test: `backend/tests/storage/__init__.py`
- Test: `backend/tests/storage/test_client.py`
- Test: `backend/tests/storage/test_dependencies.py`

**Interfaces:**
- Consumes: `Settings` (Task 1 — `minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_bucket`)
- Produces: `ObjectStorage` class with `.upload(key: str, content: bytes) -> None`, `.download(key: str) -> bytes`, `.delete(key: str) -> None`
- Produces: `ObjectStorageError(Exception)`
- Produces: `get_object_storage() -> ObjectStorage` (lru_cached dependency provider, mirrors `get_semantic_analyzer`)

- [ ] **Step 1: Write the failing tests**

`backend/tests/storage/__init__.py`:
```python
```

`backend/tests/storage/test_client.py`:
```python
import pytest
from botocore.exceptions import ClientError

from app.storage.client import ObjectStorage, ObjectStorageError


class FakeBotoClient:
    """Minimal stand-in for a boto3 S3 client's put/get/delete_object methods."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.fail_next = False

    def put_object(self, Bucket, Key, Body, ContentType):
        if self.fail_next:
            raise ClientError({"Error": {"Code": "500", "Message": "boom"}}, "PutObject")
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if self.fail_next:
            raise ClientError({"Error": {"Code": "500", "Message": "boom"}}, "GetObject")
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject")

        class _Body:
            def read(self_inner) -> bytes:
                return self.objects[Key]

        return {"Body": _Body()}

    def delete_object(self, Bucket, Key):
        if self.fail_next:
            raise ClientError({"Error": {"Code": "500", "Message": "boom"}}, "DeleteObject")
        self.objects.pop(Key, None)


def test_upload_then_download_roundtrips_bytes():
    client = FakeBotoClient()
    storage = ObjectStorage(client, "bucket")

    storage.upload("key.pdf", b"%PDF-1.4 fake content")

    assert storage.download("key.pdf") == b"%PDF-1.4 fake content"


def test_upload_wraps_client_error():
    client = FakeBotoClient()
    client.fail_next = True
    storage = ObjectStorage(client, "bucket")

    with pytest.raises(ObjectStorageError):
        storage.upload("key.pdf", b"data")


def test_download_wraps_client_error_on_missing_key():
    client = FakeBotoClient()
    storage = ObjectStorage(client, "bucket")

    with pytest.raises(ObjectStorageError):
        storage.download("missing.pdf")


def test_delete_removes_object():
    client = FakeBotoClient()
    storage = ObjectStorage(client, "bucket")
    storage.upload("key.pdf", b"data")

    storage.delete("key.pdf")

    with pytest.raises(ObjectStorageError):
        storage.download("key.pdf")
```

`backend/tests/storage/test_dependencies.py`:
```python
from app.storage.dependencies import get_object_storage


def test_get_object_storage_uses_configured_bucket():
    get_object_storage.cache_clear()
    storage = get_object_storage()

    assert storage._bucket == "personalization"

    get_object_storage.cache_clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/storage -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.storage'`

- [ ] **Step 3: Implement the storage client**

`backend/app/storage/__init__.py`:
```python
```

`backend/app/storage/client.py`:
```python
from botocore.exceptions import BotoCoreError, ClientError


class ObjectStorageError(Exception):
    pass


class ObjectStorage:
    def __init__(self, client, bucket: str):
        self._client = client
        self._bucket = bucket

    def upload(self, key: str, content: bytes) -> None:
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=content, ContentType="application/pdf")
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(f"Échec de l'upload de l'objet '{key}'.") from exc

    def download(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(f"Échec du téléchargement de l'objet '{key}'.") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(f"Échec de la suppression de l'objet '{key}'.") from exc
```

`backend/app/storage/dependencies.py`:
```python
from functools import lru_cache

import boto3

from app.config import get_settings
from app.storage.client import ObjectStorage


@lru_cache
def get_object_storage() -> ObjectStorage:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",
    )
    return ObjectStorage(client, settings.minio_bucket)
```

`boto3.client(...)` does not perform any network I/O at construction time (the connection is only opened on the first actual call like `put_object`), so this dependency is safe to construct during tests even though no MinIO instance is running there — tests override `get_object_storage` with a fake before any request that would actually call it (see Task 8).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/storage -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/storage backend/tests/storage
git commit -m "feat: add MinIO-backed object storage client"
```

---

### Task 4: Structured content schemas and PDF rendering

**Files:**
- Create: `backend/app/personalization/__init__.py`
- Create: `backend/app/personalization/schemas.py`
- Create: `backend/app/personalization/pdf_generator.py`
- Test: `backend/tests/personalization/__init__.py`
- Test: `backend/tests/personalization/test_pdf_generator.py`

**Interfaces:**
- Produces: `CvExperienceEntry(BaseModel)` — `title: str`, `company: str`, `dates: str`, `bullets: list[str]`
- Produces: `RewrittenCv(BaseModel)` — `summary: str`, `experience: list[CvExperienceEntry]`, `education: list[str]`, `skills: list[str]`
- Produces: `CoverLetter(BaseModel)` — `greeting: str`, `body_paragraphs: list[str]`, `closing: str`
- Produces: `render_cv_pdf(cv: RewrittenCv) -> bytes`, `render_cover_letter_pdf(letter: CoverLetter) -> bytes`

- [ ] **Step 1: Write the failing tests**

`backend/tests/personalization/__init__.py`:
```python
```

`backend/tests/personalization/test_pdf_generator.py`:
```python
from app.personalization.pdf_generator import render_cover_letter_pdf, render_cv_pdf
from app.personalization.schemas import CoverLetter, CvExperienceEntry, RewrittenCv


def test_render_cv_pdf_returns_nonempty_pdf_bytes():
    cv = RewrittenCv(
        summary="Résumé optimisé pour cette offre.",
        experience=[
            CvExperienceEntry(
                title="Développeuse Full Stack",
                company="TechCorp Solutions",
                dates="2020-2022",
                bullets=["A conçu et déployé des API REST performantes."],
            )
        ],
        education=["Master Informatique, Université Paris-Saclay, 2019"],
        skills=["Python", "Docker", "PostgreSQL"],
    )

    pdf_bytes = render_cv_pdf(cv)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_render_cover_letter_pdf_returns_nonempty_pdf_bytes():
    letter = CoverLetter(
        greeting="Madame, Monsieur,",
        body_paragraphs=[
            "Je vous écris pour candidater au poste de développeuse.",
            "Mon expérience chez TechCorp Solutions correspond à vos besoins.",
        ],
        closing="Cordialement, Jane Doe",
    )

    pdf_bytes = render_cover_letter_pdf(letter)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/personalization/test_pdf_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.personalization'`

- [ ] **Step 3: Implement schemas and PDF rendering**

`backend/app/personalization/__init__.py`:
```python
```

`backend/app/personalization/schemas.py`:
```python
from pydantic import BaseModel


class CvExperienceEntry(BaseModel):
    title: str
    company: str
    dates: str
    bullets: list[str]


class RewrittenCv(BaseModel):
    summary: str
    experience: list[CvExperienceEntry]
    education: list[str]
    skills: list[str]


class CoverLetter(BaseModel):
    greeting: str
    body_paragraphs: list[str]
    closing: str
```

`backend/app/personalization/pdf_generator.py`:
```python
from fpdf import FPDF

from app.personalization.schemas import CoverLetter, RewrittenCv


def render_cv_pdf(cv: RewrittenCv) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, "CV")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, cv.summary)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, "Expérience")
    for entry in cv.experience:
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 6, f"{entry.title} - {entry.company} ({entry.dates})")
        pdf.set_font("Helvetica", "", 11)
        for bullet in entry.bullets:
            pdf.multi_cell(0, 6, f"- {bullet}")
        pdf.ln(2)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, "Formation")
    pdf.set_font("Helvetica", "", 11)
    for item in cv.education:
        pdf.multi_cell(0, 6, item)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, "Compétences")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, ", ".join(cv.skills))

    return bytes(pdf.output())


def render_cover_letter_pdf(letter: CoverLetter) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 11)

    pdf.multi_cell(0, 6, letter.greeting)
    pdf.ln(4)
    for paragraph in letter.body_paragraphs:
        pdf.multi_cell(0, 6, paragraph)
        pdf.ln(3)
    pdf.ln(2)
    pdf.multi_cell(0, 6, letter.closing)

    return bytes(pdf.output())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/personalization/test_pdf_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/personalization/__init__.py backend/app/personalization/schemas.py backend/app/personalization/pdf_generator.py backend/tests/personalization/__init__.py backend/tests/personalization/test_pdf_generator.py
git commit -m "feat: add personalization content schemas and PDF rendering"
```

---

### Task 5: Deterministic anti-hallucination verification

**Files:**
- Create: `backend/app/personalization/verification.py`
- Test: `backend/tests/personalization/test_verification.py`

**Interfaces:**
- Consumes: `RewrittenCv`, `CvExperienceEntry` (Task 4)
- Produces: `cv_needs_review(original_cv_text: str, rewritten: RewrittenCv) -> bool`

- [ ] **Step 1: Write the failing tests**

`backend/tests/personalization/test_verification.py`:
```python
from app.personalization.schemas import CvExperienceEntry, RewrittenCv
from app.personalization.verification import cv_needs_review

_ORIGINAL_CV_TEXT = (
    "Jane Doe\n"
    "Expérience professionnelle\n"
    "Développeuse Full Stack chez TechCorp Solutions, 2020-2022\n"
    "- A conçu des API REST\n"
    "Formation\n"
    "Master Informatique, Université Paris-Saclay, 2019\n"
    "Compétences\n"
    "Python, Docker, PostgreSQL"
)


def test_returns_false_when_rewritten_only_reformulates_existing_content():
    rewritten = RewrittenCv(
        summary="Développeuse Full Stack expérimentée, spécialisée dans les API REST.",
        experience=[
            CvExperienceEntry(
                title="Développeuse Full Stack",
                company="TechCorp Solutions",
                dates="2020-2022",
                bullets=["A conçu et déployé des API REST performantes."],
            )
        ],
        education=["Master Informatique, Université Paris-Saclay, 2019"],
        skills=["Python", "Docker", "PostgreSQL"],
    )

    assert cv_needs_review(_ORIGINAL_CV_TEXT, rewritten) is False


def test_returns_true_when_rewritten_introduces_an_unknown_employer():
    rewritten = RewrittenCv(
        summary="Développeuse Full Stack expérimentée.",
        experience=[
            CvExperienceEntry(
                title="Développeuse Full Stack",
                company="Global Innovations Group",
                dates="2020-2022",
                bullets=["A conçu des API REST."],
            )
        ],
        education=["Master Informatique, Université Paris-Saclay, 2019"],
        skills=["Python", "Docker", "PostgreSQL"],
    )

    assert cv_needs_review(_ORIGINAL_CV_TEXT, rewritten) is True


def test_returns_true_when_rewritten_introduces_an_unknown_date():
    rewritten = RewrittenCv(
        summary="Développeuse Full Stack expérimentée.",
        experience=[
            CvExperienceEntry(
                title="Développeuse Full Stack",
                company="TechCorp Solutions",
                dates="2018-2021",
                bullets=["A conçu des API REST."],
            )
        ],
        education=["Master Informatique, Université Paris-Saclay, 2019"],
        skills=["Python", "Docker", "PostgreSQL"],
    )

    assert cv_needs_review(_ORIGINAL_CV_TEXT, rewritten) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/personalization/test_verification.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.personalization.verification'`

- [ ] **Step 3: Implement the deterministic check**

`backend/app/personalization/verification.py`:
```python
import re

from app.personalization.schemas import RewrittenCv

# Non-capturing groups so `.findall()` returns whole matches, not sub-groups.
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_PROPER_NOUN_RE = re.compile(r"\b[A-ZÀ-Ý][\wÀ-ÿ'&.-]*(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'&.-]*){1,3}\b")


def _extract_reference_terms(text: str) -> set[str]:
    years = set(_YEAR_RE.findall(text))
    proper_nouns = {match.strip().lower() for match in _PROPER_NOUN_RE.findall(text)}
    return years | proper_nouns


def cv_needs_review(original_cv_text: str, rewritten: RewrittenCv) -> bool:
    """Lightweight, deterministic anti-hallucination guard for a rewritten CV.

    Compares 4-digit years and multi-word capitalized phrases (a cheap proxy
    for employer names, school names, and dates - the most damaging things
    to hallucinate) between the original CV text and the rewritten CV. If
    the rewritten CV mentions one that isn't in the original, it's flagged
    for the user to double-check. This never blocks generation - it only
    sets a flag - and it deliberately does not call a second LLM to verify,
    per the design spec.
    """
    original_terms = _extract_reference_terms(original_cv_text)

    rewritten_text = "\n".join(
        [
            rewritten.summary,
            *(
                f"{entry.title} {entry.company} {entry.dates} {' '.join(entry.bullets)}"
                for entry in rewritten.experience
            ),
            *rewritten.education,
            *rewritten.skills,
        ]
    )
    rewritten_terms = _extract_reference_terms(rewritten_text)

    return not rewritten_terms.issubset(original_terms)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/personalization/test_verification.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/personalization/verification.py backend/tests/personalization/test_verification.py
git commit -m "feat: add deterministic anti-hallucination check for rewritten CVs"
```

---

### Task 6: CV Rewriter and Cover Letter Generator (Claude Sonnet)

**Files:**
- Create: `backend/app/personalization/analyzer.py`
- Create: `backend/app/personalization/dependencies.py`
- Test: `backend/tests/personalization/test_analyzer.py`
- Test: `backend/tests/personalization/test_dependencies.py`

**Interfaces:**
- Consumes: `RewrittenCv`, `CoverLetter` (Task 4)
- Produces: `PersonalizationError(Exception)`
- Produces: `CvRewriter.rewrite(cv_text: str, offer_text: str, missing_keywords: list[str], recommendations: list[str]) -> RewrittenCv`
- Produces: `CoverLetterGenerator.generate(cv_text: str, offer_text: str, missing_keywords: list[str], recommendations: list[str]) -> CoverLetter`
- Produces: `get_cv_rewriter() -> CvRewriter`, `get_cover_letter_generator() -> CoverLetterGenerator` (lru_cached dependency providers)

- [ ] **Step 1: Write the failing tests**

`backend/tests/personalization/test_analyzer.py`:
```python
from types import SimpleNamespace

import anthropic
import pytest

from app.personalization.analyzer import CoverLetterGenerator, CvRewriter, PersonalizationError


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


_VALID_CV_PAYLOAD = {
    "summary": "Résumé optimisé.",
    "experience": [
        {"title": "Développeuse", "company": "Acme", "dates": "2020-2022", "bullets": ["A conçu des API."]}
    ],
    "education": ["Master Informatique"],
    "skills": ["Python", "Docker"],
}

_VALID_LETTER_PAYLOAD = {
    "greeting": "Madame, Monsieur,",
    "body_paragraphs": ["Je vous écris pour candidater à ce poste."],
    "closing": "Cordialement, Jane Doe",
}


def test_rewrite_returns_parsed_cv_on_valid_response():
    client = FakeClient([_fake_tool_use_response(_VALID_CV_PAYLOAD)])
    rewriter = CvRewriter(client)

    cv = rewriter.rewrite("cv text", "offer text", ["Docker"], ["Add Docker"])

    assert cv.summary == "Résumé optimisé."
    assert cv.experience[0].company == "Acme"
    assert client.messages.calls[0]["tool_choice"] == {"type": "tool", "name": "submit_rewritten_cv"}
    assert client.messages.calls[0]["model"] == "claude-sonnet-5"


def test_rewrite_retries_once_on_invalid_payload_then_succeeds():
    client = FakeClient(
        [
            _fake_tool_use_response({"summary": "x"}),
            _fake_tool_use_response(_VALID_CV_PAYLOAD),
        ]
    )
    rewriter = CvRewriter(client)

    cv = rewriter.rewrite("cv text", "offer text", [], [])

    assert cv.summary == "Résumé optimisé."
    assert len(client.messages.calls) == 2


def test_rewrite_raises_after_two_failures():
    client = FakeClient([_fake_tool_use_response({"summary": "x"}), _fake_tool_use_response({"summary": "y"})])
    rewriter = CvRewriter(client)

    with pytest.raises(PersonalizationError):
        rewriter.rewrite("cv text", "offer text", [], [])


def test_rewrite_retries_on_api_error():
    client = FakeClient(
        [anthropic.APIConnectionError(request=SimpleNamespace()), _fake_tool_use_response(_VALID_CV_PAYLOAD)]
    )
    rewriter = CvRewriter(client)

    cv = rewriter.rewrite("cv text", "offer text", [], [])
    assert cv.summary == "Résumé optimisé."


def test_generate_returns_parsed_letter_on_valid_response():
    client = FakeClient([_fake_tool_use_response(_VALID_LETTER_PAYLOAD)])
    generator = CoverLetterGenerator(client)

    letter = generator.generate("cv text", "offer text", [], [])

    assert letter.greeting == "Madame, Monsieur,"
    assert letter.body_paragraphs == ["Je vous écris pour candidater à ce poste."]
    assert client.messages.calls[0]["tool_choice"] == {"type": "tool", "name": "submit_cover_letter"}


def test_generate_raises_after_two_failures():
    client = FakeClient([_fake_tool_use_response({"greeting": "x"}), _fake_tool_use_response({"greeting": "y"})])
    generator = CoverLetterGenerator(client)

    with pytest.raises(PersonalizationError):
        generator.generate("cv text", "offer text", [], [])
```

`backend/tests/personalization/test_dependencies.py`:
```python
from app.personalization.dependencies import get_cover_letter_generator, get_cv_rewriter


def test_cv_rewriter_client_has_bounded_timeout_and_no_sdk_retries():
    get_cv_rewriter.cache_clear()
    rewriter = get_cv_rewriter()
    client = rewriter._client

    assert client.timeout == 60.0
    assert client.max_retries == 0

    get_cv_rewriter.cache_clear()


def test_cover_letter_generator_client_has_bounded_timeout_and_no_sdk_retries():
    get_cover_letter_generator.cache_clear()
    generator = get_cover_letter_generator()
    client = generator._client

    assert client.timeout == 60.0
    assert client.max_retries == 0

    get_cover_letter_generator.cache_clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/personalization/test_analyzer.py tests/personalization/test_dependencies.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.personalization.analyzer'`

- [ ] **Step 3: Implement the analyzer and dependencies**

`backend/app/personalization/analyzer.py`:
```python
import anthropic
from pydantic import BaseModel, ValidationError

from app.personalization.schemas import CoverLetter, RewrittenCv

PERSONALIZATION_MODEL = "claude-sonnet-5"

_MAX_ATTEMPTS = 2

_ANTI_HALLUCINATION_INSTRUCTIONS = (
    "Do not invent any experience, skill, employer, date, or qualification "
    "that is not already present in the original CV. Only reformulate, "
    "reorganize, and emphasize what is already there, using vocabulary from "
    "the job offer where genuinely applicable."
)

_CV_REWRITE_TOOL = {
    "name": "submit_rewritten_cv",
    "description": "Submit the CV rewritten and optimized for the target job offer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Short professional summary/hook at the top of the CV, tailored to the offer.",
            },
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "company": {"type": "string"},
                        "dates": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "company", "dates", "bullets"],
                },
                "description": "Work experience entries, reworded to highlight relevance to the offer.",
            },
            "education": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Education entries, unchanged in substance from the original CV.",
            },
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skills list, reordered/reworded to surface those matching the offer.",
            },
        },
        "required": ["summary", "experience", "education", "skills"],
    },
}

_COVER_LETTER_TOOL = {
    "name": "submit_cover_letter",
    "description": "Submit the generated cover letter for the target job offer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "greeting": {"type": "string", "description": "Opening line, e.g. 'Madame, Monsieur,'."},
            "body_paragraphs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Body paragraphs of the letter, in order.",
            },
            "closing": {"type": "string", "description": "Closing formula, e.g. 'Cordialement, ...'."},
        },
        "required": ["greeting", "body_paragraphs", "closing"],
    },
}


class PersonalizationError(Exception):
    pass


def _submit_via_tool_use(
    client,
    model: str,
    max_tokens: int,
    tool: dict,
    prompt: str,
    schema_cls: type[BaseModel],
):
    last_error: Exception | None = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{"role": "user", "content": prompt}],
            )
            tool_use = next((block for block in response.content if block.type == "tool_use"), None)
            if tool_use is None:
                raise PersonalizationError("No tool_use block in Claude response")
            return schema_cls.model_validate(tool_use.input)
        except (ValidationError, PersonalizationError, anthropic.APIError) as exc:
            last_error = exc
            continue
    raise PersonalizationError(f"Personalization call failed after retries: {last_error}")


class CvRewriter:
    def __init__(self, client, model: str = PERSONALIZATION_MODEL):
        self._client = client
        self._model = model

    def rewrite(
        self,
        cv_text: str,
        offer_text: str,
        missing_keywords: list[str],
        recommendations: list[str],
    ) -> RewrittenCv:
        prompt = (
            f"{_ANTI_HALLUCINATION_INSTRUCTIONS}\n\n"
            "Rewrite this CV to better match the job offer. The CV and offer "
            "may be in French or English; respond in the same language as "
            "the CV.\n\n"
            f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}\n\n"
            f"Missing keywords identified by a prior diagnostic: {missing_keywords}\n"
            f"Recommendations from a prior diagnostic: {recommendations}"
        )
        return _submit_via_tool_use(self._client, self._model, 4096, _CV_REWRITE_TOOL, prompt, RewrittenCv)


class CoverLetterGenerator:
    def __init__(self, client, model: str = PERSONALIZATION_MODEL):
        self._client = client
        self._model = model

    def generate(
        self,
        cv_text: str,
        offer_text: str,
        missing_keywords: list[str],
        recommendations: list[str],
    ) -> CoverLetter:
        prompt = (
            "Write a cover letter for this candidate applying to this job "
            "offer, based only on their CV - do not invent experience or "
            "skills not present in the CV. The CV and offer may be in "
            "French or English; respond in the same language as the CV.\n\n"
            f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}\n\n"
            f"Missing keywords identified by a prior diagnostic: {missing_keywords}\n"
            f"Recommendations from a prior diagnostic: {recommendations}"
        )
        return _submit_via_tool_use(self._client, self._model, 2048, _COVER_LETTER_TOOL, prompt, CoverLetter)
```

`backend/app/personalization/dependencies.py`:
```python
from functools import lru_cache

import anthropic

from app.config import get_settings
from app.personalization.analyzer import CoverLetterGenerator, CvRewriter


def _build_client() -> anthropic.Anthropic:
    settings = get_settings()
    # Same reasoning as app.llm_analyzer.dependencies.get_semantic_analyzer:
    # this call holds the per-user rate-limit row lock for its duration, so
    # it must not be allowed to hang for the SDK's very-long default
    # timeout. max_retries=0 avoids double-retrying on top of the
    # 2-attempt retry loop in app.personalization.analyzer. The timeout is
    # higher than the diagnostic's 30s because CV rewriting produces more
    # output tokens.
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=60.0,
        max_retries=0,
    )


@lru_cache
def get_cv_rewriter() -> CvRewriter:
    return CvRewriter(_build_client())


@lru_cache
def get_cover_letter_generator() -> CoverLetterGenerator:
    return CoverLetterGenerator(_build_client())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/personalization/test_analyzer.py tests/personalization/test_dependencies.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/personalization/analyzer.py backend/app/personalization/dependencies.py backend/tests/personalization/test_analyzer.py backend/tests/personalization/test_dependencies.py
git commit -m "feat: add Claude Sonnet CV rewriter and cover letter generator"
```

---

### Task 7: Personalization rate limiting

**Files:**
- Modify: `backend/app/rate_limit/limiter.py`
- Modify: `backend/tests/rate_limit/test_limiter.py`

**Interfaces:**
- Consumes: `PersonalizationRequestLog` (Task 2)
- Produces: `MAX_PERSONALIZATIONS_PER_HOUR: int`, `check_personalization_rate_limit(db: Session, user_id: int) -> None` (raises `RateLimitExceeded`)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/rate_limit/test_limiter.py`:
```python
from app.models.personalization_request_log import PersonalizationRequestLog
from app.rate_limit.limiter import MAX_PERSONALIZATIONS_PER_HOUR, check_personalization_rate_limit


def _add_personalization_logs(db_session, user_id: int, count: int) -> None:
    for _ in range(count):
        db_session.add(PersonalizationRequestLog(user_id=user_id))
    db_session.commit()


def test_personalization_allows_under_limit(db_session):
    user = _make_user(db_session)
    _add_personalization_logs(db_session, user.id, MAX_PERSONALIZATIONS_PER_HOUR - 1)
    check_personalization_rate_limit(db_session, user.id)  # should not raise


def test_personalization_blocks_at_limit(db_session):
    user = _make_user(db_session)
    _add_personalization_logs(db_session, user.id, MAX_PERSONALIZATIONS_PER_HOUR)
    import pytest

    with pytest.raises(RateLimitExceeded):
        check_personalization_rate_limit(db_session, user.id)


def test_diagnostic_and_personalization_rate_limits_are_independent(db_session):
    user = _make_user(db_session)
    _add_diagnostics(db_session, user.id, MAX_DIAGNOSTICS_PER_HOUR)
    # The diagnostic limit is maxed out, but personalization has its own counter.
    check_personalization_rate_limit(db_session, user.id)  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/rate_limit/test_limiter.py -v`
Expected: FAIL with `ImportError: cannot import name 'MAX_PERSONALIZATIONS_PER_HOUR'`

- [ ] **Step 3: Implement the new rate-limit check**

Modify `backend/app/rate_limit/limiter.py` (append to the existing file, which already has `lock_user_for_rate_limit`, `check_rate_limit`, `RateLimitExceeded`):
```python
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.diagnostic import Diagnostic
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.user import User

MAX_DIAGNOSTICS_PER_HOUR = 10
MAX_PERSONALIZATIONS_PER_HOUR = 10


class RateLimitExceeded(Exception):
    pass


def lock_user_for_rate_limit(db: Session, user_id: int) -> None:
    """Take a row lock on the user's own User row for the rest of the request.

    This serializes diagnostic creation per-user so the rate-limit check and
    the resulting insert are effectively atomic with respect to other
    concurrent requests from the same user, closing a TOCTOU race where N
    concurrent requests could all pass `check_rate_limit` before any of
    their Diagnostic rows exist. Reused as-is by the personalization
    endpoints for the same reason.

    PostgreSQL supports `SELECT ... FOR UPDATE` row-level locking; SQLite
    (used in this project's test suite) does not support meaningful
    row-level locking, so on SQLite this is a no-op. That's safe because the
    test suite never issues concurrent requests against the same SQLite
    connection/session, and production runs on PostgreSQL, where the lock
    genuinely applies.
    """
    query = select(User.id).where(User.id == user_id)
    if db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    db.execute(query)


def check_rate_limit(db: Session, user_id: int) -> None:
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count()).select_from(Diagnostic).where(
            Diagnostic.user_id == user_id,
            Diagnostic.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_DIAGNOSTICS_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_DIAGNOSTICS_PER_HOUR} diagnostics par heure atteinte. Réessaie plus tard."
        )


def check_personalization_rate_limit(db: Session, user_id: int) -> None:
    """Counts CV and lettre generations combined, over the last hour.

    Backed by PersonalizationRequestLog rather than PersonalizedDocument
    because the latter is upserted (one row per diagnostic+kind, overwritten
    on regeneration) and would not reflect how many generations actually
    happened - repeated regenerations of the same document would only ever
    count as one row.
    """
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count()).select_from(PersonalizationRequestLog).where(
            PersonalizationRequestLog.user_id == user_id,
            PersonalizationRequestLog.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_PERSONALIZATIONS_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_PERSONALIZATIONS_PER_HOUR} générations par heure atteinte. Réessaie plus tard."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/rate_limit/test_limiter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/rate_limit/limiter.py backend/tests/rate_limit/test_limiter.py
git commit -m "feat: add dedicated rate limit for CV/lettre personalization"
```

---

### Task 8: Personalization router (generate + download endpoints)

**Files:**
- Create: `backend/app/schemas/personalization.py`
- Create: `backend/app/routers/personalization.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/routers/test_personalization.py`

**Interfaces:**
- Consumes: `Diagnostic` (existing), `PersonalizedDocument`, `PersonalizationRequestLog` (Task 2), `ObjectStorage`/`ObjectStorageError`/`get_object_storage` (Task 3), `CvRewriter`/`CoverLetterGenerator`/`PersonalizationError`/`get_cv_rewriter`/`get_cover_letter_generator` (Task 6), `cv_needs_review` (Task 5), `render_cv_pdf`/`render_cover_letter_pdf` (Task 4), `lock_user_for_rate_limit`/`check_personalization_rate_limit`/`RateLimitExceeded` (Task 7), `get_current_user` (existing)
- Produces: router mounted at `/diagnostics` with `POST /diagnostics/{id}/cv`, `POST /diagnostics/{id}/lettre`, `GET /diagnostics/{id}/cv`, `GET /diagnostics/{id}/lettre`
- Produces: `PersonalizedDocumentOut` response schema — `kind: str`, `needs_review: bool`, `created_at: datetime`, `updated_at: datetime`

- [ ] **Step 1: Write the failing tests**

`backend/tests/routers/test_personalization.py`:
```python
import io

from docx import Document

from app.main import app
from app.personalization.dependencies import get_cover_letter_generator, get_cv_rewriter
from app.personalization.schemas import CoverLetter, CvExperienceEntry, RewrittenCv
from app.rate_limit.limiter import MAX_PERSONALIZATIONS_PER_HOUR
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage


class FakeCvRewriter:
    def rewrite(self, cv_text, offer_text, missing_keywords, recommendations):
        return RewrittenCv(
            summary="Résumé optimisé.",
            experience=[
                CvExperienceEntry(title="Développeuse", company="Acme", dates="2020-2022", bullets=["A conçu des API."])
            ],
            education=["Master Informatique"],
            skills=["Python"],
        )


class FailingCvRewriter:
    def rewrite(self, cv_text, offer_text, missing_keywords, recommendations):
        from app.personalization.analyzer import PersonalizationError

        raise PersonalizationError("boom")


class FakeCoverLetterGenerator:
    def generate(self, cv_text, offer_text, missing_keywords, recommendations):
        return CoverLetter(
            greeting="Madame, Monsieur,",
            body_paragraphs=["Je vous écris pour candidater à ce poste."],
            closing="Cordialement, Jane Doe",
        )


class FakeObjectStorage(ObjectStorage):
    def __init__(self):
        self._objects: dict[str, bytes] = {}

    def upload(self, key: str, content: bytes) -> None:
        self._objects[key] = content

    def download(self, key: str) -> bytes:
        if key not in self._objects:
            raise ObjectStorageError(f"missing key {key}")
        return self._objects[key]

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)


def _clean_cv_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    document.add_paragraph("Développeur")
    document.add_paragraph("Formation")
    document.add_paragraph("Master")
    document.add_paragraph("Compétences")
    document.add_paragraph("Python")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _register_and_login(client) -> str:
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": "jane@example.com", "password": "s3cret!1"})
    return login.json()["access_token"]


def _create_diagnostic(client, headers) -> int:
    from app.llm_analyzer.analyzer import SemanticReport
    from app.llm_analyzer.dependencies import get_semantic_analyzer

    class FakeAnalyzer:
        def analyze(self, cv_text: str, offer_text: str) -> SemanticReport:
            return SemanticReport(score=60, missing_keywords=["Docker"], recommendations=["Add Docker"])

    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    response = client.post(
        "/diagnostics",
        headers=headers,
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer with Docker experience."},
    )
    app.dependency_overrides.pop(get_semantic_analyzer, None)
    return response.json()["id"]


def _override_personalization_deps():
    app.dependency_overrides[get_cv_rewriter] = lambda: FakeCvRewriter()
    app.dependency_overrides[get_cover_letter_generator] = lambda: FakeCoverLetterGenerator()
    app.dependency_overrides[get_object_storage] = lambda: FakeObjectStorage()


def _clear_personalization_overrides():
    app.dependency_overrides.pop(get_cv_rewriter, None)
    app.dependency_overrides.pop(get_cover_letter_generator, None)
    app.dependency_overrides.pop(get_object_storage, None)


def test_generate_cv_returns_metadata_and_download_serves_pdf(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    diagnostic_id = _create_diagnostic(client, headers)
    _override_personalization_deps()

    generate = client.post(f"/diagnostics/{diagnostic_id}/cv", headers=headers)
    assert generate.status_code == 201
    body = generate.json()
    assert body["kind"] == "cv"
    assert body["needs_review"] is False
    assert body["created_at"]

    download = client.get(f"/diagnostics/{diagnostic_id}/cv", headers=headers)
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF")

    _clear_personalization_overrides()


def test_generate_lettre_returns_metadata_and_download_serves_pdf(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    diagnostic_id = _create_diagnostic(client, headers)
    _override_personalization_deps()

    generate = client.post(f"/diagnostics/{diagnostic_id}/lettre", headers=headers)
    assert generate.status_code == 201
    assert generate.json()["kind"] == "lettre"

    download = client.get(f"/diagnostics/{diagnostic_id}/lettre", headers=headers)
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")

    _clear_personalization_overrides()


def test_regenerating_cv_replaces_the_previous_document(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    diagnostic_id = _create_diagnostic(client, headers)
    _override_personalization_deps()

    first = client.post(f"/diagnostics/{diagnostic_id}/cv", headers=headers).json()
    second = client.post(f"/diagnostics/{diagnostic_id}/cv", headers=headers).json()

    assert first["created_at"] == second["created_at"]
    assert second["updated_at"] >= first["updated_at"]

    _clear_personalization_overrides()


def test_generate_cv_for_missing_diagnostic_returns_404(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _override_personalization_deps()

    response = client.post("/diagnostics/999999/cv", headers=headers)
    assert response.status_code == 404

    _clear_personalization_overrides()


def test_download_cv_before_generation_returns_404(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    diagnostic_id = _create_diagnostic(client, headers)
    _override_personalization_deps()

    response = client.get(f"/diagnostics/{diagnostic_id}/cv", headers=headers)
    assert response.status_code == 404

    _clear_personalization_overrides()


def test_generate_cv_returns_503_on_llm_failure(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    diagnostic_id = _create_diagnostic(client, headers)
    _override_personalization_deps()
    app.dependency_overrides[get_cv_rewriter] = lambda: FailingCvRewriter()

    response = client.post(f"/diagnostics/{diagnostic_id}/cv", headers=headers)
    assert response.status_code == 503

    _clear_personalization_overrides()


def test_personalization_rate_limit_returns_429(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    diagnostic_id = _create_diagnostic(client, headers)
    _override_personalization_deps()

    for _ in range(MAX_PERSONALIZATIONS_PER_HOUR):
        response = client.post(f"/diagnostics/{diagnostic_id}/cv", headers=headers)
        assert response.status_code == 201

    blocked = client.post(f"/diagnostics/{diagnostic_id}/cv", headers=headers)
    assert blocked.status_code == 429

    _clear_personalization_overrides()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/routers/test_personalization.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.personalization'`

- [ ] **Step 3: Implement the response schema and router**

`backend/app/schemas/personalization.py`:
```python
from datetime import datetime

from pydantic import BaseModel


class PersonalizedDocumentOut(BaseModel):
    kind: str
    needs_review: bool
    created_at: datetime
    updated_at: datetime
```

`backend/app/routers/personalization.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.diagnostic import Diagnostic
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.personalized_document import PersonalizedDocument
from app.models.user import User
from app.personalization.analyzer import CoverLetterGenerator, CvRewriter, PersonalizationError
from app.personalization.dependencies import get_cover_letter_generator, get_cv_rewriter
from app.personalization.pdf_generator import render_cover_letter_pdf, render_cv_pdf
from app.personalization.verification import cv_needs_review
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_personalization_rate_limit,
    lock_user_for_rate_limit,
)
from app.schemas.personalization import PersonalizedDocumentOut
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage

router = APIRouter(prefix="/diagnostics", tags=["personalization"])


def _get_owned_diagnostic(db: Session, diagnostic_id: int, user_id: int) -> Diagnostic:
    diagnostic = (
        db.query(Diagnostic)
        .filter(Diagnostic.id == diagnostic_id, Diagnostic.user_id == user_id)
        .first()
    )
    if diagnostic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic introuvable.")
    return diagnostic


def _storage_key(user_id: int, diagnostic_id: int, kind: str) -> str:
    return f"users/{user_id}/diagnostics/{diagnostic_id}/{kind}.pdf"


def _get_document(db: Session, diagnostic_id: int, kind: str) -> PersonalizedDocument | None:
    return (
        db.query(PersonalizedDocument)
        .filter(PersonalizedDocument.diagnostic_id == diagnostic_id, PersonalizedDocument.kind == kind)
        .first()
    )


def _upsert_document(
    db: Session, diagnostic_id: int, kind: str, storage_key: str, needs_review: bool
) -> PersonalizedDocument:
    document = _get_document(db, diagnostic_id, kind)
    if document is None:
        document = PersonalizedDocument(
            diagnostic_id=diagnostic_id, kind=kind, storage_key=storage_key, needs_review=needs_review
        )
        db.add(document)
    else:
        document.storage_key = storage_key
        document.needs_review = needs_review
    return document


@router.post("/{diagnostic_id}/cv", response_model=PersonalizedDocumentOut, status_code=status.HTTP_201_CREATED)
def generate_cv(
    diagnostic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rewriter: CvRewriter = Depends(get_cv_rewriter),
    storage: ObjectStorage = Depends(get_object_storage),
) -> PersonalizedDocumentOut:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_personalization_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    diagnostic = _get_owned_diagnostic(db, diagnostic_id, current_user.id)

    try:
        rewritten = rewriter.rewrite(
            diagnostic.cv_text, diagnostic.offer_text, diagnostic.missing_keywords, diagnostic.recommendations
        )
    except PersonalizationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    needs_review = cv_needs_review(diagnostic.cv_text, rewritten)
    pdf_bytes = render_cv_pdf(rewritten)
    key = _storage_key(current_user.id, diagnostic.id, "cv")

    try:
        storage.upload(key, pdf_bytes)
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Le stockage du document a échoué."
        ) from exc

    document = _upsert_document(db, diagnostic.id, "cv", key, needs_review)
    db.add(PersonalizationRequestLog(user_id=current_user.id))
    db.commit()
    db.refresh(document)

    return PersonalizedDocumentOut(
        kind=document.kind, needs_review=document.needs_review, created_at=document.created_at, updated_at=document.updated_at
    )


@router.post("/{diagnostic_id}/lettre", response_model=PersonalizedDocumentOut, status_code=status.HTTP_201_CREATED)
def generate_lettre(
    diagnostic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    generator: CoverLetterGenerator = Depends(get_cover_letter_generator),
    storage: ObjectStorage = Depends(get_object_storage),
) -> PersonalizedDocumentOut:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_personalization_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    diagnostic = _get_owned_diagnostic(db, diagnostic_id, current_user.id)

    try:
        letter = generator.generate(
            diagnostic.cv_text, diagnostic.offer_text, diagnostic.missing_keywords, diagnostic.recommendations
        )
    except PersonalizationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    pdf_bytes = render_cover_letter_pdf(letter)
    key = _storage_key(current_user.id, diagnostic.id, "lettre")

    try:
        storage.upload(key, pdf_bytes)
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Le stockage du document a échoué."
        ) from exc

    document = _upsert_document(db, diagnostic.id, "lettre", key, needs_review=False)
    db.add(PersonalizationRequestLog(user_id=current_user.id))
    db.commit()
    db.refresh(document)

    return PersonalizedDocumentOut(
        kind=document.kind, needs_review=document.needs_review, created_at=document.created_at, updated_at=document.updated_at
    )


def _download(
    diagnostic_id: int, kind: str, filename: str, db: Session, current_user: User, storage: ObjectStorage
) -> Response:
    diagnostic = _get_owned_diagnostic(db, diagnostic_id, current_user.id)
    document = _get_document(db, diagnostic.id, kind)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucun document '{kind}' n'a encore été généré pour ce diagnostic.",
        )
    try:
        pdf_bytes = storage.download(document.storage_key)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{diagnostic_id}/cv")
def download_cv(
    diagnostic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    return _download(diagnostic_id, "cv", "cv_optimise.pdf", db, current_user, storage)


@router.get("/{diagnostic_id}/lettre")
def download_lettre(
    diagnostic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    return _download(diagnostic_id, "lettre", "lettre_motivation.pdf", db, current_user, storage)
```

Modify `backend/app/main.py` to include the new router:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app import database
from app.routers import auth, diagnostics, personalization
import app.models  # noqa: F401 register models on Base

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Deferred to app startup (rather than module import time) so that
    # merely importing app.main - e.g. for linting, OpenAPI generation, or
    # `pytest --collect-only` - does not connect to and issue DDL against
    # whatever DATABASE_URL happens to be configured on the machine.
    # Looked up via the `database` module (not a direct `engine` import) so
    # tests can monkeypatch `app.database.engine` to an isolated in-memory
    # database before the lifespan runs.
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/routers/test_personalization.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/personalization.py backend/app/routers/personalization.py backend/app/main.py backend/tests/routers/test_personalization.py
git commit -m "feat: add CV/lettre generation and download endpoints"
```

---

### Task 9: RGPD purge cascade — delete MinIO objects and PersonalizedDocument rows

**Files:**
- Modify: `backend/app/routers/diagnostics.py`
- Modify: `backend/tests/routers/test_diagnostics.py`

**Interfaces:**
- Consumes: `PersonalizedDocument` (Task 2), `ObjectStorage`/`ObjectStorageError`/`get_object_storage` (Task 3)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/routers/test_diagnostics.py`:
```python
from app.models.personalized_document import PersonalizedDocument
from app.personalization.dependencies import get_cv_rewriter
from app.personalization.schemas import CvExperienceEntry, RewrittenCv
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage


class _FakeCvRewriter:
    def rewrite(self, cv_text, offer_text, missing_keywords, recommendations):
        return RewrittenCv(
            summary="Résumé.",
            experience=[CvExperienceEntry(title="Dev", company="Acme", dates="2020-2022", bullets=["Bullet."])],
            education=["Master"],
            skills=["Python"],
        )


class _FakeObjectStorage(ObjectStorage):
    def __init__(self):
        self._objects: dict[str, bytes] = {}

    def upload(self, key: str, content: bytes) -> None:
        self._objects[key] = content

    def download(self, key: str) -> bytes:
        if key not in self._objects:
            raise ObjectStorageError(f"missing key {key}")
        return self._objects[key]

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)


def test_delete_all_diagnostics_also_purges_personalized_documents(client, db_session):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    fake_storage = _FakeObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: fake_storage
    app.dependency_overrides[get_cv_rewriter] = lambda: _FakeCvRewriter()

    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    diagnostic_id = client.post(
        "/diagnostics",
        headers=headers,
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer."},
    ).json()["id"]

    client.post(f"/diagnostics/{diagnostic_id}/cv", headers=headers)
    assert len(fake_storage._objects) == 1

    deleted = client.delete("/diagnostics", headers=headers)
    assert deleted.status_code == 204

    assert db_session.query(PersonalizedDocument).count() == 0
    assert len(fake_storage._objects) == 0

    app.dependency_overrides.pop(get_semantic_analyzer, None)
    app.dependency_overrides.pop(get_object_storage, None)
    app.dependency_overrides.pop(get_cv_rewriter, None)
```

Note: this test needs `db_session` as a fixture argument alongside `client` — both come from `conftest.py` and share the same underlying SQLite connection (see `conftest.py`'s `client` fixture, which overrides `get_db` with `db_session`), so it's safe to query `db_session` directly to verify DB state after HTTP calls made through `client`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/routers/test_diagnostics.py::test_delete_all_diagnostics_also_purges_personalized_documents -v`
Expected: FAIL — `PersonalizedDocument` rows and MinIO objects are not purged yet (the count assertions fail).

- [ ] **Step 3: Implement the purge cascade**

Modify `backend/app/routers/diagnostics.py` — add the new imports and replace `delete_all_diagnostics`:
```python
import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
from app.cv_parser.parser import parse_cv, CVParsingError, MAX_CV_SIZE_BYTES
from app.offer_ingestion.ingestion import get_offer_text, OfferIngestionError
from app.rules_engine.rules import evaluate_structure
from app.llm_analyzer.analyzer import SemanticAnalyzer, LLMAnalysisError
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.aggregator.aggregator import build_diagnostic_report
from app.schemas.diagnostic import DiagnosticReport
from app.rate_limit.limiter import check_rate_limit, lock_user_for_rate_limit, RateLimitExceeded
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

# ... create_diagnostic and list_diagnostics unchanged ...


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> None:
    diagnostic_ids = [
        row[0] for row in db.query(Diagnostic.id).filter(Diagnostic.user_id == current_user.id).all()
    ]

    # Collected before deletion, and PersonalizedDocument rows are deleted
    # explicitly below rather than relying on the FK's ondelete="CASCADE":
    # this is a bulk `.delete()` query (not per-instance `db.delete(...)`),
    # which bypasses SQLAlchemy ORM-level relationship cascades, and SQLite
    # (used in the test suite) doesn't enforce FK-level cascade unless
    # `PRAGMA foreign_keys=ON` is explicitly set. Explicit deletion works
    # correctly on both SQLite and production PostgreSQL.
    documents = (
        db.query(PersonalizedDocument)
        .filter(PersonalizedDocument.diagnostic_id.in_(diagnostic_ids))
        .all()
    )
    storage_keys = [document.storage_key for document in documents]

    db.query(PersonalizedDocument).filter(PersonalizedDocument.diagnostic_id.in_(diagnostic_ids)).delete(
        synchronize_session=False
    )
    db.query(Diagnostic).filter(Diagnostic.user_id == current_user.id).delete()
    db.commit()

    for key in storage_keys:
        try:
            storage.delete(key)
        except ObjectStorageError:
            # The DB rows (source of truth for the RGPD purge) are already
            # gone at this point; a MinIO object left behind by a transient
            # storage failure is logged for manual follow-up rather than
            # failing the whole purge request.
            logger.warning("Failed to delete MinIO object %s during RGPD purge", key)
```

`list_diagnostics` and `create_diagnostic` are unchanged from their current implementation — only the imports at the top of the file and the `delete_all_diagnostics` function body change.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/routers/test_diagnostics.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: PASS (all tests, including the diagnostic sub-project's existing suite)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/diagnostics.py backend/tests/routers/test_diagnostics.py
git commit -m "feat: purge MinIO objects and PersonalizedDocument rows on RGPD delete"
```

---
