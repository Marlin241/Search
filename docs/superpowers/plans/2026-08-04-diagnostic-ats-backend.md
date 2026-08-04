# Diagnostic ATS — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend for the ATS diagnostic tool: users register/login, upload a CV (PDF/DOCX) plus a job offer (text or URL), and get back a diagnostic combining a rule-based structural/parsability score with an LLM-based semantic match score.

**Architecture:** FastAPI API (no server-rendered UI — a separate Next.js frontend will consume this API in a later plan). SQLAlchemy 2.0 ORM against PostgreSQL in production, SQLite in-memory for tests. CV parsing and structural rules are pure deterministic Python; semantic matching calls the Claude API with forced tool-use for structured output.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, pydantic-settings, PyJWT, bcrypt, pdfplumber, python-docx, httpx, BeautifulSoup4, anthropic SDK, pytest, respx, fpdf2, Pillow.

## Global Constraints

- Max CV upload size: 5 MB (5 * 1024 * 1024 bytes).
- Supported CV formats: PDF and DOCX only. No OCR/scanned-CV support in this version.
- Supported languages: French and English (CV and offer text).
- LLM model: `claude-haiku-4-5-20251001`, called via forced tool use for structured output, with exactly 1 retry on failure before raising an error.
- Never store the raw CV file — only extracted text and structural metadata are persisted.
- Users must be able to delete their diagnostic history (RGPD) via `DELETE /diagnostics`.
- Rate limit: 10 diagnostics per user per hour — anti-abuse safeguard, not a product quota (accounts are free and unlimited in this version).
- No payment/billing in this version.
- Auth: JWT bearer tokens (PyJWT), bcrypt password hashing.

---

### Task 1: Project scaffolding & health check

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/__init__.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.get_settings() -> Settings` (fields: `database_url: str`, `jwt_secret: str`, `jwt_algorithm: str`, `jwt_expire_minutes: int`, `anthropic_api_key: str`, `cors_origins: list[str]`)
- Produces: `app.main.app` (FastAPI instance)

- [ ] **Step 1: Create requirements files**

`backend/requirements.txt`:
```
fastapi
uvicorn[standard]
sqlalchemy>=2.0
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
```

`backend/requirements-dev.txt`:
```
-r requirements.txt
pytest
respx
fpdf2
pillow
```

`backend/.env.example`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/ats_diagnostic
JWT_SECRET=change-me
ANTHROPIC_API_KEY=sk-ant-...
CORS_ORIGINS=["http://localhost:3000"]
```

- [ ] **Step 2: Create config module**

`backend/app/config.py`:
```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    anthropic_api_key: str
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Write the failing test**

`backend/tests/test_health.py`:
```python
import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from fastapi.testclient import TestClient
from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && pip install -r requirements-dev.txt && pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 5: Create minimal FastAPI app**

`backend/app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="ATS Diagnostic API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd backend && git add requirements.txt requirements-dev.txt .env.example app/__init__.py app/config.py app/main.py tests/__init__.py tests/test_health.py
git commit -m "feat: project scaffolding with health check endpoint"
```

---

### Task 2: Database setup

**Files:**
- Create: `backend/app/database.py`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_database.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Task 1)
- Produces: `app.database.Base` (declarative base), `app.database.engine`, `app.database.SessionLocal`, `app.database.get_db()` (FastAPI dependency, yields `Session`)
- Produces test fixture: `db_session` (in `conftest.py`) — an in-memory SQLite `Session` with tables created

- [ ] **Step 1: Write the failing test**

`backend/tests/conftest.py`:
```python
import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401 register all models on Base

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
```

`backend/tests/test_database.py`:
```python
from sqlalchemy import text


def test_db_session_executes_query(db_session):
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_database.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.database'`

- [ ] **Step 3: Implement database module**

`backend/app/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Also create the (still-empty) models package so `import app.models` in `conftest.py` succeeds:

`backend/app/models/__init__.py`:
```python
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/database.py app/models/__init__.py tests/conftest.py tests/test_database.py
git commit -m "feat: database engine/session setup"
```

---

### Task 3: User model

**Files:**
- Create: `backend/app/models/user.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/test_user.py`

**Interfaces:**
- Consumes: `app.database.Base` (Task 2)
- Produces: `app.models.user.User` (fields: `id: int`, `email: str`, `hashed_password: str`, `created_at: datetime`)

- [ ] **Step 1: Write the failing test**

`backend/tests/models/__init__.py`:
```python
```

`backend/tests/models/test_user.py`:
```python
from app.models.user import User


