# Rappels de relance et de finalisation de candidatures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Envoyer un email quotidien récapitulant, par utilisateur, les candidatures à relancer (envoyées, sans réponse depuis 7 jours) et à finaliser (jamais envoyées, créées depuis 7 jours) — jamais renvoyé deux fois pour la même candidature.

**Architecture:** Un deuxième job APScheduler, enregistré sur le même `BackgroundScheduler` déjà démarré dans le `lifespan` de `main.py` (chantier recherche proactive), tourne toutes les heures. Il réutilise le fuseau horaire de `SavedSearch` s'il existe pour l'utilisateur (sinon UTC), sélectionne les candidatures éligibles par requête SQL directe sur `Application`, envoie un seul email récapitulatif via le client Resend déjà en place, et marque `reminder_sent_at` uniquement après un envoi réussi.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, APScheduler (déjà câblé), `httpx`/Resend (déjà en place), aucune nouvelle dépendance.

**Spec:** `docs/superpowers/specs/2026-08-13-relances-candidatures-design.md`

## Global Constraints

- Un seul rappel par candidature, jamais renvoyé (`reminder_sent_at` non réinitialisé une fois posé).
- Seuil fixe de 7 jours pour les deux catégories, pas de réglage par utilisateur.
- Pas de toggle, pas de désabonnement pour cette fonctionnalité (email transactionnel).
- Fuseau horaire : `SavedSearch.timezone` si l'utilisateur en a une, sinon UTC.
- Tout envoi échoué ne marque aucune candidature (rattrapage naturel au passage suivant), même règle que `NotifiedListing` du chantier précédent.
- Toute nouvelle valeur `DateTime` doit utiliser `app.utils.time.utcnow` si un nouveau code l'exige explicitement — ici les comparaisons se font sur des `datetime` naïfs dérivés du `now` figé par le job lui-même (voir Tâche 3), pas de nouvel usage de `datetime.utcnow`.

---

## Task 1: Config et modèle de données

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/models/application.py`
- Test: `backend/tests/models/test_application.py`

**Interfaces:**
- Produces: `Settings.frontend_base_url: str` ; `Application.reminder_sent_at: datetime | None` — consommés par les tâches 2 et 3.

- [ ] **Step 1: Write the failing test**

Ajouter à la fin de `backend/tests/models/test_application.py` :
```python
def test_reminder_sent_at_defaults_to_none(db_session):
    diagnostic = _make_diagnostic(db_session)

    application = Application(
        user_id=diagnostic.user_id,
        diagnostic_id=diagnostic.id,
        offer_url="https://example.com/job/reminder-default",
        source="manual",
        company_name="Acme",
        job_title="Dev",
        ats_type=None,
        status=APPLICATION_STATUS_EN_COURS,
    )
    db_session.add(application)
    db_session.commit()

    fetched = (
        db_session.query(Application)
        .filter(Application.offer_url == "https://example.com/job/reminder-default")
        .first()
    )
    assert fetched.reminder_sent_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/models/test_application.py::test_reminder_sent_at_defaults_to_none -v`
Expected: FAIL avec `AttributeError` ou `TypeError` (le champ n'existe pas encore sur le modèle).

- [ ] **Step 3: Ajouter le champ au modèle**

Dans `backend/app/models/application.py`, ajouter après `updated_at` (avant la relation `diagnostic`) :
```python
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Ajouter le nouveau setting**

Dans `backend/app/config.py`, ajouter après `backend_base_url` :
```python
    frontend_base_url: str = "http://localhost:3000"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/models/test_application.py -v`
Expected: PASS (tous les tests du fichier, y compris le nouveau).

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/models/application.py backend/tests/models/test_application.py
git commit -m "feat(backend): add Application.reminder_sent_at and FRONTEND_BASE_URL setting"
```

---

## Task 2: Email de rappel (`resend_client.py`)

**Files:**
- Modify: `backend/app/notifications/resend_client.py`
- Modify: `backend/tests/notifications/test_resend_client.py`

**Interfaces:**
- Consumes: `Application` (Task 1), `Settings.frontend_base_url` (Task 1).
- Produces: `send_application_reminders_email(to_email: str, to_relance: list[Application], to_finalize: list[Application]) -> None` — consommé par la tâche 3.

Ce fichier contient déjà `send_daily_digest_email` (chantier précédent) — cette
tâche factorise l'appel HTTP Resend commun (`_send_email`) plutôt que de le
dupliquer une deuxième fois, et renomme `_render_html` en
`_render_job_listings_html` par précision (une deuxième fonction de rendu
apparaît dans ce fichier).

- [ ] **Step 1: Write the failing tests**

Ajouter à la fin de `backend/tests/notifications/test_resend_client.py` :
```python
from datetime import UTC, datetime

