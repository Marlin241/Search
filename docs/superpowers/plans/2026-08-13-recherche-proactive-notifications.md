# Recherche proactive et notifications par email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre à un utilisateur de sauvegarder une recherche d'offres et de recevoir un email quotidien listant les nouvelles offres correspondantes, sans avoir à relancer une recherche manuelle.

**Architecture:** Un scheduler APScheduler in-process (démarré dans le `lifespan` FastAPI) tourne toutes les heures ; à chaque passage il traite les `SavedSearch` activées dont l'heure locale (fuseau propre à l'utilisateur) vient d'atteindre 8h. Pour chacune, il réutilise la logique de recherche existante (`search_jobs`, cache Greenhouse/Lever), déduplique via `NotifiedListing`, et envoie un email via l'API Resend (appel `httpx` direct, pas de SDK) contenant un lien de désabonnement.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, APScheduler 3.x (`BackgroundScheduler`), `zoneinfo`/`tzdata` (stdlib + fallback PyPI), `httpx` (déjà présent), Resend REST API, Next.js/TypeScript (frontend).

**Spec:** `docs/superpowers/specs/2026-08-13-recherche-proactive-notifications-design.md`

## Global Constraints

- Une seule `SavedSearch` par utilisateur (relation un-à-un, `user_id` unique).
- Notification par email uniquement — pas de notification in-app cette itération.
- Le job planifié n'est jamais soumis aux rate-limits de `app/rate_limit/limiter.py` (il n'est pas déclenché par l'utilisateur).
- Un échec pour un utilisateur (recherche ou envoi d'email) ne doit jamais interrompre le traitement des autres utilisateurs du même passage.
- Une offre n'est marquée « notifiée » (`NotifiedListing`) qu'après un envoi d'email réussi — un échec d'envoi laisse les offres non marquées, elles réapparaîtront donc naturellement le lendemain (pas de mécanisme de retry dédié).
- Pas de header `List-Unsubscribe` (RFC 8058) cette itération — un simple lien cliquable dans le corps de l'email suffit.
- Toute nouvelle valeur `DateTime` par défaut sur un modèle utilise le helper `app.utils.time.utcnow` (introduit lors du chantier CI/fiabilité), jamais `datetime.utcnow` directement.

---

## Task 1: Dépendances backend et configuration

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`

**Interfaces:**
- Produces: `Settings.resend_api_key: str`, `Settings.resend_from_email: str`, `Settings.backend_base_url: str` — utilisés par les tâches 4 et 6.

- [ ] **Step 1: Ajouter les nouvelles dépendances**

Dans `backend/requirements.txt`, ajouter (ordre alphabétique parmi les
dépendances existantes, pas de section séparée) :
```
apscheduler
tzdata
```
`tzdata` est nécessaire car l'image Docker du backend (`python:3.13-slim`)
n'embarque pas forcément la base de données de fuseaux horaires du système
— le module stdlib `zoneinfo` se rabat automatiquement sur le paquet PyPI
`tzdata` quand elle est absente de l'OS.

- [ ] **Step 2: Installer et vérifier**

Run: `cd backend && source venv/bin/activate && pip install -r requirements.txt`

Run: `python -c "from zoneinfo import ZoneInfo, available_timezones; print(ZoneInfo('Europe/Paris')); print('Europe/Paris' in available_timezones())"`
Expected: affiche `Europe/Paris` (l'objet `ZoneInfo`) puis `True`, sans
erreur `ZoneInfoNotFoundError`.

- [ ] **Step 3: Ajouter les nouveaux settings**

Dans `backend/app/config.py`, ajouter à la classe `Settings` (après
`la_bonne_alternance_api_key`) :
```python
    resend_api_key: str = ""
    resend_from_email: str = ""
    backend_base_url: str = "http://localhost:8000"
```

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt backend/app/config.py
git commit -m "chore(backend): add apscheduler/tzdata deps and Resend/base-url settings"
```

---

## Task 2: Modèles `SavedSearch` et `NotifiedListing`

**Files:**
- Create: `backend/app/models/saved_search.py`
- Create: `backend/app/models/notified_listing.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/test_saved_search.py`
- Test: `backend/tests/models/test_notified_listing.py`

**Interfaces:**
- Consumes: `app.utils.time.utcnow` (existant, chantier CI/fiabilité).
- Produces: `SavedSearch` (`id, user_id, keywords, location, contract_type, remote, exclude_keywords, timezone, enabled, created_at, updated_at`), `NotifiedListing` (`id, user_id, offer_url, notified_at`) — consommés par les tâches 5, 6, 7.

- [ ] **Step 1: Écrire les tests (qui échouent, les modèles n'existent pas encore)**

Créer `backend/tests/models/test_saved_search.py` :
```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.saved_search import SavedSearch
from app.models.user import User


def test_create_saved_search_with_defaults(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(SavedSearch(user_id=user.id, keywords="python backend"))
    db_session.commit()

    fetched = (
        db_session.query(SavedSearch).filter(SavedSearch.user_id == user.id).first()
    )
    assert fetched.keywords == "python backend"
    assert fetched.location is None
    assert fetched.exclude_keywords == []
    assert fetched.timezone == "Europe/Paris"
    assert fetched.enabled is True
    assert fetched.created_at is not None


def test_saved_search_user_id_is_unique(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(SavedSearch(user_id=user.id, keywords="a"))
    db_session.commit()

    db_session.add(SavedSearch(user_id=user.id, keywords="b"))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

Créer `backend/tests/models/test_notified_listing.py` :
```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.notified_listing import NotifiedListing
from app.models.user import User


def test_create_notified_listing(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(
        NotifiedListing(user_id=user.id, offer_url="https://example.com/job/1")
    )
    db_session.commit()

    fetched = (
        db_session.query(NotifiedListing)
        .filter(NotifiedListing.user_id == user.id)
        .first()
    )
    assert fetched.offer_url == "https://example.com/job/1"
    assert fetched.notified_at is not None


def test_notified_listing_unique_per_user_and_url(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(NotifiedListing(user_id=user.id, offer_url="https://example.com/job/1"))
    db_session.commit()

    db_session.add(NotifiedListing(user_id=user.id, offer_url="https://example.com/job/1"))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/models/test_saved_search.py tests/models/test_notified_listing.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.models.saved_search'` (et pareil pour `notified_listing`).

- [ ] **Step 3: Créer `SavedSearch`**

Créer `backend/app/models/saved_search.py` :
```python
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utcnow


class SavedSearch(Base):
    """Une recherche sauvegardée par utilisateur (relation un-à-un), traitée
    quotidiennement par app.job_search.daily_search.run_daily_search."""

    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    keywords: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remote: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    exclude_keywords: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Europe/Paris"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
```

- [ ] **Step 4: Créer `NotifiedListing`**

Créer `backend/app/models/notified_listing.py` :
```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utcnow


class NotifiedListing(Base):
    """Trace qu'une offre (offer_url) a déjà été envoyée à un utilisateur
    par email — empêche de renvoyer deux fois la même offre. Volontairement
    jamais purgée (voir spec, section "Hors scope")."""

    __tablename__ = "notified_listings"
    __table_args__ = (
        UniqueConstraint("user_id", "offer_url", name="uq_notified_listing_user_offer_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    offer_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    notified_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
```

- [ ] **Step 5: Enregistrer les deux modèles**

Dans `backend/app/models/__init__.py`, ajouter les imports et les entrées
`__all__` (ordre alphabétique, cohérent avec l'existant) :
```python
from app.models.application import Application
from app.models.candidate_profile import CandidateProfile
from app.models.company_ats_mapping import CompanyAtsMapping
from app.models.diagnostic import Diagnostic
from app.models.job_search_request_log import JobSearchRequestLog
from app.models.notified_listing import NotifiedListing
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.personalized_document import PersonalizedDocument
from app.models.prefilled_form_request_log import PrefilledFormRequestLog
from app.models.saved_search import SavedSearch
from app.models.user import User

__all__ = [
    "Application",
    "CandidateProfile",
    "CompanyAtsMapping",
    "Diagnostic",
    "JobSearchRequestLog",
    "NotifiedListing",
    "PersonalizationRequestLog",
    "PersonalizedDocument",
    "PrefilledFormRequestLog",
    "SavedSearch",
    "User",
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/models/test_saved_search.py tests/models/test_notified_listing.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/saved_search.py backend/app/models/notified_listing.py backend/app/models/__init__.py backend/tests/models/test_saved_search.py backend/tests/models/test_notified_listing.py
git commit -m "feat(backend): add SavedSearch and NotifiedListing models"
```

---

## Task 3: Token de désabonnement

**Files:**
- Create: `backend/app/job_search/unsubscribe.py`
- Test: `backend/tests/job_search/test_unsubscribe.py`

**Interfaces:**
- Produces: `create_unsubscribe_token(user_id: int) -> str`, `verify_unsubscribe_token(token: str) -> int`, `InvalidUnsubscribeTokenError` (exception) — consommés par les tâches 6 et 7.

- [ ] **Step 1: Write the failing tests**

Créer `backend/tests/job_search/test_unsubscribe.py` :
```python
import pytest

from app.job_search.unsubscribe import (
    InvalidUnsubscribeTokenError,
    create_unsubscribe_token,
    verify_unsubscribe_token,
)


def test_create_then_verify_round_trip():
    token = create_unsubscribe_token(user_id=42)
    assert verify_unsubscribe_token(token) == 42


def test_verify_rejects_a_normal_login_token():
    import jwt

    from app.config import get_settings

    settings = get_settings()
    login_token = jwt.encode(
        {"sub": "42"}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(InvalidUnsubscribeTokenError):
        verify_unsubscribe_token(login_token)


def test_verify_rejects_garbage_token():
    with pytest.raises(InvalidUnsubscribeTokenError):
        verify_unsubscribe_token("not-a-real-token")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/job_search/test_unsubscribe.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.job_search.unsubscribe'`.

- [ ] **Step 3: Write the implementation**

Créer `backend/app/job_search/unsubscribe.py` :
```python
from datetime import timedelta

import jwt

from app.config import get_settings
from app.utils.time import utcnow

_UNSUBSCRIBE_TOKEN_PURPOSE = "unsubscribe"
_UNSUBSCRIBE_TOKEN_EXPIRE_DAYS = 365


class InvalidUnsubscribeTokenError(Exception):
    pass


def create_unsubscribe_token(user_id: int) -> str:
    """Signé avec le même secret que les tokens de connexion, mais avec une
    claim `purpose` distincte et une expiration longue (365 jours plutôt que
    les quelques heures d'un token de connexion) - un email peut être lu des
    semaines après réception. Un token frais est généré à chaque envoi
    d'email, jamais réutilisé/stocké."""
    settings = get_settings()
    expire = utcnow() + timedelta(days=_UNSUBSCRIBE_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "purpose": _UNSUBSCRIBE_TOKEN_PURPOSE,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_unsubscribe_token(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidUnsubscribeTokenError("Token invalide ou expiré.") from exc
    if payload.get("purpose") != _UNSUBSCRIBE_TOKEN_PURPOSE:
        raise InvalidUnsubscribeTokenError("Token invalide pour cet usage.")
    return int(payload["sub"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/job_search/test_unsubscribe.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/unsubscribe.py backend/tests/job_search/test_unsubscribe.py
git commit -m "feat(backend): add unsubscribe token creation/verification"
```

---

## Task 4: Client email Resend

**Files:**
- Create: `backend/app/notifications/__init__.py`
- Create: `backend/app/notifications/resend_client.py`
- Test: `backend/tests/notifications/__init__.py`
- Test: `backend/tests/notifications/test_resend_client.py`

**Interfaces:**
- Consumes: `Settings.resend_api_key`, `Settings.resend_from_email`, `Settings.backend_base_url` (Task 1) ; `app.job_search.schemas.JobListing` (existant).
- Produces: `send_daily_digest_email(to_email: str, listings: list[JobListing], unsubscribe_token: str) -> None`, `EmailSendError` (exception) — consommés par la tâche 7.

- [ ] **Step 1: Write the failing test**

Créer `backend/app/notifications/__init__.py` (fichier vide) et
`backend/tests/notifications/__init__.py` (fichier vide).

Créer `backend/tests/notifications/test_resend_client.py` :
```python
import json

import httpx
import pytest
import respx

from app.job_search.schemas import JobListing
from app.notifications.resend_client import EmailSendError, send_daily_digest_email


def _listing(url: str = "https://example.com/job/1") -> JobListing:
    return JobListing(
        title="Développeur Python",
        company="Acme",
        location="Paris",
        snippet="...",
        url=url,
        source="france_travail",
        ats_type=None,
    )


@respx.mock
def test_send_daily_digest_email_posts_to_resend():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    send_daily_digest_email("jane@example.com", [_listing()], "tok-123")

    assert route.called
    request = route.calls[0].request
    assert request.headers["authorization"].startswith("Bearer ")
    payload = json.loads(request.content)
    assert payload["to"] == ["jane@example.com"]
    assert "1 nouvelle offre" in payload["subject"]
    assert "https://example.com/job/1" in payload["html"]
    assert "tok-123" in payload["html"]


@respx.mock
def test_send_daily_digest_email_raises_on_http_error():
    respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(422, json={"message": "invalid from address"})
    )

    with pytest.raises(EmailSendError):
        send_daily_digest_email("jane@example.com", [_listing()], "tok-123")


@respx.mock
def test_send_daily_digest_email_pluralizes_subject_for_multiple_listings():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    send_daily_digest_email(
        "jane@example.com",
        [_listing("https://example.com/job/1"), _listing("https://example.com/job/2")],
        "tok-123",
    )

    payload = json.loads(route.calls[0].request.content)
    assert "2 nouvelles offres" in payload["subject"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/notifications/test_resend_client.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.notifications.resend_client'`.

- [ ] **Step 3: Write the implementation**

Créer `backend/app/notifications/resend_client.py` :
```python
import httpx

from app.config import get_settings
from app.job_search.schemas import JobListing

_RESEND_API_URL = "https://api.resend.com/emails"


class EmailSendError(Exception):
    pass


def _render_html(listings: list[JobListing], unsubscribe_url: str) -> str:
    items = "".join(
        f"<li><a href=\"{listing.url}\">{listing.title}</a> — {listing.company}"
        f"{f' ({listing.location})' if listing.location else ''}</li>"
        for listing in listings
    )
    return (
        "<p>Nouvelles offres correspondant à votre recherche :</p>"
        f"<ul>{items}</ul>"
        f"<p><a href=\"{unsubscribe_url}\">Se désabonner de ces alertes</a></p>"
    )


def send_daily_digest_email(
    to_email: str, listings: list[JobListing], unsubscribe_token: str
) -> None:
    settings = get_settings()
    count = len(listings)
    subject = (
        f"{count} nouvelle{'s' if count > 1 else ''} offre{'s' if count > 1 else ''} "
        "correspondant à votre recherche"
    )
    unsubscribe_url = (
        f"{settings.backend_base_url}/job-search/saved-search/unsubscribe"
        f"?token={unsubscribe_token}"
    )
    response = httpx.post(
        _RESEND_API_URL,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": subject,
            "html": _render_html(listings, unsubscribe_url),
        },
        timeout=10.0,
    )
    if response.status_code >= 400:
        raise EmailSendError(
            f"Échec de l'envoi de l'email via Resend ({response.status_code}): {response.text}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/notifications/test_resend_client.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/notifications backend/tests/notifications
git commit -m "feat(backend): add Resend email client for the daily digest"
```

---

## Task 5: Endpoints `GET`/`PUT /job-search/saved-search`

**Files:**
- Modify: `backend/app/schemas/job_search.py`
- Modify: `backend/app/routers/job_search.py`
- Test: `backend/tests/routers/test_saved_search.py`

**Interfaces:**
- Consumes: `SavedSearch` (Task 2).
- Produces: `SavedSearchIn`, `SavedSearchOut` (pydantic) — `SavedSearchOut` est aussi utilisé par la tâche 6 (page de désabonnement n'en a pas besoin, mais le modèle `SavedSearch` qu'elle modifie est le même).

- [ ] **Step 1: Write the failing tests**

Créer `backend/tests/routers/test_saved_search.py` :
```python
def _register_and_login(client, email: str = "jane@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": email, "password": "s3cret!1"})
    return login.json()["access_token"]


def test_get_saved_search_returns_404_when_none_exists(client):
    token = _register_and_login(client)
    response = client.get(
        "/job-search/saved-search", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


def test_put_saved_search_creates_it(client):
    token = _register_and_login(client)
    response = client.put(
        "/job-search/saved-search",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "keywords": "python backend",
            "location": "Paris",
            "contract_type": "CDI",
            "remote": True,
            "exclude_keywords": ["stage"],
            "timezone": "Europe/Paris",
            "enabled": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["keywords"] == "python backend"
    assert body["timezone"] == "Europe/Paris"
    assert body["enabled"] is True

    get_response = client.get(
        "/job-search/saved-search", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 200
    assert get_response.json()["keywords"] == "python backend"


def test_put_saved_search_updates_existing(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/job-search/saved-search",
        headers=headers,
        json={
            "keywords": "python",
            "exclude_keywords": [],
            "timezone": "Europe/Paris",
            "enabled": True,
        },
    )

    response = client.put(
        "/job-search/saved-search",
        headers=headers,
        json={
            "keywords": "python senior",
            "exclude_keywords": [],
            "timezone": "Europe/Paris",
            "enabled": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["keywords"] == "python senior"
    assert body["enabled"] is False


def test_put_saved_search_rejects_invalid_timezone(client):
    token = _register_and_login(client)
    response = client.put(
        "/job-search/saved-search",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "keywords": "python",
            "exclude_keywords": [],
            "timezone": "Not/A_Real_Zone",
            "enabled": True,
        },
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/routers/test_saved_search.py -v`
Expected: FAIL — `404` attendu vs `404` (route inexistante donne aussi 404,
mais pour la mauvaise raison) ; les tests `PUT` échouent clairement (route
absente → FastAPI renvoie `405`/`404` selon le cas, en tout cas pas les
codes/corps attendus).

- [ ] **Step 3: Ajouter les schémas**

Dans `backend/app/schemas/job_search.py`, ajouter après
`JobSearchDiscoveryResponse` :
```python
class SavedSearchIn(BaseModel):
    keywords: str
    location: str | None = None
    contract_type: str | None = None
    remote: bool | None = None
    exclude_keywords: list[str] = []
    timezone: str = "Europe/Paris"
    enabled: bool = True


class SavedSearchOut(BaseModel):
    keywords: str
    location: str | None
    contract_type: str | None
    remote: bool | None
    exclude_keywords: list[str]
    timezone: str
    enabled: bool
```

- [ ] **Step 4: Ajouter les endpoints**

Dans `backend/app/routers/job_search.py`, ajouter à l'import
`app.schemas.job_search` (`SavedSearchIn`, `SavedSearchOut`), ajouter :
```python
from zoneinfo import available_timezones
```
et un import `from app.models.saved_search import SavedSearch`.

Puis, à la fin du fichier (après `get_discovery`) :
```python
def _to_saved_search_out(saved_search: SavedSearch) -> SavedSearchOut:
    return SavedSearchOut(
        keywords=saved_search.keywords,
        location=saved_search.location,
        contract_type=saved_search.contract_type,
        remote=saved_search.remote,
        exclude_keywords=saved_search.exclude_keywords,
        timezone=saved_search.timezone,
        enabled=saved_search.enabled,
    )


@router.get("/saved-search", response_model=SavedSearchOut)
def get_saved_search(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchOut:
    saved_search = (
        db.query(SavedSearch).filter(SavedSearch.user_id == current_user.id).first()
    )
    if saved_search is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune recherche sauvegardée.",
        )
    return _to_saved_search_out(saved_search)


@router.put("/saved-search", response_model=SavedSearchOut)
def put_saved_search(
    payload: SavedSearchIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchOut:
    if payload.timezone not in available_timezones():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fuseau horaire invalide.",
        )

    saved_search = (
        db.query(SavedSearch).filter(SavedSearch.user_id == current_user.id).first()
    )
    if saved_search is None:
        saved_search = SavedSearch(user_id=current_user.id)
        db.add(saved_search)

    saved_search.keywords = payload.keywords
    saved_search.location = payload.location
    saved_search.contract_type = payload.contract_type
    saved_search.remote = payload.remote
    saved_search.exclude_keywords = payload.exclude_keywords
    saved_search.timezone = payload.timezone
    saved_search.enabled = payload.enabled
    db.commit()
    db.refresh(saved_search)
    return _to_saved_search_out(saved_search)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/routers/test_saved_search.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Run the full backend suite (non-regression)**

Run: `pytest -q`
Expected: tous les tests passent (les 314 précédents + les nouveaux).

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/job_search.py backend/app/routers/job_search.py backend/tests/routers/test_saved_search.py
git commit -m "feat(backend): add GET/PUT /job-search/saved-search endpoints"
```

---

## Task 6: Endpoint de désabonnement

**Files:**
- Modify: `backend/app/routers/job_search.py`
- Test: `backend/tests/routers/test_saved_search_unsubscribe.py`

**Interfaces:**
- Consumes: `create_unsubscribe_token`, `verify_unsubscribe_token`, `InvalidUnsubscribeTokenError` (Task 3) ; `SavedSearch` (Task 2).

- [ ] **Step 1: Write the failing tests**

Créer `backend/tests/routers/test_saved_search_unsubscribe.py` :
```python
from app.job_search.unsubscribe import create_unsubscribe_token


def _register_and_login(client, email: str = "jane@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": email, "password": "s3cret!1"})
    return login.json()["access_token"]


def test_unsubscribe_disables_the_saved_search(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/job-search/saved-search",
        headers=headers,
        json={
            "keywords": "python",
            "exclude_keywords": [],
            "timezone": "Europe/Paris",
            "enabled": True,
        },
    )
    me = client.get("/auth/me", headers=headers).json()
    unsubscribe_token = create_unsubscribe_token(me["id"])

    response = client.get(
        f"/job-search/saved-search/unsubscribe?token={unsubscribe_token}"
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    saved = client.get("/job-search/saved-search", headers=headers).json()
    assert saved["enabled"] is False


def test_unsubscribe_is_idempotent(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/job-search/saved-search",
        headers=headers,
        json={
            "keywords": "python",
            "exclude_keywords": [],
            "timezone": "Europe/Paris",
            "enabled": True,
        },
    )
    me = client.get("/auth/me", headers=headers).json()
    unsubscribe_token = create_unsubscribe_token(me["id"])

    client.get(f"/job-search/saved-search/unsubscribe?token={unsubscribe_token}")
    second_response = client.get(
        f"/job-search/saved-search/unsubscribe?token={unsubscribe_token}"
    )

    assert second_response.status_code == 200
    saved = client.get("/job-search/saved-search", headers=headers).json()
    assert saved["enabled"] is False


def test_unsubscribe_with_invalid_token_returns_400():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get(
            "/job-search/saved-search/unsubscribe?token=garbage"
        )
    assert response.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/routers/test_saved_search_unsubscribe.py -v`
Expected: FAIL — route `/job-search/saved-search/unsubscribe` inexistante
(`404`/`405`).

- [ ] **Step 3: Write the implementation**

Dans `backend/app/routers/job_search.py`, ajouter à l'import FastAPI
existant `HTMLResponse` :
```python
from fastapi.responses import HTMLResponse
```
et l'import :
```python
from app.job_search.unsubscribe import (
    InvalidUnsubscribeTokenError,
    verify_unsubscribe_token,
)
```

Puis, à la fin du fichier :
```python
@router.get("/saved-search/unsubscribe", response_class=HTMLResponse)
def unsubscribe_saved_search(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    try:
        user_id = verify_unsubscribe_token(token)
    except InvalidUnsubscribeTokenError:
        return HTMLResponse(
            "<html><body><p>Ce lien de désabonnement n'est plus valide.</p></body></html>",
            status_code=400,
        )
    saved_search = (
        db.query(SavedSearch).filter(SavedSearch.user_id == user_id).first()
    )
    if saved_search is not None:
        saved_search.enabled = False
        db.commit()
    return HTMLResponse(
        "<html><body><p>Vous ne recevrez plus d'alertes email pour votre "
        "recherche sauvegardée.</p></body></html>"
    )
```

Cette route est déclarée **avant** aucune dépendance d'authentification —
volontairement publique (appelée depuis un client email, jamais depuis
l'app).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/routers/test_saved_search_unsubscribe.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/job_search.py backend/tests/routers/test_saved_search_unsubscribe.py
git commit -m "feat(backend): add public unsubscribe endpoint for saved searches"
```

---

## Task 7: Job quotidien (`daily_search.py`)

**Files:**
- Create: `backend/app/job_search/daily_search.py`
- Test: `backend/tests/job_search/test_daily_search.py`

**Interfaces:**
- Consumes: `search_jobs` (`aggregator.py`), `get_cached_mapping`/`save_mapping` (`company_cache.py`), `detect_company_ats` (`discovery.py`), `extract_unique_companies` (`discovery.py`), `cache_known_seed_mappings`/`get_seed_companies` (`seed_companies.py`), `get_job_search_clients` (`dependencies.py`), `SearchClient`/`SluggableSearchClient`/`SearchCriteria`/`JobListing` (`schemas.py`) — tous existants. `SavedSearch`, `NotifiedListing` (Task 2). `send_daily_digest_email`, `EmailSendError` (Task 4). `create_unsubscribe_token` (Task 3).
- Produces: `run_daily_search(db_session_factory: Callable[[], Session]) -> None` — consommé par la tâche 8 (wiring APScheduler).

- [ ] **Step 1: Write the failing tests**

Créer `backend/tests/job_search/test_daily_search.py` :
```python
from datetime import datetime, timezone as dt_timezone

import httpx
import respx

from app.job_search.daily_search import _is_notification_time, run_daily_search
from app.job_search.schemas import JobListing
from app.models.notified_listing import NotifiedListing
from app.models.saved_search import SavedSearch
from app.models.user import User


def test_is_notification_time_matches_local_8am():
    saved_search = SavedSearch(timezone="Europe/Paris")
    # 6h UTC = 8h à Paris en été (UTC+2)
    now = datetime(2026, 7, 15, 6, 0, tzinfo=dt_timezone.utc)
    assert _is_notification_time(saved_search, now) is True


def test_is_notification_time_does_not_match_other_hours():
    saved_search = SavedSearch(timezone="Europe/Paris")
    now = datetime(2026, 7, 15, 12, 0, tzinfo=dt_timezone.utc)
    assert _is_notification_time(saved_search, now) is False


class _EmptyClient:
    def search(self, criteria):
        return []


class _EmptySluggableClient:
    def search(self, criteria, company_slugs):
        return []


def _clients() -> dict[str, object]:
    return {
        "france_travail": _EmptyClient(),
        "adzuna": _EmptyClient(),
        "la_bonne_alternance": _EmptyClient(),
        "greenhouse": _EmptySluggableClient(),
        "lever": _EmptySluggableClient(),
    }


def _make_user_with_saved_search(db_session, email: str = "jane@example.com") -> User:
    user = User(email=email, hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    db_session.add(
        SavedSearch(
            user_id=user.id,
            keywords="python",
            exclude_keywords=[],
            timezone="Europe/Paris",
            enabled=True,
        )
    )
    db_session.commit()
    return user


@respx.mock
def test_run_daily_search_sends_email_and_records_notified_listings(
    db_session, monkeypatch
):
    user = _make_user_with_saved_search(db_session)

    class SingleListingClient:
        def search(self, criteria):
            return [
                JobListing(
                    title="Développeur Python",
                    company="",
                    location="Paris",
                    snippet="...",
                    url="https://example.com/job/1",
                    source="france_travail",
                    ats_type=None,
                )
            ]

    clients = _clients()
    clients["france_travail"] = SingleListingClient()
    monkeypatch.setattr(
        "app.job_search.daily_search.get_job_search_clients", lambda: clients
    )

    sent_emails = []
    monkeypatch.setattr(
        "app.job_search.daily_search.send_daily_digest_email",
        lambda to_email, listings, token: sent_emails.append((to_email, listings)),
    )

    now = datetime(2026, 7, 15, 6, 0, tzinfo=dt_timezone.utc)  # 8h à Paris
    monkeypatch.setattr("app.job_search.daily_search.datetime", _FixedDatetime(now))

    run_daily_search(lambda: db_session)

    assert len(sent_emails) == 1
    assert sent_emails[0][0] == user.email
    assert len(sent_emails[0][1]) == 1

    notified = (
        db_session.query(NotifiedListing)
        .filter(NotifiedListing.user_id == user.id)
        .all()
    )
    assert len(notified) == 1
    assert notified[0].offer_url == "https://example.com/job/1"


class _FixedDatetime:
    """Minimal stand-in for the `datetime` class exposing only what
    daily_search.run_daily_search calls (`datetime.now(UTC)`), so tests can
    freeze "now" without a third-party time-freezing dependency."""

    def __init__(self, fixed_now):
        self._fixed_now = fixed_now

    def now(self, tz=None):
        return self._fixed_now


@respx.mock
def test_run_daily_search_skips_already_notified_listings(db_session, monkeypatch):
    user = _make_user_with_saved_search(db_session)
    db_session.add(
        NotifiedListing(user_id=user.id, offer_url="https://example.com/job/1")
    )
    db_session.commit()

    class SingleListingClient:
        def search(self, criteria):
            return [
                JobListing(
                    title="Développeur Python",
                    company="",
                    location="Paris",
                    snippet="...",
                    url="https://example.com/job/1",
                    source="france_travail",
                    ats_type=None,
                )
            ]

    clients = _clients()
    clients["france_travail"] = SingleListingClient()
    monkeypatch.setattr(
        "app.job_search.daily_search.get_job_search_clients", lambda: clients
    )

    sent_emails = []
    monkeypatch.setattr(
        "app.job_search.daily_search.send_daily_digest_email",
        lambda to_email, listings, token: sent_emails.append((to_email, listings)),
    )

    now = datetime(2026, 7, 15, 6, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr("app.job_search.daily_search.datetime", _FixedDatetime(now))

    run_daily_search(lambda: db_session)

    assert sent_emails == []


@respx.mock
def test_run_daily_search_skips_users_outside_their_notification_hour(
    db_session, monkeypatch
):
    _make_user_with_saved_search(db_session)

    clients = _clients()
    monkeypatch.setattr(
        "app.job_search.daily_search.get_job_search_clients", lambda: clients
    )
    sent_emails = []
    monkeypatch.setattr(
        "app.job_search.daily_search.send_daily_digest_email",
        lambda to_email, listings, token: sent_emails.append((to_email, listings)),
    )

    now = datetime(2026, 7, 15, 12, 0, tzinfo=dt_timezone.utc)  # 14h à Paris, pas 8h
    monkeypatch.setattr("app.job_search.daily_search.datetime", _FixedDatetime(now))

    run_daily_search(lambda: db_session)

    assert sent_emails == []


@respx.mock
def test_run_daily_search_continues_after_one_user_email_fails(
    db_session, monkeypatch
):
    _make_user_with_saved_search(db_session, email="jane@example.com")
    _make_user_with_saved_search(db_session, email="bob@example.com")

    class SingleListingClient:
        def search(self, criteria):
            return [
                JobListing(
                    title="Développeur Python",
                    company="",
                    location="Paris",
                    snippet="...",
                    url="https://example.com/job/1",
                    source="france_travail",
                    ats_type=None,
                )
            ]

    clients = _clients()
    clients["france_travail"] = SingleListingClient()
    monkeypatch.setattr(
        "app.job_search.daily_search.get_job_search_clients", lambda: clients
    )

    from app.notifications.resend_client import EmailSendError

    sent_emails = []

    def fake_send(to_email, listings, token):
        if to_email == "jane@example.com":
            raise EmailSendError("boom")
        sent_emails.append(to_email)

    monkeypatch.setattr(
        "app.job_search.daily_search.send_daily_digest_email", fake_send
    )

    now = datetime(2026, 7, 15, 6, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr("app.job_search.daily_search.datetime", _FixedDatetime(now))

    run_daily_search(lambda: db_session)

    # bob's email still got sent despite jane's failing
    assert sent_emails == ["bob@example.com"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/job_search/test_daily_search.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.job_search.daily_search'`.

- [ ] **Step 3: Write the implementation**

Créer `backend/app/job_search/daily_search.py` :
```python
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.job_search.aggregator import search_jobs
from app.job_search.company_cache import get_cached_mapping, save_mapping
from app.job_search.dependencies import get_job_search_clients
from app.job_search.discovery import detect_company_ats, extract_unique_companies
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import (
    JobListing,
    SearchClient,
    SearchCriteria,
    SluggableSearchClient,
)
from app.job_search.seed_companies import cache_known_seed_mappings, get_seed_companies
from app.job_search.unsubscribe import create_unsubscribe_token
from app.models.notified_listing import NotifiedListing
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.notifications.resend_client import EmailSendError, send_daily_digest_email

logger = logging.getLogger(__name__)

NOTIFICATION_HOUR = 8


def _is_notification_time(saved_search: SavedSearch, now: datetime) -> bool:
    return now.astimezone(ZoneInfo(saved_search.timezone)).hour == NOTIFICATION_HOUR


def _resolve_and_fetch_known_companies(
    db: Session,
    criteria: SearchCriteria,
    candidate_companies: list[str],
    clients: dict[str, object],
    http_client: httpx.Client,
) -> list[JobListing]:
    known_listings: list[JobListing] = []
    for company_name in candidate_companies:
        mapping = get_cached_mapping(db, company_name)
        if mapping is None:
            result = detect_company_ats(company_name, http_client)
            if not result.confirmed:
                continue
            save_mapping(db, company_name, result.source, result.slug)
            if result.source is None:
                continue
            assert result.slug is not None  # DetectionResult always sets slug alongside source
            source, slug = result.source, result.slug
        elif mapping.source is not None:
            assert mapping.slug is not None  # CompanyAtsMapping always sets slug alongside source
            source, slug = mapping.source, mapping.slug
        else:
            continue

        client = cast(SluggableSearchClient, clients[source])
        try:
            known_listings.extend(client.search(criteria, [slug]))
        except JobSearchSourceError:
            continue
    return known_listings


def _process_saved_search(
    db: Session, saved_search: SavedSearch, clients: dict[str, object]
) -> None:
    criteria = SearchCriteria(
        keywords=saved_search.keywords,
        location=saved_search.location,
        contract_type=saved_search.contract_type,
        remote=saved_search.remote,
        exclude_keywords=saved_search.exclude_keywords,
    )
    primary_clients: dict[str, SearchClient] = {
        "france_travail": cast(SearchClient, clients["france_travail"]),
        "adzuna": cast(SearchClient, clients["adzuna"]),
        "la_bonne_alternance": cast(SearchClient, clients["la_bonne_alternance"]),
    }
    listings, _unavailable_sources = search_jobs(criteria, primary_clients)

    cache_known_seed_mappings(db, criteria.location)
    candidate_companies = list(
        dict.fromkeys(
            extract_unique_companies(listings) + get_seed_companies(criteria.location)
        )
    )

    http_client = httpx.Client(timeout=10.0)
    try:
        known_listings = _resolve_and_fetch_known_companies(
            db, criteria, candidate_companies, clients, http_client
        )
    finally:
        http_client.close()

    all_listings = listings + known_listings
    already_notified = {
        row.offer_url
        for row in db.query(NotifiedListing)
        .filter(NotifiedListing.user_id == saved_search.user_id)
        .all()
    }
    new_listings = [
        listing for listing in all_listings if listing.url not in already_notified
    ]
    if not new_listings:
        return

    user = db.get(User, saved_search.user_id)
    if user is None:
        return

    token = create_unsubscribe_token(user.id)
    try:
        send_daily_digest_email(user.email, new_listings, token)
    except EmailSendError:
        logger.error(
            "Échec de l'envoi de l'email quotidien pour l'utilisateur %s",
            user.id,
        )
        return

    for listing in new_listings:
        db.add(NotifiedListing(user_id=saved_search.user_id, offer_url=listing.url))
    db.commit()


def run_daily_search(db_session_factory: Callable[[], Session]) -> None:
    db = db_session_factory()
    try:
        clients = get_job_search_clients()
        now = datetime.now(UTC)
        saved_searches = (
            db.query(SavedSearch).filter(SavedSearch.enabled.is_(True)).all()
        )
        for saved_search in saved_searches:
            if not _is_notification_time(saved_search, now):
                continue
            try:
                _process_saved_search(db, saved_search, clients)
            except Exception:
                # Isolation volontairement large (pas une exception métier
                # précise) : une panne inattendue pour un utilisateur (bug,
                # erreur réseau, erreur DB) ne doit jamais empêcher le
                # traitement des autres utilisateurs de ce passage horaire.
                logger.exception(
                    "Échec du traitement de la recherche sauvegardée pour "
                    "l'utilisateur %s",
                    saved_search.user_id,
                )
    finally:
        db.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/job_search/test_daily_search.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run the full backend suite (non-regression)**

Run: `pytest -q`
Expected: tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add backend/app/job_search/daily_search.py backend/tests/job_search/test_daily_search.py
git commit -m "feat(backend): add the daily saved-search job (search, dedup, email)"
```

---

## Task 8: Câblage du scheduler dans `main.py`

**Files:**
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `run_daily_search` (Task 7).

- [ ] **Step 1: Modifier le lifespan**

Dans `backend/app/main.py`, ajouter les imports :
```python
from apscheduler.schedulers.background import BackgroundScheduler
```
et
```python
from app.job_search.daily_search import run_daily_search
```

Remplacer le `lifespan` existant :
```python
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
```
par :
```python
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

    # A fresh BackgroundScheduler is created on every lifespan entry
    # (rather than a module-level singleton) because APScheduler schedulers
    # cannot be restarted after shutdown() - a module-level instance would
    # break the second of any two `with TestClient(app)` blocks in the test
    # suite, which each trigger one lifespan start/stop cycle.
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        # Looked up as database.SessionLocal (not a bare `SessionLocal` name
        # imported at module load) so the test suite's monkeypatch of
        # database.SessionLocal (see tests/conftest.py) takes effect - same
        # convention as the background_discovery.run_discovery task.
        lambda: run_daily_search(database.SessionLocal),
        trigger="cron",
        minute=0,
        id="daily_search",
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
```

- [ ] **Step 2: Run the full backend suite (verify the scheduler wiring doesn't break anything)**

Run: `cd backend && source venv/bin/activate && pytest -q`
Expected: tous les tests passent, y compris ceux qui créent un
`TestClient(app)` (le scheduler démarre/s'arrête à chaque fois sans
erreur — aucun test n'attend une heure pile, donc le job ne se déclenche
jamais pendant les tests).

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(backend): wire APScheduler to run the daily saved-search job hourly"
```

---

## Task 9: Types et fonctions API frontend

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

**Interfaces:**
- Produces: `SavedSearch`, `SavedSearchInput` (types), `getSavedSearch(token)`, `saveSavedSearch(token, payload)` — consommés par la tâche 10.

- [ ] **Step 1: Write the failing tests**

Créer `frontend/lib/savedSearch.test.ts` :
```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { getSavedSearch, saveSavedSearch, ApiError } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("getSavedSearch", () => {
  it("returns null when the backend responds 404", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "not found" }, 404));
    const result = await getSavedSearch("tok123");
    expect(result).toBeNull();
  });

  it("returns the saved search when found", async () => {
    const saved = {
      keywords: "python",
      location: null,
      contract_type: null,
      remote: null,
      exclude_keywords: [],
      timezone: "Europe/Paris",
      enabled: true,
    };
    vi.mocked(fetch).mockResolvedValue(jsonResponse(saved));
    const result = await getSavedSearch("tok123");
    expect(result).toEqual(saved);
  });

  it("rethrows non-404 errors", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "boom" }, 500));
    await expect(getSavedSearch("tok123")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("saveSavedSearch", () => {
  it("PUTs the payload and returns the saved search", async () => {
    const saved = {
      keywords: "python",
      location: null,
      contract_type: null,
      remote: null,
      exclude_keywords: [],
      timezone: "Europe/Paris",
      enabled: true,
    };
    vi.mocked(fetch).mockResolvedValue(jsonResponse(saved));
    const result = await saveSavedSearch("tok123", {
      keywords: "python",
      exclude_keywords: [],
      timezone: "Europe/Paris",
      enabled: true,
    });
    expect(result).toEqual(saved);
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(init?.method).toBe("PUT");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run lib/savedSearch.test.ts`
Expected: FAIL — le module `./api` n'exporte pas encore `getSavedSearch`/
`saveSavedSearch`.

- [ ] **Step 3: Ajouter les types**

Dans `frontend/lib/types.ts`, ajouter après `JobSearchDiscoveryResult` :
```typescript
export interface SavedSearch {
  keywords: string;
  location: string | null;
  contract_type: string | null;
  remote: boolean | null;
  exclude_keywords: string[];
  timezone: string;
  enabled: boolean;
}

export interface SavedSearchInput {
  keywords: string;
  location?: string;
  contract_type?: string;
  remote?: boolean;
  exclude_keywords: string[];
  timezone: string;
  enabled: boolean;
}
```

- [ ] **Step 4: Ajouter les fonctions API**

Dans `frontend/lib/api.ts`, ajouter `SavedSearch` et `SavedSearchInput` à
l'import de types en haut du fichier, puis ajouter après
`fetchJobSearchDiscovery` :
```typescript
export async function getSavedSearch(token: string): Promise<SavedSearch | null> {
  try {
    return await request<SavedSearch>("/job-search/saved-search", { method: "GET" }, token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function saveSavedSearch(token: string, payload: SavedSearchInput): Promise<SavedSearch> {
  return request<SavedSearch>(
    "/job-search/saved-search",
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    token
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run lib/savedSearch.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/lib/savedSearch.test.ts
git commit -m "feat(frontend): add SavedSearch types and API functions"
```

---

## Task 10: Composant `SavedSearchPanel` et intégration à la page candidatures

**Files:**
- Create: `frontend/components/SavedSearchPanel.tsx`
- Test: `frontend/components/SavedSearchPanel.test.tsx`
- Modify: `frontend/app/candidatures/page.tsx`

**Interfaces:**
- Consumes: `getSavedSearch`, `saveSavedSearch` (Task 9) ; `toSearchCriteria`, `SearchCriteriaFormValue` (`SearchCriteriaForm.tsx`, existant) ; `ErrorBanner`, `toBannerContent` (existants).

- [ ] **Step 1: Write the failing test**

Créer `frontend/components/SavedSearchPanel.test.tsx` :
```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SavedSearchPanel } from "./SavedSearchPanel";
import * as api from "@/lib/api";
import { EMPTY_SEARCH_CRITERIA_FORM_VALUE } from "./SearchCriteriaForm";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    getSavedSearch: vi.fn(),
    saveSavedSearch: vi.fn(),
    ApiError: actual.ApiError,
  };
});

beforeEach(() => {
  vi.mocked(api.getSavedSearch).mockReset();
  vi.mocked(api.saveSavedSearch).mockReset();
});

describe("SavedSearchPanel", () => {
  it("shows 'Sauvegarder' when no saved search exists yet", async () => {
    vi.mocked(api.getSavedSearch).mockResolvedValue(null);
    render(
      <SavedSearchPanel
        token="tok123"
        criteria={{ ...EMPTY_SEARCH_CRITERIA_FORM_VALUE, keywords: "python" }}
      />
    );
    await waitFor(() => expect(api.getSavedSearch).toHaveBeenCalled());
    expect(screen.getByText("Sauvegarder cette recherche")).toBeInTheDocument();
    expect(screen.queryByText("Désactiver")).not.toBeInTheDocument();
  });

  it("pre-fills the timezone and shows the toggle when a saved search exists", async () => {
    vi.mocked(api.getSavedSearch).mockResolvedValue({
      keywords: "python",
      location: null,
      contract_type: null,
      remote: null,
      exclude_keywords: [],
      timezone: "America/New_York",
      enabled: true,
    });
    render(
      <SavedSearchPanel
        token="tok123"
        criteria={{ ...EMPTY_SEARCH_CRITERIA_FORM_VALUE, keywords: "python" }}
      />
    );
    await waitFor(() => expect(screen.getByText("Désactiver")).toBeInTheDocument());
    expect(screen.getByDisplayValue("America/New_York")).toBeInTheDocument();
  });

  it("calls saveSavedSearch with enabled:true when saving", async () => {
    vi.mocked(api.getSavedSearch).mockResolvedValue(null);
    vi.mocked(api.saveSavedSearch).mockResolvedValue({
      keywords: "python",
      location: null,
      contract_type: null,
      remote: null,
      exclude_keywords: [],
      timezone: "Europe/Paris",
      enabled: true,
    });
    render(
      <SavedSearchPanel
        token="tok123"
        criteria={{ ...EMPTY_SEARCH_CRITERIA_FORM_VALUE, keywords: "python" }}
      />
    );
    await waitFor(() => expect(api.getSavedSearch).toHaveBeenCalled());
    fireEvent.click(screen.getByText("Sauvegarder cette recherche"));
    await waitFor(() => expect(api.saveSavedSearch).toHaveBeenCalled());
    expect(vi.mocked(api.saveSavedSearch).mock.calls[0][1]).toMatchObject({
      keywords: "python",
      enabled: true,
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/SavedSearchPanel.test.tsx`
Expected: FAIL avec une erreur de résolution de module (`SavedSearchPanel`
n'existe pas encore).

- [ ] **Step 3: Write the implementation**

Créer `frontend/components/SavedSearchPanel.tsx` :
```tsx
"use client";

import { useEffect, useState } from "react";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { Select } from "./ui/Field";
import { ErrorBanner } from "./ErrorBanner";
import { getSavedSearch, saveSavedSearch } from "@/lib/api";
import { toBannerContent, type BannerContent } from "@/lib/errors";
import { toSearchCriteria, type SearchCriteriaFormValue } from "./SearchCriteriaForm";

const TIMEZONES = [
  "Europe/Paris",
  "Europe/London",
  "America/New_York",
  "America/Los_Angeles",
  "Africa/Dakar",
  "UTC",
];

interface SavedSearchPanelProps {
  token: string;
  criteria: SearchCriteriaFormValue;
}

export function SavedSearchPanel({ token, criteria }: SavedSearchPanelProps) {
  const [timezone, setTimezone] = useState("Europe/Paris");
  const [enabled, setEnabled] = useState(false);
  const [hasSaved, setHasSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [banner, setBanner] = useState<BannerContent | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSavedSearch(token).then((saved) => {
      if (cancelled || !saved) return;
      setTimezone(saved.timezone);
      setEnabled(saved.enabled);
      setHasSaved(true);
    });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function persist(nextEnabled: boolean) {
    setBanner(null);
    setIsSaving(true);
    try {
      const saved = await saveSavedSearch(token, {
        ...toSearchCriteria(criteria),
        timezone,
        enabled: nextEnabled,
      });
      setEnabled(saved.enabled);
      setHasSaved(true);
    } catch (error) {
      setBanner(toBannerContent(error));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Card className="mt-4 flex flex-col gap-3 p-4">
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Recherche automatique</p>
      <p className="text-sm text-slate-600 dark:text-slate-400">
        Recevez un email quotidien listant les nouvelles offres correspondant aux critères ci-dessus.
      </p>
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Fuseau horaire
        <Select value={timezone} onChange={(event) => setTimezone(event.target.value)}>
          {TIMEZONES.map((tz) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </Select>
      </label>
      {banner && <ErrorBanner content={banner} />}
      <div className="flex items-center gap-3">
        <Button
          onClick={() => persist(true)}
          isLoading={isSaving}
          disabled={criteria.keywords.trim().length === 0}
          className="w-fit"
        >
          Sauvegarder cette recherche
        </Button>
        {hasSaved && (
          <Button variant="secondary" onClick={() => persist(!enabled)} isLoading={isSaving} className="w-fit">
            {enabled ? "Désactiver" : "Activer"}
          </Button>
        )}
      </div>
    </Card>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run components/SavedSearchPanel.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Intégrer à la page candidatures**

Dans `frontend/app/candidatures/page.tsx`, ajouter l'import :
```typescript
import { SavedSearchPanel } from "@/components/SavedSearchPanel";
```
puis, juste après le bloc `<SearchCriteriaForm ... />` (avant le bloc
`isDiscovering`) :
```tsx
      {token && (
        <div className="mt-4">
          <SavedSearchPanel token={token} criteria={criteria} />
        </div>
      )}
```

- [ ] **Step 6: Run the full frontend suite (non-regression)**

Run: `npx vitest run`
Expected: tous les tests passent (les 144 précédents + les 7 nouveaux).

- [ ] **Step 7: Commit**

```bash
git add frontend/components/SavedSearchPanel.tsx frontend/components/SavedSearchPanel.test.tsx frontend/app/candidatures/page.tsx
git commit -m "feat(frontend): add SavedSearchPanel and wire it into the candidatures page"
```

---

## Task 11: Vérification finale et documentation opérationnelle

**Files:** aucun fichier de code — vérification uniquement.

**Interfaces:** aucune.

- [ ] **Step 1: Suite complète backend**

Run: `cd backend && source venv/bin/activate && ruff check . && ruff format --check . && mypy app && pytest -q`
Expected: tout est vert (ruff, mypy, 314 + nouveaux tests backend).

- [ ] **Step 2: Suite complète frontend**

Run: `cd frontend && npx eslint . && npx tsc --noEmit && npx vitest run`
Expected: tout est vert (eslint, tsc, 144 + nouveaux tests frontend).

- [ ] **Step 3: Vérification manuelle des variables d'environnement requises en production**

Documenter (dans le message de fin de tâche, pas dans un fichier) que ces
variables doivent être renseignées dans `backend/.env` avant déploiement,
sans quoi le job tourne mais n'envoie jamais d'email avec succès (Resend
rejettera une clé API vide) :
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL` (doit être une adresse d'un domaine vérifié auprès de Resend)
- `BACKEND_BASE_URL` (doit être l'URL publique réellement joignable du
  backend, utilisée dans le lien de désabonnement de chaque email — une
  valeur `localhost` en production rendrait ce lien inutilisable pour le
  destinataire)

- [ ] **Step 4: Test manuel de bout en bout (nécessite une clé Resend valide)**

1. Renseigner `RESEND_API_KEY`/`RESEND_FROM_EMAIL`/`BACKEND_BASE_URL` dans
   `backend/.env`.
2. Créer une `SavedSearch` via l'UI (page candidatures) avec des mots-clés
   larges (ex: "développeur") pour maximiser les chances de résultats, et
   un fuseau horaire dont l'heure locale correspond à l'heure actuelle + 1
   à 2 minutes (pour ne pas attendre potentiellement jusqu'à 23h).
3. Démarrer le backend (`uvicorn app.main:app`) et attendre le prochain
   passage horaire du scheduler.
4. Vérifier la réception de l'email (ou son absence si aucune offre
   réellement nouvelle n'a été trouvée — dans ce cas, vérifier dans les
   logs backend qu'aucune erreur n'est survenue).
5. Cliquer le lien de désabonnement dans l'email reçu, vérifier que la
   page de confirmation s'affiche et que le toggle repasse à "désactivé"
   dans l'UI.

Cette étape n'est pas automatisable (dépend d'une vraie clé API externe et
du passage réel du temps) — c'est une vérification manuelle, à faire une
fois avant de considérer le chantier terminé.