def test_create_and_query_user(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    fetched = db_session.query(User).filter(User.email == "jane@example.com").first()
    assert fetched is not None
    assert fetched.hashed_password == "hashed"
    assert fetched.created_at is not None


def test_email_must_be_unique(db_session):
    db_session.add(User(email="dup@example.com", hashed_password="a"))
    db_session.commit()
    db_session.add(User(email="dup@example.com", hashed_password="b"))

    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/models/test_user.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.user'`

- [ ] **Step 3: Implement User model**

`backend/app/models/user.py`:
```python
from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

`backend/app/models/__init__.py`:
```python
from app.models.user import User

__all__ = ["User"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/models/test_user.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/models/user.py app/models/__init__.py tests/models/__init__.py tests/models/test_user.py
git commit -m "feat: add User model"
```

---

### Task 4: Password hashing & JWT utilities

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/security.py`
- Test: `backend/tests/auth/test_security.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Task 1)
- Produces: `hash_password(password: str) -> str`, `verify_password(password: str, hashed_password: str) -> bool`, `create_access_token(subject: str) -> str`, `decode_access_token(token: str) -> str` (all in `app.auth.security`)

- [ ] **Step 1: Write the failing test**

`backend/tests/auth/__init__.py`:
```python
```

`backend/tests/auth/test_security.py`:
```python
import time

import jwt
import pytest

from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("s3cret!")
    assert hashed != "s3cret!"
    assert verify_password("s3cret!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token(subject="jane@example.com")
    assert decode_access_token(token) == "jane@example.com"


def test_decode_invalid_token_raises():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-real-token")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/auth/test_security.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth'`

- [ ] **Step 3: Implement security module**

`backend/app/auth/security.py`:
```python
from datetime import datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return payload["sub"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/auth/test_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/auth/__init__.py app/auth/security.py tests/auth/__init__.py tests/auth/test_security.py
git commit -m "feat: password hashing and JWT utilities"
```

---

### Task 5: Auth endpoints (register, login, me)

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/routers/test_auth.py`

**Interfaces:**
- Consumes: `app.database.get_db`, `app.models.user.User`, `app.auth.security.*` (Tasks 2-4)
- Produces: `app.auth.dependencies.get_current_user` (FastAPI dependency, returns `User`)
- Produces: router mounted at `/auth` with `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- Produces test fixture: `client` (in `conftest.py`) — `TestClient` with `get_db` overridden to use `db_session`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/conftest.py`:
```python
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

`backend/tests/routers/__init__.py`:
```python
```

`backend/tests/routers/test_auth.py`:
```python
def test_register_creates_user(client):
    response = client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert "id" in body


def test_register_duplicate_email_returns_409(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "s3cret!"})
    response = client.post("/auth/register", json={"email": "dup@example.com", "password": "other"})
    assert response.status_code == 409


def test_login_returns_token(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!"})
    response = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "s3cret!"}
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_wrong_password_returns_401(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!"})
    response = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "wrong"}
    )
    assert response.status_code == 401


def test_me_requires_valid_token(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!"})
    login = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "s3cret!"}
    )
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "jane@example.com"

    unauthorized = client.get("/auth/me")
    assert unauthorized.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/routers/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas'`

- [ ] **Step 3: Implement schemas, dependency, router, and wire main.py**

`backend/app/schemas/__init__.py`:
```python
```

`backend/app/schemas/auth.py`:
```python
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

`backend/app/auth/dependencies.py`:
```python
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Impossible de valider les identifiants.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        email = decode_access_token(token)
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user
```

`backend/app/routers/__init__.py`:
```python
```

`backend/app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserCreate, UserOut, Token
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet email est déjà utilisé.")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )
    token = create_access_token(subject=user.email)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
```

`backend/app/main.py`:
```python
from fastapi import FastAPI

from app.database import Base, engine
from app.routers import auth
import app.models  # noqa: F401 register models on Base

app = FastAPI(title="ATS Diagnostic API")

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/routers/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/schemas app/auth/dependencies.py app/routers app/main.py tests/conftest.py tests/routers
git commit -m "feat: auth register/login/me endpoints"
```

---

### Task 6: CV section detection (shared)

**Files:**
- Create: `backend/app/cv_parser/__init__.py`
- Create: `backend/app/cv_parser/sections.py`
- Test: `backend/tests/cv_parser/test_sections.py`

**Interfaces:**
- Produces: `detect_sections(text: str) -> set[str]` in `app.cv_parser.sections` — returns subset of `{"experience", "education", "skills"}`

- [ ] **Step 1: Write the failing test**

`backend/tests/cv_parser/__init__.py`:
```python
```

`backend/tests/cv_parser/test_sections.py`:
```python
from app.cv_parser.sections import detect_sections


def test_detects_french_sections():
    text = "Expérience professionnelle\n...\nFormation\n...\nCompétences\n..."
    assert detect_sections(text) == {"experience", "education", "skills"}


def test_detects_english_sections():
    text = "Work History\n...\nEducation\n...\nSkills\n..."
    assert detect_sections(text) == {"experience", "education", "skills"}


def test_missing_sections_not_detected():
    text = "Just a paragraph with no headers at all."
    assert detect_sections(text) == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/cv_parser/test_sections.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.cv_parser'`

- [ ] **Step 3: Implement section detection**

`backend/app/cv_parser/__init__.py`:
```python
```

`backend/app/cv_parser/sections.py`:
```python
SECTION_KEYWORDS: dict[str, list[str]] = {
    "experience": ["expérience", "experience", "parcours professionnel", "work history"],
    "education": ["formation", "education", "études", "academic background"],
    "skills": ["compétences", "skills", "competencies"],
}


def detect_sections(text: str) -> set[str]:
    lowered = text.lower()
    detected = set()
    for section, keywords in SECTION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            detected.add(section)
    return detected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/cv_parser/test_sections.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/cv_parser/__init__.py app/cv_parser/sections.py tests/cv_parser
git commit -m "feat: shared CV section detection"
```

---

### Task 7: CV structural data model + DOCX parser

**Files:**
- Create: `backend/app/cv_parser/models.py`
- Create: `backend/app/cv_parser/docx_parser.py`
- Test: `backend/tests/cv_parser/test_docx_parser.py`

**Interfaces:**
- Consumes: `detect_sections` (Task 6)
- Produces: `app.cv_parser.models.CVParseResult` (fields: `text: str`, `has_tables: bool`, `has_multi_column: bool`, `has_images: bool`, `detected_sections: set[str]`)
- Produces: `parse_docx(file_bytes: bytes) -> CVParseResult` in `app.cv_parser.docx_parser`

- [ ] **Step 1: Write the failing test**

`backend/tests/cv_parser/test_docx_parser.py`:
```python
import io

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image

from app.cv_parser.docx_parser import parse_docx


def _save(document: Document) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_parses_simple_docx_and_detects_sections():
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    document.add_paragraph("Développeur chez Acme, 2020-2024")
    document.add_paragraph("Formation")
    document.add_paragraph("Master informatique")
    document.add_paragraph("Compétences")
    document.add_paragraph("Python, FastAPI")

    result = parse_docx(_save(document))

    assert "Développeur chez Acme" in result.text
    assert result.detected_sections == {"experience", "education", "skills"}
    assert result.has_tables is False
    assert result.has_images is False
    assert result.has_multi_column is False


def test_detects_table():
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    document.add_table(rows=2, cols=2)

    result = parse_docx(_save(document))
    assert result.has_tables is True


def test_detects_image():
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    img_buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="black").save(img_buffer, format="PNG")
    img_buffer.seek(0)
    document.add_picture(img_buffer)

    result = parse_docx(_save(document))
    assert result.has_images is True


def test_detects_multi_column_section():
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    section = document.sections[0]
    cols = OxmlElement("w:cols")
    cols.set(qn("w:num"), "2")
    section._sectPr.append(cols)

    result = parse_docx(_save(document))
    assert result.has_multi_column is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/cv_parser/test_docx_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.cv_parser.docx_parser'`

- [ ] **Step 3: Implement CVParseResult and DOCX parser**

`backend/app/cv_parser/models.py`:
```python
from pydantic import BaseModel


class CVParseResult(BaseModel):
    text: str
    has_tables: bool
    has_multi_column: bool
    has_images: bool
    detected_sections: set[str]
```

`backend/app/cv_parser/docx_parser.py`:
```python
import io

from docx import Document
from docx.oxml.ns import qn

from app.cv_parser.models import CVParseResult
from app.cv_parser.sections import detect_sections


def _has_multi_column(document: Document) -> bool:
    for section in document.sections:
        cols = section._sectPr.find(qn("w:cols"))
        if cols is not None:
            num = cols.get(qn("w:num"))
            if num is not None and int(num) > 1:
                return True
    return False


def parse_docx(file_bytes: bytes) -> CVParseResult:
    document = Document(io.BytesIO(file_bytes))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    return CVParseResult(
        text=text,
        has_tables=len(document.tables) > 0,
        has_multi_column=_has_multi_column(document),
        has_images=len(document.inline_shapes) > 0,
        detected_sections=detect_sections(text),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/cv_parser/test_docx_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/cv_parser/models.py app/cv_parser/docx_parser.py tests/cv_parser/test_docx_parser.py
git commit -m "feat: DOCX CV parsing with structural detection"
```

---

### Task 8: PDF parser

**Files:**
- Create: `backend/app/cv_parser/pdf_parser.py`
- Test: `backend/tests/cv_parser/test_pdf_parser.py`

**Interfaces:**
- Consumes: `CVParseResult`, `detect_sections` (Tasks 6-7)
- Produces: `parse_pdf(file_bytes: bytes) -> CVParseResult` in `app.cv_parser.pdf_parser`

- [ ] **Step 1: Write the failing test**

`backend/tests/cv_parser/test_pdf_parser.py`:
```python
from fpdf import FPDF
from PIL import Image

from app.cv_parser.pdf_parser import parse_pdf


def _output(pdf: FPDF) -> bytes:
    return bytes(pdf.output())


def test_extracts_text_and_sections():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Expérience professionnelle\nDéveloppeur chez Acme\nFormation\nMaster\nCompétences\nPython")

    result = parse_pdf(_output(pdf))
    assert "Développeur chez Acme" in result.text
    assert result.detected_sections == {"experience", "education", "skills"}
    assert result.has_multi_column is False


def test_detects_table():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    x0, y0, col_w, row_h = 10, 10, 40, 10
    for row in range(3):
        for col in range(2):
            pdf.rect(x0 + col * col_w, y0 + row * row_h, col_w, row_h)

    result = parse_pdf(_output(pdf))
    assert result.has_tables is True


def test_detects_image():
    pdf = FPDF()
    pdf.add_page()
    img = Image.new("RGB", (10, 10), color="black")
    pdf.image(img, x=10, y=10, w=10, h=10)

    result = parse_pdf(_output(pdf))
    assert result.has_images is True


def test_detects_two_column_layout():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    pdf.set_xy(10, 10)
    pdf.multi_cell(90, 6, "Colonne gauche avec du texte. " * 40)
    pdf.set_xy(110, 10)
    pdf.multi_cell(90, 6, "Colonne droite avec du texte. " * 40)

    result = parse_pdf(_output(pdf))
    assert result.has_multi_column is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/cv_parser/test_pdf_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.cv_parser.pdf_parser'`

- [ ] **Step 3: Implement PDF parser**

`backend/app/cv_parser/pdf_parser.py`:
```python
import io

import pdfplumber

from app.cv_parser.models import CVParseResult
from app.cv_parser.sections import detect_sections

_TABLE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}


def _detect_multi_column(page: "pdfplumber.page.Page") -> bool:
    words = page.extract_words()
    if len(words) < 20:
        return False
    band_start = page.width * 0.45
    band_end = page.width * 0.55
    words_in_band = [w for w in words if band_start <= w["x0"] <= band_end]
    words_left = [w for w in words if w["x0"] < band_start]
    words_right = [w for w in words if w["x0"] > band_end]
    if not words_left or not words_right:
        return False
    return (len(words_in_band) / len(words)) < 0.02


def parse_pdf(file_bytes: bytes) -> CVParseResult:
    text_parts: list[str] = []
    has_tables = False
    has_images = False
    has_multi_column = False

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
            if page.find_tables(table_settings=_TABLE_SETTINGS):
                has_tables = True
            if page.images:
                has_images = True
            if _detect_multi_column(page):
                has_multi_column = True

    text = "\n".join(text_parts)
    return CVParseResult(
        text=text,
        has_tables=has_tables,
        has_multi_column=has_multi_column,
        has_images=has_images,
        detected_sections=detect_sections(text),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/cv_parser/test_pdf_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/cv_parser/pdf_parser.py tests/cv_parser/test_pdf_parser.py
git commit -m "feat: PDF CV parsing with structural detection"
```

---

### Task 9: Unified CV parser entrypoint + validation

**Files:**
- Create: `backend/app/cv_parser/parser.py`
- Test: `backend/tests/cv_parser/test_parser.py`

**Interfaces:**
- Consumes: `parse_docx`, `parse_pdf`, `CVParseResult` (Tasks 7-8)
- Produces: `parse_cv(file_bytes: bytes, filename: str) -> CVParseResult`, `CVParsingError` (both in `app.cv_parser.parser`)

- [ ] **Step 1: Write the failing test**

`backend/tests/cv_parser/test_parser.py`:
```python
import pytest
from docx import Document
import io
from fpdf import FPDF

from app.cv_parser.parser import parse_cv, CVParsingError, MAX_CV_SIZE_BYTES


def _docx_bytes(paragraph_text: str) -> bytes:
    document = Document()
    document.add_paragraph(paragraph_text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_parses_valid_docx_by_extension():
    result = parse_cv(_docx_bytes("Expérience professionnelle chez Acme"), "cv.docx")
    assert "Acme" in result.text


def test_parses_valid_pdf_by_extension():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Expérience professionnelle chez Acme " * 5)
    result = parse_cv(bytes(pdf.output()), "cv.pdf")
    assert "Acme" in result.text


def test_rejects_unsupported_extension():
    with pytest.raises(CVParsingError):
        parse_cv(b"whatever", "cv.txt")


def test_rejects_file_too_large():
    oversized = b"0" * (MAX_CV_SIZE_BYTES + 1)
    with pytest.raises(CVParsingError):
        parse_cv(oversized, "cv.pdf")


def test_rejects_corrupt_pdf():
    with pytest.raises(CVParsingError):
        parse_cv(b"not a real pdf", "cv.pdf")


def test_rejects_scanned_cv_with_no_text():
    pdf = FPDF()
    pdf.add_page()
    with pytest.raises(CVParsingError):
        parse_cv(bytes(pdf.output()), "cv.pdf")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/cv_parser/test_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.cv_parser.parser'`

- [ ] **Step 3: Implement unified parser**

`backend/app/cv_parser/parser.py`:
```python
from app.cv_parser.models import CVParseResult
from app.cv_parser.docx_parser import parse_docx
from app.cv_parser.pdf_parser import parse_pdf

MAX_CV_SIZE_BYTES = 5 * 1024 * 1024


class CVParsingError(Exception):
    pass


def parse_cv(file_bytes: bytes, filename: str) -> CVParseResult:
    if len(file_bytes) > MAX_CV_SIZE_BYTES:
        raise CVParsingError("Le fichier dépasse la taille maximale autorisée (5 Mo).")

    lowered_name = filename.lower()
    try:
        if lowered_name.endswith(".pdf"):
            result = parse_pdf(file_bytes)
        elif lowered_name.endswith(".docx"):
            result = parse_docx(file_bytes)
        else:
            raise CVParsingError("Format de fichier non supporté. Utilisez un PDF ou un DOCX.")
    except CVParsingError:
        raise
    except Exception as exc:
        raise CVParsingError(f"Impossible de lire ce fichier : {exc}") from exc

    if len(result.text.strip()) < 50:
        raise CVParsingError(
            "Ce CV semble être une image scannée ou ne contient pas de texte extractible. "
            "L'analyse automatique n'est pas encore possible sur ce format."
        )
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/cv_parser/test_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/cv_parser/parser.py tests/cv_parser/test_parser.py
git commit -m "feat: unified CV parser entrypoint with validation"
```

---

### Task 10: Structural Rules Engine

**Files:**
- Create: `backend/app/rules_engine/__init__.py`
- Create: `backend/app/rules_engine/rules.py`
- Test: `backend/tests/rules_engine/test_rules.py`

**Interfaces:**
- Consumes: `CVParseResult` (Task 7)
- Produces: `app.rules_engine.rules.StructuralReport` (fields: `score: int`, `issues: list[str]`), `evaluate_structure(parse_result: CVParseResult) -> StructuralReport`

- [ ] **Step 1: Write the failing test**

`backend/tests/rules_engine/__init__.py`:
```python
```

`backend/tests/rules_engine/test_rules.py`:
```python
from app.cv_parser.models import CVParseResult
from app.rules_engine.rules import evaluate_structure


def _clean_cv() -> CVParseResult:
    return CVParseResult(
        text="...",
        has_tables=False,
        has_multi_column=False,
        has_images=False,
        detected_sections={"experience", "education", "skills"},
    )


def test_clean_cv_scores_100_with_no_issues():
    report = evaluate_structure(_clean_cv())
    assert report.score == 100
    assert report.issues == []


def test_multi_column_lowers_score_and_adds_issue():
    cv = _clean_cv().model_copy(update={"has_multi_column": True})
    report = evaluate_structure(cv)
    assert report.score == 75
    assert any("colonnes" in issue for issue in report.issues)


def test_missing_sections_lower_score_and_add_issues():
    cv = _clean_cv().model_copy(update={"detected_sections": set()})
    report = evaluate_structure(cv)
    assert report.score == 70
    assert len(report.issues) == 3


def test_score_never_goes_below_zero():
    cv = CVParseResult(
        text="...",
        has_tables=True,
        has_multi_column=True,
        has_images=True,
        detected_sections=set(),
    )
    report = evaluate_structure(cv)
    assert report.score == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/rules_engine/test_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.rules_engine'`

- [ ] **Step 3: Implement rules engine**

`backend/app/rules_engine/__init__.py`:
```python
```

`backend/app/rules_engine/rules.py`:
```python
from pydantic import BaseModel

from app.cv_parser.models import CVParseResult


class StructuralReport(BaseModel):
    score: int
    issues: list[str]


_REQUIRED_SECTIONS = {
    "experience": "Aucune section 'Expérience' standard détectée.",
    "education": "Aucune section 'Formation' standard détectée.",
    "skills": "Aucune section 'Compétences' standard détectée.",
}


def evaluate_structure(parse_result: CVParseResult) -> StructuralReport:
    issues: list[str] = []
    penalty = 0

    if parse_result.has_multi_column:
        issues.append("Ce CV utilise une mise en page en colonnes, souvent mal lue par les ATS.")
        penalty += 25
    if parse_result.has_tables:
        issues.append("Ce CV contient des tableaux, qui peuvent être mal interprétés par les ATS.")
        penalty += 20
    if parse_result.has_images:
        issues.append(
            "Ce CV contient des images ; tout texte qu'elles contiennent ne sera pas lu par l'ATS."
        )
        penalty += 15

    for section, message in _REQUIRED_SECTIONS.items():
        if section not in parse_result.detected_sections:
            issues.append(message)
            penalty += 10

    return StructuralReport(score=max(0, 100 - penalty), issues=issues)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/rules_engine/test_rules.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/rules_engine tests/rules_engine
git commit -m "feat: structural rules engine for CV parsability score"
```

---

### Task 11: Offer ingestion (scraping + unified entrypoint)

**Files:**
- Create: `backend/app/offer_ingestion/__init__.py`
- Create: `backend/app/offer_ingestion/scraper.py`
- Create: `backend/app/offer_ingestion/ingestion.py`
- Test: `backend/tests/offer_ingestion/test_scraper.py`
- Test: `backend/tests/offer_ingestion/test_ingestion.py`

**Interfaces:**
- Produces: `scrape_offer(url: str) -> str`, `ScrapingError` (in `app.offer_ingestion.scraper`)
- Produces: `get_offer_text(text: str | None, url: str | None) -> str`, `OfferIngestionError` (in `app.offer_ingestion.ingestion`)

- [ ] **Step 1: Write the failing tests**

`backend/tests/offer_ingestion/__init__.py`:
```python
```

`backend/tests/offer_ingestion/test_scraper.py`:
```python
import httpx
import pytest
import respx

from app.offer_ingestion.scraper import scrape_offer, ScrapingError


@respx.mock
def test_scrape_offer_success():
    respx.get("https://example.com/job").mock(
        return_value=httpx.Response(200, html="<html><body>" + ("Description du poste. " * 50) + "</body></html>")
    )
    text = scrape_offer("https://example.com/job")
    assert "Description du poste" in text


@respx.mock
def test_scrape_offer_blocked_raises():
    respx.get("https://example.com/blocked").mock(return_value=httpx.Response(403))
    with pytest.raises(ScrapingError):
        scrape_offer("https://example.com/blocked")


@respx.mock
def test_scrape_offer_empty_content_raises():
    respx.get("https://example.com/empty").mock(
        return_value=httpx.Response(200, html="<html><body></body></html>")
    )
    with pytest.raises(ScrapingError):
        scrape_offer("https://example.com/empty")
```

`backend/tests/offer_ingestion/test_ingestion.py`:
```python
from unittest.mock import patch

import pytest

from app.offer_ingestion.ingestion import get_offer_text, OfferIngestionError
from app.offer_ingestion.scraper import ScrapingError


def test_returns_pasted_text_when_provided():
    assert get_offer_text("Some offer text", None) == "Some offer text"


def test_scrapes_url_when_no_text_provided():
    with patch("app.offer_ingestion.ingestion.scrape_offer", return_value="Scraped offer text") as mocked:
        result = get_offer_text(None, "https://example.com/job")
    mocked.assert_called_once_with("https://example.com/job")
    assert result == "Scraped offer text"


def test_scraping_failure_raises_ingestion_error():
    with patch("app.offer_ingestion.ingestion.scrape_offer", side_effect=ScrapingError("blocked")):
        with pytest.raises(OfferIngestionError):
            get_offer_text(None, "https://example.com/job")


def test_no_text_or_url_raises():
    with pytest.raises(OfferIngestionError):
        get_offer_text(None, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/offer_ingestion -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.offer_ingestion'`

- [ ] **Step 3: Implement scraper and ingestion entrypoint**

`backend/app/offer_ingestion/__init__.py`:
```python
```

`backend/app/offer_ingestion/scraper.py`:
```python
import httpx
from bs4 import BeautifulSoup


class ScrapingError(Exception):
    pass


def scrape_offer(url: str) -> str:
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(
                url, headers={"User-Agent": "Mozilla/5.0 (compatible; ATSDiagnosticBot/1.0)"}
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ScrapingError(f"Failed to fetch offer URL: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)

    if len(text) < 200:
        raise ScrapingError("Scraped content too short, likely blocked or JS-rendered page")
    return text
```

`backend/app/offer_ingestion/ingestion.py`:
```python
from app.offer_ingestion.scraper import scrape_offer, ScrapingError


class OfferIngestionError(Exception):
    pass


def get_offer_text(text: str | None, url: str | None) -> str:
    if text and text.strip():
        return text.strip()
    if url:
        try:
            return scrape_offer(url)
        except ScrapingError as exc:
            raise OfferIngestionError(
                "Impossible de récupérer le contenu de cette offre automatiquement. "
                "Merci de coller le texte de l'offre manuellement."
            ) from exc
    raise OfferIngestionError("Merci de fournir le texte de l'offre ou son URL.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/offer_ingestion -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/offer_ingestion tests/offer_ingestion
git commit -m "feat: offer ingestion via pasted text or URL scraping"
```

---

### Task 12: Diagnostic ORM model

**Files:**
- Create: `backend/app/models/diagnostic.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/test_diagnostic.py`

**Interfaces:**
- Consumes: `app.database.Base`, `app.models.user.User` (Tasks 2-3)
- Produces: `app.models.diagnostic.Diagnostic` (fields: `id: int`, `user_id: int`, `cv_text: str`, `offer_text: str`, `overall_score: int`, `structural_score: int`, `structural_issues: list[str]`, `semantic_score: int`, `missing_keywords: list[str]`, `recommendations: list[str]`, `created_at: datetime`)
- Adds: `User.diagnostics` relationship (list of `Diagnostic`)

- [ ] **Step 1: Write the failing test**

`backend/tests/models/test_diagnostic.py`:
```python
from app.models.user import User
from app.models.diagnostic import Diagnostic


def test_create_diagnostic_linked_to_user(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    diagnostic = Diagnostic(
        user_id=user.id,
        cv_text="cv text",
        offer_text="offer text",
        overall_score=80,
        structural_score=90,
        structural_issues=["issue 1"],
        semantic_score=70,
        missing_keywords=["Python"],
        recommendations=["Add Python to your skills section"],
    )
    db_session.add(diagnostic)
    db_session.commit()

    fetched = db_session.query(Diagnostic).filter(Diagnostic.user_id == user.id).first()
    assert fetched.overall_score == 80
    assert fetched.structural_issues == ["issue 1"]
    assert fetched.missing_keywords == ["Python"]

    refreshed_user = db_session.query(User).filter(User.id == user.id).first()
    assert len(refreshed_user.diagnostics) == 1


def test_deleting_user_cascades_diagnostics(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    db_session.add(
        Diagnostic(
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
    )
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(Diagnostic).count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/models/test_diagnostic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.diagnostic'`

- [ ] **Step 3: Implement Diagnostic model and wire the relationship**

`backend/app/models/diagnostic.py`:
```python
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    cv_text: Mapped[str] = mapped_column(Text, nullable=False)
    offer_text: Mapped[str] = mapped_column(Text, nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    structural_score: Mapped[int] = mapped_column(Integer, nullable=False)
    structural_issues: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    semantic_score: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    recommendations: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="diagnostics")
```

Modify `backend/app/models/user.py` — add the relationship (import `relationship` and add the field):
```python
from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    diagnostics: Mapped[list["Diagnostic"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
```

`backend/app/models/__init__.py`:
```python
from app.models.user import User
from app.models.diagnostic import Diagnostic

__all__ = ["User", "Diagnostic"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/models/test_diagnostic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/models
git commit -m "feat: add Diagnostic model linked to User"
```

---

### Task 13: Diagnostic schema + aggregator

**Files:**
- Create: `backend/app/schemas/diagnostic.py`
- Create: `backend/app/aggregator/__init__.py`
- Create: `backend/app/aggregator/aggregator.py`
- Test: `backend/tests/aggregator/test_aggregator.py`

**Interfaces:**
- Consumes: `StructuralReport` (Task 10)
- Consumes: `SemanticReport` (Task 14 — defined next, but this task only needs its shape: `score: int`, `missing_keywords: list[str]`, `recommendations: list[str]`, so it's safe to build now against that shape)
- Produces: `app.schemas.diagnostic.DiagnosticReport` (fields: `overall_score: int`, `structural_score: int`, `structural_issues: list[str]`, `semantic_score: int`, `missing_keywords: list[str]`, `recommendations: list[str]`)
- Produces: `build_diagnostic_report(structural: StructuralReport, semantic: SemanticReport) -> DiagnosticReport` in `app.aggregator.aggregator`

- [ ] **Step 1: Write the failing test**

`backend/tests/aggregator/__init__.py`:
```python
```

`backend/tests/aggregator/test_aggregator.py`:
```python
from pydantic import BaseModel

from app.rules_engine.rules import StructuralReport
from app.aggregator.aggregator import build_diagnostic_report


class FakeSemanticReport(BaseModel):
    score: int
    missing_keywords: list[str]
    recommendations: list[str]


def test_aggregates_scores_and_details():
    structural = StructuralReport(score=80, issues=["Missing skills section"])
    semantic = FakeSemanticReport(score=60, missing_keywords=["Docker"], recommendations=["Add Docker"])

    report = build_diagnostic_report(structural, semantic)

    assert report.overall_score == 70
    assert report.structural_score == 80
    assert report.structural_issues == ["Missing skills section"]
    assert report.semantic_score == 60
    assert report.missing_keywords == ["Docker"]
    assert report.recommendations == ["Add Docker"]


def test_overall_score_rounds_to_nearest_int():
    structural = StructuralReport(score=100, issues=[])
    semantic = FakeSemanticReport(score=83, missing_keywords=[], recommendations=[])

    report = build_diagnostic_report(structural, semantic)
    # Python's round() uses round-half-to-even: (100 + 83) / 2 == 91.5 -> 92
    assert report.overall_score == 92
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/aggregator/test_aggregator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.aggregator'`

- [ ] **Step 3: Implement schema and aggregator**

`backend/app/schemas/diagnostic.py`:
```python
from pydantic import BaseModel


class DiagnosticReport(BaseModel):
    overall_score: int
    structural_score: int
    structural_issues: list[str]
    semantic_score: int
    missing_keywords: list[str]
    recommendations: list[str]
```

`backend/app/aggregator/__init__.py`:
```python
```

`backend/app/aggregator/aggregator.py`:
```python
from typing import Protocol

from app.rules_engine.rules import StructuralReport
from app.schemas.diagnostic import DiagnosticReport


class SemanticReportLike(Protocol):
    score: int
    missing_keywords: list[str]
    recommendations: list[str]


def build_diagnostic_report(
    structural: StructuralReport, semantic: SemanticReportLike
) -> DiagnosticReport:
    overall_score = round((structural.score + semantic.score) / 2)
    return DiagnosticReport(
        overall_score=overall_score,
        structural_score=structural.score,
        structural_issues=structural.issues,
        semantic_score=semantic.score,
        missing_keywords=semantic.missing_keywords,
        recommendations=semantic.recommendations,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/aggregator/test_aggregator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/schemas/diagnostic.py app/aggregator tests/aggregator
git commit -m "feat: diagnostic report schema and score aggregator"
```

---

### Task 14: LLM Semantic Analyzer

**Files:**
- Create: `backend/app/llm_analyzer/__init__.py`
- Create: `backend/app/llm_analyzer/analyzer.py`
- Create: `backend/app/llm_analyzer/dependencies.py`
- Test: `backend/tests/llm_analyzer/test_analyzer.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Task 1)
- Produces: `app.llm_analyzer.analyzer.SemanticReport` (fields: `score: int`, `missing_keywords: list[str]`, `recommendations: list[str]`) — matches the `SemanticReportLike` shape consumed by the aggregator (Task 13)
- Produces: `app.llm_analyzer.analyzer.SemanticAnalyzer` (constructor: `(client, model: str = "claude-haiku-4-5-20251001")`, method: `analyze(cv_text: str, offer_text: str) -> SemanticReport`), `LLMAnalysisError`
- Produces: `app.llm_analyzer.dependencies.get_semantic_analyzer() -> SemanticAnalyzer` (FastAPI dependency)

- [ ] **Step 1: Write the failing test**

`backend/tests/llm_analyzer/__init__.py`:
```python
```

`backend/tests/llm_analyzer/test_analyzer.py`:
```python
from types import SimpleNamespace

import anthropic
import pytest

from app.llm_analyzer.analyzer import SemanticAnalyzer, LLMAnalysisError


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


def test_analyze_returns_parsed_report_on_valid_response():
    client = FakeClient(
        [_fake_tool_use_response({"score": 72, "missing_keywords": ["Docker"], "recommendations": ["Add Docker"]})]
    )
    analyzer = SemanticAnalyzer(client)

    report = analyzer.analyze("cv text", "offer text")

    assert report.score == 72
    assert report.missing_keywords == ["Docker"]
    assert report.recommendations == ["Add Docker"]
    assert client.messages.calls[0]["tool_choice"] == {"type": "tool", "name": "submit_diagnostic"}


def test_analyze_retries_once_on_invalid_payload_then_succeeds():
    client = FakeClient(
        [
            _fake_tool_use_response({"score": "not-a-number"}),
            _fake_tool_use_response({"score": 50, "missing_keywords": [], "recommendations": []}),
        ]
    )
    analyzer = SemanticAnalyzer(client)

    report = analyzer.analyze("cv text", "offer text")

    assert report.score == 50
    assert len(client.messages.calls) == 2


def test_analyze_raises_after_two_failures():
    client = FakeClient(
        [
            _fake_tool_use_response({"score": "not-a-number"}),
            _fake_tool_use_response({"score": "still-not-a-number"}),
        ]
    )
    analyzer = SemanticAnalyzer(client)

    with pytest.raises(LLMAnalysisError):
        analyzer.analyze("cv text", "offer text")


def test_analyze_retries_on_api_error():
    client = FakeClient(
        [
            anthropic.APIConnectionError(request=SimpleNamespace()),
            _fake_tool_use_response({"score": 40, "missing_keywords": [], "recommendations": []}),
        ]
    )
    analyzer = SemanticAnalyzer(client)

    report = analyzer.analyze("cv text", "offer text")
    assert report.score == 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/llm_analyzer/test_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.llm_analyzer'`

- [ ] **Step 3: Implement the semantic analyzer**

`backend/app/llm_analyzer/__init__.py`:
```python
```

`backend/app/llm_analyzer/analyzer.py`:
```python
import anthropic
from pydantic import BaseModel, ValidationError


class SemanticReport(BaseModel):
    score: int
    missing_keywords: list[str]
    recommendations: list[str]


class LLMAnalysisError(Exception):
    pass


_DIAGNOSTIC_TOOL = {
    "name": "submit_diagnostic",
    "description": "Submit the semantic match diagnostic between a CV and a job offer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "description": "Compatibility score from 0 to 100 between the CV and the job offer.",
            },
            "missing_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skills or keywords present in the offer but missing from the CV.",
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete, actionable recommendations to improve the match.",
            },
        },
        "required": ["score", "missing_keywords", "recommendations"],
    },
}

_MAX_ATTEMPTS = 2


class SemanticAnalyzer:
    def __init__(self, client, model: str = "claude-haiku-4-5-20251001"):
        self._client = client
        self._model = model

    def analyze(self, cv_text: str, offer_text: str) -> SemanticReport:
        last_error: Exception | None = None
        for _ in range(_MAX_ATTEMPTS):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    tools=[_DIAGNOSTIC_TOOL],
                    tool_choice={"type": "tool", "name": "submit_diagnostic"},
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                "Compare this CV and this job offer. Identify the compatibility "
                                "score, missing keywords/skills, and concrete recommendations. "
                                "The CV and offer may be in French or English; respond in the "
                                "same language as the CV.\n\n"
                                f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}"
                            ),
                        }
                    ],
                )
                tool_use = next(
                    (block for block in response.content if block.type == "tool_use"), None
                )
                if tool_use is None:
                    raise LLMAnalysisError("No tool_use block in Claude response")
                return SemanticReport.model_validate(tool_use.input)
            except (ValidationError, LLMAnalysisError, anthropic.APIError) as exc:
                last_error = exc
                continue
        raise LLMAnalysisError(f"Semantic analysis failed after retries: {last_error}")
```

`backend/app/llm_analyzer/dependencies.py`:
```python
from functools import lru_cache

import anthropic

from app.config import get_settings
from app.llm_analyzer.analyzer import SemanticAnalyzer


@lru_cache
def get_semantic_analyzer() -> SemanticAnalyzer:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return SemanticAnalyzer(client)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/llm_analyzer/test_analyzer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/llm_analyzer tests/llm_analyzer
git commit -m "feat: LLM semantic analyzer with structured output and retry"
```

---

### Task 15: Diagnostics router (create/list/delete) with rate limiting

**Files:**
- Create: `backend/app/rate_limit/__init__.py`
- Create: `backend/app/rate_limit/limiter.py`
- Create: `backend/app/routers/diagnostics.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/rate_limit/test_limiter.py`
- Test: `backend/tests/routers/test_diagnostics.py`

**Interfaces:**
- Consumes: `Diagnostic` model (Task 12), `parse_cv`/`CVParsingError` (Task 9), `get_offer_text`/`OfferIngestionError` (Task 11), `evaluate_structure` (Task 10), `SemanticAnalyzer`/`get_semantic_analyzer`/`LLMAnalysisError` (Task 14), `build_diagnostic_report`/`DiagnosticReport` (Task 13), `get_current_user` (Task 5)
- Produces: `check_rate_limit(db: Session, user_id: int) -> None`, `RateLimitExceeded` (in `app.rate_limit.limiter`)
- Produces: router mounted at `/diagnostics` with `POST /diagnostics`, `GET /diagnostics`, `DELETE /diagnostics`

- [ ] **Step 1: Write the failing tests**

`backend/tests/rate_limit/__init__.py`:
```python
```

`backend/tests/rate_limit/test_limiter.py`:
```python
from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.rate_limit.limiter import check_rate_limit, RateLimitExceeded, MAX_DIAGNOSTICS_PER_HOUR


def _make_user(db_session) -> User:
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    return user


def _add_diagnostics(db_session, user_id: int, count: int) -> None:
    for _ in range(count):
        db_session.add(
            Diagnostic(
                user_id=user_id,
                cv_text="cv",
                offer_text="offer",
                overall_score=1,
                structural_score=1,
                structural_issues=[],
                semantic_score=1,
                missing_keywords=[],
                recommendations=[],
            )
        )
    db_session.commit()


def test_allows_under_limit(db_session):
    user = _make_user(db_session)
    _add_diagnostics(db_session, user.id, MAX_DIAGNOSTICS_PER_HOUR - 1)
    check_rate_limit(db_session, user.id)  # should not raise


def test_blocks_at_limit(db_session):
    user = _make_user(db_session)
    _add_diagnostics(db_session, user.id, MAX_DIAGNOSTICS_PER_HOUR)
    import pytest

    with pytest.raises(RateLimitExceeded):
        check_rate_limit(db_session, user.id)
```

`backend/tests/routers/test_diagnostics.py`:
```python
import io

from docx import Document

from app.llm_analyzer.analyzer import SemanticReport
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.main import app
from app.rate_limit.limiter import MAX_DIAGNOSTICS_PER_HOUR


class FakeAnalyzer:
    def analyze(self, cv_text: str, offer_text: str) -> SemanticReport:
        return SemanticReport(score=60, missing_keywords=["Docker"], recommendations=["Add Docker"])


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
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!"})
    login = client.post("/auth/login", data={"username": "jane@example.com", "password": "s3cret!"})
    return login.json()["access_token"]


def test_create_diagnostic_returns_combined_report(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)

    response = client.post(
        "/diagnostics",
        headers={"Authorization": f"Bearer {token}"},
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer with Docker experience."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["structural_score"] == 100
    assert body["semantic_score"] == 60
    assert body["overall_score"] == 80
    assert body["missing_keywords"] == ["Docker"]

    app.dependency_overrides.pop(get_semantic_analyzer, None)


def test_create_diagnostic_without_offer_returns_422(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)

    response = client.post(
        "/diagnostics",
        headers={"Authorization": f"Bearer {token}"},
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 422
    app.dependency_overrides.pop(get_semantic_analyzer, None)


def test_list_and_delete_diagnostics(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/diagnostics",
        headers=headers,
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer."},
    )

    listed = client.get("/diagnostics", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = client.delete("/diagnostics", headers=headers)
    assert deleted.status_code == 204

    listed_after = client.get("/diagnostics", headers=headers)
    assert listed_after.json() == []

    app.dependency_overrides.pop(get_semantic_analyzer, None)


def test_rate_limit_returns_429(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(MAX_DIAGNOSTICS_PER_HOUR):
        response = client.post(
            "/diagnostics",
            headers=headers,
            files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"offer_text": "We need a Python developer."},
        )
        assert response.status_code == 201

    blocked = client.post(
        "/diagnostics",
        headers=headers,
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer."},
    )
    assert blocked.status_code == 429

    app.dependency_overrides.pop(get_semantic_analyzer, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/rate_limit tests/routers/test_diagnostics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.rate_limit'`

- [ ] **Step 3: Implement rate limiter, router, and wire main.py**

`backend/app/rate_limit/__init__.py`:
```python
```

`backend/app/rate_limit/limiter.py`:
```python
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.diagnostic import Diagnostic

MAX_DIAGNOSTICS_PER_HOUR = 10


class RateLimitExceeded(Exception):
    pass


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
```

`backend/app/routers/diagnostics.py`:
```python
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.cv_parser.parser import parse_cv, CVParsingError
from app.offer_ingestion.ingestion import get_offer_text, OfferIngestionError
from app.rules_engine.rules import evaluate_structure
from app.llm_analyzer.analyzer import SemanticAnalyzer, LLMAnalysisError
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.aggregator.aggregator import build_diagnostic_report
from app.schemas.diagnostic import DiagnosticReport
from app.rate_limit.limiter import check_rate_limit, RateLimitExceeded

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.post("", response_model=DiagnosticReport, status_code=status.HTTP_201_CREATED)
def create_diagnostic(
    cv_file: UploadFile = File(...),
    offer_text: str | None = Form(None),
    offer_url: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analyzer: SemanticAnalyzer = Depends(get_semantic_analyzer),
) -> DiagnosticReport:
    try:
        check_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    try:
        cv_bytes = cv_file.file.read()
        parsed_cv = parse_cv(cv_bytes, cv_file.filename or "")
    except CVParsingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        offer = get_offer_text(offer_text, offer_url)
    except OfferIngestionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    structural = evaluate_structure(parsed_cv)

    try:
        semantic = analyzer.analyze(parsed_cv.text, offer)
    except LLMAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    report = build_diagnostic_report(structural, semantic)

    db.add(
        Diagnostic(
            user_id=current_user.id,
            cv_text=parsed_cv.text,
            offer_text=offer,
            overall_score=report.overall_score,
            structural_score=report.structural_score,
            structural_issues=report.structural_issues,
            semantic_score=report.semantic_score,
            missing_keywords=report.missing_keywords,
            recommendations=report.recommendations,
        )
    )
    db.commit()

    return report


@router.get("", response_model=list[DiagnosticReport])
def list_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DiagnosticReport]:
    diagnostics = (
        db.query(Diagnostic)
        .filter(Diagnostic.user_id == current_user.id)
        .order_by(Diagnostic.created_at.desc())
        .all()
    )
    return [
        DiagnosticReport(
            overall_score=d.overall_score,
            structural_score=d.structural_score,
            structural_issues=d.structural_issues,
            semantic_score=d.semantic_score,
            missing_keywords=d.missing_keywords,
            recommendations=d.recommendations,
        )
        for d in diagnostics
    ]


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    db.query(Diagnostic).filter(Diagnostic.user_id == current_user.id).delete()
    db.commit()
```

Modify `backend/app/main.py` to include the new router:
```python
from fastapi import FastAPI

from app.database import Base, engine
from app.routers import auth, diagnostics
import app.models  # noqa: F401 register models on Base

app = FastAPI(title="ATS Diagnostic API")

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(diagnostics.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/rate_limit tests/routers/test_diagnostics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/rate_limit app/routers/diagnostics.py app/main.py tests/rate_limit tests/routers/test_diagnostics.py
git commit -m "feat: diagnostics endpoints with rate limiting"
```

---

### Task 16: CORS, full end-to-end test, and setup docs

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_end_to_end.py`
- Create: `backend/README.md`

**Interfaces:**
- Consumes: everything from Tasks 1-15
- No new interfaces — this task wires CORS and validates the full flow works together end-to-end

- [ ] **Step 1: Write the failing test**

`backend/tests/test_end_to_end.py`:
```python
import io

from docx import Document

from app.llm_analyzer.analyzer import SemanticReport
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.main import app


class FakeAnalyzer:
    def analyze(self, cv_text: str, offer_text: str) -> SemanticReport:
        return SemanticReport(score=50, missing_keywords=["Kubernetes"], recommendations=["Learn Kubernetes"])


def _cv_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    document.add_paragraph("Formation")
    document.add_paragraph("Compétences")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_cors_allows_configured_origin(client):
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_full_flow_register_login_diagnose_list_delete(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()

    register = client.post("/auth/register", json={"email": "flow@example.com", "password": "s3cret!"})
    assert register.status_code == 201

    login = client.post("/auth/login", data={"username": "flow@example.com", "password": "s3cret!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    diagnose = client.post(
        "/diagnostics",
        headers=headers,
        files={"cv_file": ("cv.docx", _cv_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "Looking for a Kubernetes engineer."},
    )
    assert diagnose.status_code == 201
    assert diagnose.json()["overall_score"] == 75

    listed = client.get("/diagnostics", headers=headers)
    assert len(listed.json()) == 1

    deleted = client.delete("/diagnostics", headers=headers)
    assert deleted.status_code == 204

    assert client.get("/diagnostics", headers=headers).json() == []

    app.dependency_overrides.pop(get_semantic_analyzer, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_end_to_end.py -v`
Expected: `test_cors_allows_configured_origin` FAILS (no `access-control-allow-origin` header yet, since `CORSMiddleware` isn't registered). `test_full_flow_register_login_diagnose_list_delete` already PASSES — it doesn't depend on CORS and exists as a regression-guard covering the whole stack, not as the change driver for this task.

- [ ] **Step 3: Add CORS configuration**

Modify `backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, diagnostics
import app.models  # noqa: F401 register models on Base

settings = get_settings()

app = FastAPI(title="ATS Diagnostic API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(diagnostics.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

`backend/README.md`:
```markdown
# ATS Diagnostic — Backend

## Setup

1. `python -m venv venv && source venv/bin/activate`
2. `pip install -r requirements-dev.txt`
3. Copy `.env.example` to `.env` and fill in `JWT_SECRET`, `ANTHROPIC_API_KEY`, and `DATABASE_URL` (PostgreSQL in production; a local SQLite file works for manual testing).
4. `uvicorn app.main:app --reload`
5. Open `http://localhost:8000/docs` for the interactive API documentation.

## Tests

`pytest`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_end_to_end.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `cd backend && pytest -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/main.py tests/test_end_to_end.py README.md
git commit -m "feat: CORS configuration, end-to-end test, and setup docs"
```