from app.models.application import Application


def _application(
    company_name: str = "Acme",
    job_title: str = "Développeur Python",
    submitted_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Application:
    return Application(
        id=1,
        user_id=1,
        diagnostic_id=1,
        offer_url="https://example.com/job/1",
        source="manual",
        company_name=company_name,
        job_title=job_title,
        ats_type=None,
        status="soumise_auto",
        submitted_at=submitted_at,
        created_at=created_at or datetime(2026, 7, 1, tzinfo=UTC).replace(tzinfo=None),
    )


@respx.mock
def test_send_application_reminders_email_posts_to_resend():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    to_relance = [
        _application(
            submitted_at=datetime(2026, 7, 1, tzinfo=UTC).replace(tzinfo=None)
        )
    ]
    to_finalize: list[Application] = []

    from app.notifications.resend_client import send_application_reminders_email

    send_application_reminders_email("jane@example.com", to_relance, to_finalize)

    assert route.called
    payload = json.loads(route.calls[0].request.content)
    assert payload["to"] == ["jane@example.com"]
    assert "1 candidature" in payload["subject"]
    assert "à relancer" in payload["subject"]
    assert "Acme" in payload["html"]
    assert "candidatures" in payload["html"]  # lien vers la page candidatures


@respx.mock
def test_send_application_reminders_email_includes_both_sections():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    to_relance = [
        _application(
            company_name="Acme",
            submitted_at=datetime(2026, 7, 1, tzinfo=UTC).replace(tzinfo=None),
        )
    ]
    to_finalize = [_application(company_name="Globex")]

    from app.notifications.resend_client import send_application_reminders_email

    send_application_reminders_email("jane@example.com", to_relance, to_finalize)

    payload = json.loads(route.calls[0].request.content)
    assert "2 candidatures" in payload["subject"]
    assert "Acme" in payload["html"]
    assert "Globex" in payload["html"]


@respx.mock
def test_send_application_reminders_email_raises_on_http_error():
    respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(422, json={"message": "invalid from address"})
    )

    from app.notifications.resend_client import send_application_reminders_email

    with pytest.raises(EmailSendError):
        send_application_reminders_email(
            "jane@example.com",
            [_application(submitted_at=datetime(2026, 7, 1, tzinfo=UTC).replace(tzinfo=None))],
            [],
        )


@respx.mock
def test_send_application_reminders_email_escapes_html_in_fields():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    to_finalize = [_application(company_name="<script>alert(1)</script>", job_title="Dev")]

    from app.notifications.resend_client import send_application_reminders_email

    send_application_reminders_email("jane@example.com", [], to_finalize)

    payload = json.loads(route.calls[0].request.content)
    assert "<script>" not in payload["html"]
    assert "&lt;script&gt;" in payload["html"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/notifications/test_resend_client.py -v -k application_reminders`
Expected: FAIL avec `ImportError: cannot import name 'send_application_reminders_email'`.

- [ ] **Step 3: Write the implementation**

Remplacer entièrement le contenu de `backend/app/notifications/resend_client.py` par :
```python
import html
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.job_search.schemas import JobListing
from app.models.application import Application

_RESEND_API_URL = "https://api.resend.com/emails"
_ALLOWED_URL_SCHEMES = {"http", "https"}


class EmailSendError(Exception):
    pass


def _safe_href(url: str) -> str:
    """Only http(s) URLs are ever linked - rejects `javascript:` and other
    executable schemes a compromised/malicious upstream source could
    smuggle in. HTML-escaping alone does not stop this, since the scheme
    itself contains no special HTML characters to escape."""
    if urlsplit(url).scheme not in _ALLOWED_URL_SCHEMES:
        return "#"
    return html.escape(url)


def _send_email(to_email: str, subject: str, html_body: str) -> None:
    settings = get_settings()
    response = httpx.post(
        _RESEND_API_URL,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        },
        timeout=10.0,
    )
    if response.status_code >= 400:
        raise EmailSendError(
            f"Échec de l'envoi de l'email via Resend ({response.status_code}): {response.text}"
        )


def _render_job_listings_html(listings: list[JobListing], unsubscribe_url: str) -> str:
    # Every field interpolated here (title/company/location, all from
    # external job-search APIs we don't control) is HTML-escaped - without
    # it, a listing whose title/company contained raw HTML would be
    # rendered as-is in the recipient's email client.
    items = "".join(
        f'<li><a href="{_safe_href(listing.url)}">{html.escape(listing.title)}</a>'
        f" — {html.escape(listing.company)}"
        f"{f' ({html.escape(listing.location)})' if listing.location else ''}</li>"
        for listing in listings
    )
    return (
        "<p>Nouvelles offres correspondant à votre recherche :</p>"
        f"<ul>{items}</ul>"
        f'<p><a href="{_safe_href(unsubscribe_url)}">Se désabonner de ces alertes</a></p>'
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
    _send_email(
        to_email, subject, _render_job_listings_html(listings, unsubscribe_url)
    )


def _render_application_reminders_html(
    to_relance: list[Application],
    to_finalize: list[Application],
    candidatures_url: str,
) -> str:
    # company_name/job_title are, like a JobListing's fields, ultimately
    # sourced from external APIs or free-form user input - HTML-escaped for
    # the same reason as _render_job_listings_html above.
    sections = []
    if to_relance:
        items = []
        for application in to_relance:
            assert (
                application.submitted_at is not None
            )  # to_relance is filtered on submitted_at <= cutoff
            items.append(
                f"<li>{html.escape(application.job_title)} — "
                f"{html.escape(application.company_name)} "
                f"(envoyée le {application.submitted_at.strftime('%d/%m/%Y')})</li>"
            )
        sections.append(
            "<p>Candidatures à relancer (envoyées, sans réponse) :</p>"
            f"<ul>{''.join(items)}</ul>"
        )
    if to_finalize:
        items = [
            f"<li>{html.escape(application.job_title)} — "
            f"{html.escape(application.company_name)} "
            f"(créée le {application.created_at.strftime('%d/%m/%Y')})</li>"
            for application in to_finalize
        ]
        sections.append(
            "<p>Candidatures à finaliser (jamais envoyées) :</p>"
            f"<ul>{''.join(items)}</ul>"
        )
    sections.append(
        f'<p><a href="{_safe_href(candidatures_url)}">Voir mes candidatures</a></p>'
    )
    return "".join(sections)


def send_application_reminders_email(
    to_email: str, to_relance: list[Application], to_finalize: list[Application]
) -> None:
    settings = get_settings()
    count = len(to_relance) + len(to_finalize)
    subject = f"{count} candidature{'s' if count > 1 else ''} à relancer ou finaliser"
    candidatures_url = f"{settings.frontend_base_url}/candidatures"
    _send_email(
        to_email,
        subject,
        _render_application_reminders_html(to_relance, to_finalize, candidatures_url),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/notifications/test_resend_client.py -v`
Expected: PASS (9 tests : les 5 existants pour `send_daily_digest_email`,
inchangés dans leur comportement malgré le refactor, + les 4 nouveaux).

- [ ] **Step 5: Run the full backend suite (non-regression)**

Run: `pytest -q`
Expected: tous les tests passent (aucune régression sur
`send_daily_digest_email`, dont le comportement externe est identique
après le refactor).

- [ ] **Step 6: Commit**

```bash
git add backend/app/notifications/resend_client.py backend/tests/notifications/test_resend_client.py
git commit -m "feat(backend): add application reminders email, factor out shared send helper"
```

---

## Task 3: Job de rappel (`app/applications/reminders.py`)

**Files:**
- Create: `backend/app/applications/reminders.py`
- Test: `backend/tests/applications/test_reminders.py`

**Interfaces:**
- Consumes: `Application`, statuts `APPLICATION_STATUS_*` (`app.models.application`) ; `SavedSearch` (`app.models.saved_search`) ; `User` (`app.models.user`) ; `send_application_reminders_email`, `EmailSendError` (Task 2).
- Produces: `run_application_reminders(db_session_factory: Callable[[], Session]) -> None` — consommé par la tâche 4.

- [ ] **Step 1: Write the failing tests**

Créer `backend/tests/applications/test_reminders.py` :
```python
from datetime import UTC, datetime, timedelta

from app.applications.reminders import _is_notification_time, run_application_reminders
from app.models.application import (
    APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
    APPLICATION_STATUS_EN_COURS,
    APPLICATION_STATUS_SOUMISE_AUTO,
    Application,
)
from app.models.diagnostic import Diagnostic
from app.models.saved_search import SavedSearch
from app.models.user import User


def test_is_notification_time_matches_local_8am():
    now = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)  # 8h à Paris en été
    assert _is_notification_time("Europe/Paris", now) is True


def test_is_notification_time_does_not_match_other_hours():
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    assert _is_notification_time("Europe/Paris", now) is False


def _make_user(db_session, email: str = "jane@example.com") -> User:
    user = User(email=email, hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    return user


def _make_diagnostic(db_session, user: User) -> Diagnostic:
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


def _make_application(db_session, user, diagnostic, offer_url, **overrides):
    application = Application(
        user_id=user.id,
        diagnostic_id=diagnostic.id,
        offer_url=offer_url,
        source="manual",
        company_name="Acme",
        job_title="Développeur Python",
        ats_type=None,
        status=APPLICATION_STATUS_EN_COURS,
        **overrides,
    )
    db_session.add(application)
    db_session.commit()
    return application


class _FixedDatetime:
    """Minimal stand-in for the `datetime` class exposing only what
    run_application_reminders calls (`datetime.now(UTC)`), so tests can
    freeze "now" without a third-party time-freezing dependency."""

    def __init__(self, fixed_now):
        self._fixed_now = fixed_now

    def now(self, tz=None):
        return self._fixed_now


_NOW = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)  # 8h à Paris
_TEN_DAYS_AGO = _NOW.replace(tzinfo=None) - timedelta(days=10)
_TWO_DAYS_AGO = _NOW.replace(tzinfo=None) - timedelta(days=2)


def test_run_application_reminders_selects_and_marks_application_to_relance(
    db_session, monkeypatch
):
    user = _make_user(db_session)
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
    diagnostic = _make_diagnostic(db_session, user)
    application = _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
    )
    application_id = application.id
    user_email = user.email  # captured before run_application_reminders closes
    # the session below - accessing user.email afterwards would raise
    # DetachedInstanceError (same pitfall as test_daily_search.py in the
    # previous chantier: db.close() expires already-loaded attributes, but
    # a fresh query like db_session.get(...) below still works fine).

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(
            (to_email, to_relance, to_finalize)
        ),
    )
    monkeypatch.setattr("app.applications.reminders.datetime", _FixedDatetime(_NOW))

    run_application_reminders(lambda: db_session)

    assert len(sent) == 1
    assert sent[0][0] == user_email
    assert len(sent[0][1]) == 1  # to_relance
    assert sent[0][2] == []  # to_finalize

    refreshed = db_session.get(Application, application_id)
    assert refreshed.reminder_sent_at is not None


def test_run_application_reminders_selects_application_to_finalize(
    db_session, monkeypatch
):
    user = _make_user(db_session)
    diagnostic = _make_diagnostic(db_session, user)
    _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
        created_at=_TEN_DAYS_AGO,
    )

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(
            (to_email, to_relance, to_finalize)
        ),
    )
    # No SavedSearch for this user - falls back to UTC, so 6h UTC is not
    # their notification hour. Use 8h UTC instead.
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert len(sent) == 1
    assert sent[0][1] == []  # to_relance
    assert len(sent[0][2]) == 1  # to_finalize


def test_run_application_reminders_excludes_recent_applications(db_session, monkeypatch):
    user = _make_user(db_session)
    diagnostic = _make_diagnostic(db_session, user)
    _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TWO_DAYS_AGO,
    )

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(to_email),
    )
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert sent == []


def test_run_application_reminders_excludes_already_reminded(db_session, monkeypatch):
    user = _make_user(db_session)
    diagnostic = _make_diagnostic(db_session, user)
    _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
        reminder_sent_at=_TWO_DAYS_AGO,
    )

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(to_email),
    )
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert sent == []


def test_run_application_reminders_skips_users_outside_their_notification_hour(
    db_session, monkeypatch
):
    user = _make_user(db_session)
    diagnostic = _make_diagnostic(db_session, user)
    _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
    )

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(to_email),
    )
    # No SavedSearch -> UTC fallback; 14h UTC is never the notification hour.
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 14, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert sent == []


def test_run_application_reminders_continues_after_one_user_email_fails(
    db_session, monkeypatch
):
    jane = _make_user(db_session, email="jane@example.com")
    jane_diagnostic = _make_diagnostic(db_session, jane)
    _make_application(
        db_session,
        jane,
        jane_diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
    )

    bob = _make_user(db_session, email="bob@example.com")
    bob_diagnostic = _make_diagnostic(db_session, bob)
    _make_application(
        db_session,
        bob,
        bob_diagnostic,
        "https://example.com/job/2",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
    )

    from app.notifications.resend_client import EmailSendError

    sent = []

    def fake_send(to_email, to_relance, to_finalize):
        if to_email == "jane@example.com":
            raise EmailSendError("boom")
        sent.append(to_email)

    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email", fake_send
    )
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert sent == ["bob@example.com"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/applications/test_reminders.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.applications.reminders'`.

- [ ] **Step 3: Write the implementation**

Créer `backend/app/applications/reminders.py` :
```python
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.application import (
    APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
    APPLICATION_STATUS_EN_COURS,
    APPLICATION_STATUS_SOUMISE_AUTO,
    APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE,
    Application,
)
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.notifications.resend_client import EmailSendError, send_application_reminders_email

logger = logging.getLogger(__name__)

NOTIFICATION_HOUR = 8
REMINDER_THRESHOLD_DAYS = 7


def _user_timezone(db: Session, user_id: int) -> str:
    saved_search = (
        db.query(SavedSearch).filter(SavedSearch.user_id == user_id).first()
    )
    if saved_search is not None:
        return saved_search.timezone
    return "UTC"


def _is_notification_time(timezone: str, now: datetime) -> bool:
    return now.astimezone(ZoneInfo(timezone)).hour == NOTIFICATION_HOUR


def _process_user(db: Session, user_id: int, now: datetime) -> None:
    cutoff = now.replace(tzinfo=None) - timedelta(days=REMINDER_THRESHOLD_DAYS)

    to_relance = (
        db.query(Application)
        .filter(
            Application.user_id == user_id,
            Application.status.in_(
                [
                    APPLICATION_STATUS_SOUMISE_AUTO,
                    APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE,
                ]
            ),
            Application.submitted_at <= cutoff,
            Application.reminder_sent_at.is_(None),
        )
        .all()
    )
    to_finalize = (
        db.query(Application)
        .filter(
            Application.user_id == user_id,
            Application.status.in_(
                [
                    APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
                    APPLICATION_STATUS_EN_COURS,
                ]
            ),
            Application.created_at <= cutoff,
            Application.reminder_sent_at.is_(None),
        )
        .all()
    )

    if not to_relance and not to_finalize:
        return

    user = db.get(User, user_id)
    if user is None:
        return

    try:
        send_application_reminders_email(user.email, to_relance, to_finalize)
    except EmailSendError:
        logger.error(
            "Échec de l'envoi de l'email de rappel de candidatures pour "
            "l'utilisateur %s",
            user_id,
        )
        return

    reminded_at = now.replace(tzinfo=None)
    for application in to_relance + to_finalize:
        application.reminder_sent_at = reminded_at
    db.commit()


def run_application_reminders(db_session_factory: Callable[[], Session]) -> None:
    db = db_session_factory()
    try:
        now = datetime.now(UTC)
        user_ids = [row[0] for row in db.query(Application.user_id).distinct().all()]
        for user_id in user_ids:
            timezone = _user_timezone(db, user_id)
            if not _is_notification_time(timezone, now):
                continue
            try:
                _process_user(db, user_id, now)
            except Exception:
                # Isolation volontairement large, même convention que
                # app.job_search.daily_search.run_daily_search : une panne
                # inattendue pour un utilisateur ne doit jamais empêcher le
                # traitement des autres utilisateurs de ce passage horaire.
                logger.exception(
                    "Échec du traitement des rappels de candidatures pour "
                    "l'utilisateur %s",
                    user_id,
                )
    finally:
        db.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/applications/test_reminders.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Run the full backend suite (non-regression)**

Run: `pytest -q`
Expected: tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add backend/app/applications/reminders.py backend/tests/applications/test_reminders.py
git commit -m "feat(backend): add the application follow-up/finalization reminders job"
```

---

## Task 4: Câblage dans `main.py`

**Files:**
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `run_application_reminders` (Task 3).

- [ ] **Step 1: Ajouter le deuxième job au scheduler**

Dans `backend/app/main.py`, ajouter l'import après celui de `run_daily_search` :
```python
from app.applications.reminders import run_application_reminders
from app.job_search.daily_search import run_daily_search
```

Puis, dans le `lifespan`, ajouter un deuxième `scheduler.add_job(...)` juste
après celui de `daily_search` (avant `scheduler.start()`) :
```python
    scheduler.add_job(
        lambda: run_daily_search(database.SessionLocal),
        trigger="cron",
        minute=0,
        id="daily_search",
    )
    scheduler.add_job(
        # Same rationale as the daily_search job above: looked up as
        # database.SessionLocal at call time, not imported at module load,
        # so the test suite's monkeypatch takes effect.
        lambda: run_application_reminders(database.SessionLocal),
        trigger="cron",
        minute=0,
        id="application_reminders",
    )
    scheduler.start()
```

- [ ] **Step 2: Run the full backend suite (verify the second job doesn't break anything)**

Run: `cd backend && source venv/bin/activate && pytest -q`
Expected: tous les tests passent (les deux jobs démarrent/s'arrêtent à
chaque `TestClient(app)` sans erreur ; aucun test n'attend une heure pile,
donc ni l'un ni l'autre ne se déclenche pendant les tests).

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(backend): wire the application reminders job into the scheduler"
```

---

## Task 5: Vérification finale

**Files:** aucun fichier de code — vérification uniquement.

**Interfaces:** aucune.

- [ ] **Step 1: Suite complète backend**

Run: `cd backend && source venv/bin/activate && ruff check . && ruff format --check . && mypy app && pytest -q`
Expected: tout est vert.

- [ ] **Step 2: Vérification manuelle des nouvelles variables d'environnement**

`FRONTEND_BASE_URL` doit être renseignée dans `backend/.env` en production
(l'URL publique réelle du frontend, pas `localhost`) — sinon le lien « Voir
mes candidatures » dans l'email de rappel pointe vers une adresse
inatteignable pour le destinataire. Pas de nouvelle variable côté Resend
(réutilise `RESEND_API_KEY`/`RESEND_FROM_EMAIL` déjà configurés).

- [ ] **Step 3: Test manuel de bout en bout**

Nécessite au moins une candidature existante avec un statut/date antérieurs
de 7 jours ou plus (ou modifier temporairement `REMINDER_THRESHOLD_DAYS` en
local pour un test rapide, comme cela avait été envisagé pour le fuseau
horaire du chantier recherche proactive) :
1. Créer/mettre à jour une candidature en base avec `status="soumise_auto"`
   et `submitted_at` à plus de 7 jours dans le passé (ou `status=
   "a_soumettre_manuellement"` avec `created_at` ancien).
2. Démarrer le backend, attendre le prochain passage horaire correspondant
   à l'heure locale de notification.
3. Vérifier la réception de l'email et son contenu (les bonnes candidatures
   dans la bonne section, lien vers `/candidatures` fonctionnel).
4. Vérifier en base que `reminder_sent_at` est renseigné sur la candidature
   concernée, et qu'un deuxième passage horaire ne renvoie pas l'email.

Comme pour le chantier précédent, cette étape n'est pas automatisable
(dépend du passage réel du temps et d'une vraie clé Resend) — vérification
manuelle à faire une fois avant de considérer ce chantier terminé.
