# Beta — Plan 3 : Quotas & coûts LLM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plafonner mensuellement, par utilisateur et par fonctionnalité, tous les appels LLM ; enregistrer chaque appel (feature + tokens) dans une table unique ; fournir un interrupteur global ; exposer l'utilisation à l'utilisateur.

**Architecture:** Une table `llm_call_log` (une ligne = une action LLM réussie, tokens agrégés) est la source de vérité unique pour l'enforcement des quotas, les stats et le futur dashboard admin. Un wrapper `UsageRecordingAnthropic` autour du client SDK note les tokens de chaque `messages.create` dans un `ContextVar` ; les endpoints/jobs lisent l'agrégat et écrivent une ligne. `enforce_monthly_quota` compte les lignes du mois calendaire courant et compare à `settings.llm_monthly_quotas` (ou à `User.quota_overrides`). Les limites **horaires** existantes (`app/rate_limit/limiter.py`) sont **conservées** (anti-rafale). Un flag `app_setting` + une dépendance `require_llm_enabled` coupent toutes les fonctionnalités LLM sans redéploiement.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, `contextvars`, anthropic SDK, pytest, Next 16.

**Spec:** `docs/superpowers/specs/2026-08-29-lancement-beta-design.md` — §4 en entier (4.1 principe, 4.2 `LlmCallLog`, 4.3 enforcement, 4.4 config, 4.5 interrupteur, 4.6 console — hors code, 4.7 frontend, 4.8 modèles — pas de changement).

## Global Constraints

- **Branche** `feature/beta-launch`, jamais `main`. Commits scopés.
- **Migrations Alembic additives** : nouvelles tables + colonne `users.quota_overrides` **nullable** (JSON).
- **Ne pas modifier les limites horaires existantes** ni la logique `lock_user_for_rate_limit` / `db.commit()` avant `BackgroundTasks` (classe de deadlock connue — cf. [[dev-workflow-feedback]] / spec afrique-ouest). `enforce_monthly_quota` **ne lit que** (aucun lock supplémentaire) et se place à côté du `check_*_rate_limit` existant.
- **Une ligne `llm_call_log` = une action utilisateur** (pas une par sous-appel Anthropic), tokens sommés sur les sous-appels — pour que le comptage de quota reste juste même quand une génération chaîne plusieurs appels (retries, interview-prep en 2 phases).
- **Datetimes naïfs UTC** ; `app.utils.time.utcnow()`.
- **`requirements.txt`** : aucune nouvelle dépendance.
- **Messages FR** ; réponses machine-lisibles : quota → `429 {code:"quota_exceeded", ...}`, interrupteur → `503 {code:"llm_paused", ...}`.
- **Après modif backend testée** : rebuild du conteneur (`docker compose ... up -d --build backend`).
- **Features** (identifiants figés) : `diagnostic`, `cv`, `lettre`, `compatibility`, `interview_prep`, `ats_prefill`.

---

## File Structure

**Créés :**
- `backend/app/models/llm_call_log.py` — `LlmCallLog`.
- `backend/app/models/app_setting.py` — `AppSetting` (clé/valeur).
- `backend/app/llm/__init__.py`
- `backend/app/llm/usage.py` — `capture_usage()` (contextmanager), `collected()`, `_note()`.
- `backend/app/llm/client.py` — `build_anthropic_client(**kw)` → `UsageRecordingAnthropic`.
- `backend/app/llm/switch.py` — `llm_features_enabled(db)`, `set_llm_features_enabled(db, bool)`.
- `backend/app/llm/dependencies.py` — `require_llm_enabled` (dépendance FastAPI).
- `backend/app/rate_limit/llm_quota.py` — `enforce_monthly_quota`, `record_llm_call`, `usage_summary`, `QuotaExceeded`, `FEATURES`, `FEATURE_LABELS`.
- `backend/scripts/llm_switch.py` — CLI `on|off|status`.
- `backend/alembic/versions/<rev>_add_llm_call_log.py`
- `backend/alembic/versions/<rev>_add_app_setting.py`
- `backend/alembic/versions/<rev>_add_user_quota_overrides.py`
- `backend/tests/llm/test_usage_capture.py`
- `backend/tests/rate_limit/test_llm_quota.py`
- `backend/tests/llm/test_switch.py`
- `backend/tests/routers/test_llm_quota_wiring.py`
- `frontend/components/account/UsageGauges.tsx`

**Modifiés :**
- `backend/app/config.py` — `llm_monthly_quota_*` (6 clés) + propriété `llm_monthly_quotas` ; `llm_features_enabled: bool = True`.
- `backend/app/models/__init__.py` — enregistrer `LlmCallLog`, `AppSetting`.
- `backend/app/models/user.py` — `quota_overrides: Mapped[dict | None]` (JSON).
- `backend/app/llm_analyzer/dependencies.py`, `backend/app/compatibility/dependencies.py`, `backend/app/personalization/dependencies.py`, `backend/app/interview_prep/dependencies.py`, `backend/app/ats_adapters/dependencies.py` — `anthropic.Anthropic(...)` → `build_anthropic_client(...)`.
- `backend/app/routers/diagnostics.py` — kill-switch dep + quota `diagnostic` + `record_llm_call`.
- `backend/app/routers/job_search.py` — kill-switch dep + quota `compatibility` + `record_llm_call` (endpoint `compatibility-detail`).
- `backend/app/routers/applications.py` — kill-switch dep + quota `ats_prefill` + `record_llm_call` (`get_prefilled_form`).
- `backend/app/routers/personalization.py` — kill-switch dep + quota `cv`/`lettre` (synchrone, avant `db.commit()`).
- `backend/app/routers/interview_prep.py` — kill-switch dep + quota `interview_prep` (avant `db.commit()`).
- `backend/app/personalization/jobs.py` — `capture_usage()` autour des appels + `record_llm_call` à côté de `PersonalizationRequestLog`.
- `backend/app/interview_prep/jobs.py` — idem, feature `interview_prep`.
- `backend/app/routers/auth.py` — `GET /auth/me/usage`.
- `backend/app/schemas/auth.py` — `UsageItemOut`.
- `frontend/lib/api.ts` — `getUsage`, gestion `quota_exceeded` / `llm_paused` (code d'erreur).
- `frontend/lib/types.ts` — `UsageItem`.
- `frontend/app/(app)/profil/page.tsx` — insérer `<UsageGauges />`.
- `frontend/components/**` (là où les erreurs de génération s'affichent) — afficher un encart dédié quand `err.code === "quota_exceeded"` ou `"llm_paused"`.

---

## Task 1 : `LlmCallLog` + `User.quota_overrides` + migrations

**Files:**
- Create: `backend/app/models/llm_call_log.py`, `backend/alembic/versions/<rev>_add_llm_call_log.py`, `backend/alembic/versions/<rev>_add_user_quota_overrides.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/models/user.py`
- Test: `backend/tests/rate_limit/test_llm_quota.py` (créé, complété Task 4)

**Interfaces:**
- Produces:
  - `LlmCallLog` — `id`, `user_id: int` (FK `users.id`, `ondelete="CASCADE"`, index), `feature: str(32)` (index), `model: str(64) | None`, `input_tokens: int | None`, `output_tokens: int | None`, `created_at: datetime` (index, `default=datetime.utcnow`).
  - `User.quota_overrides: dict | None` (colonne `JSON`, nullable) — ex. `{"cv": 20}`.

- [ ] **Step 1 : Test qui échoue**

`backend/tests/rate_limit/test_llm_quota.py` :

```python
from app.models.llm_call_log import LlmCallLog
from app.models.user import User


def test_llm_call_log_row_roundtrips(db_session):
    u = User(email="u@e.com", hashed_password="x", quota_overrides={"cv": 20})
    db_session.add(u)
    db_session.commit()
    db_session.add(LlmCallLog(user_id=u.id, feature="cv", model="claude-sonnet-5",
                              input_tokens=1200, output_tokens=800))
    db_session.commit()
    row = db_session.query(LlmCallLog).one()
    assert row.feature == "cv" and row.input_tokens == 1200
    assert db_session.get(User, u.id).quota_overrides == {"cv": 20}
```

- [ ] **Step 2 : Vérifier l'échec** — `pytest tests/rate_limit/test_llm_quota.py -v` → FAIL.

- [ ] **Step 3 : Modèle `LlmCallLog`**

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LlmCallLog(Base):
    """One row per successful user-facing LLM action (tokens summed over any
    sub-calls). Single source of truth for monthly quota enforcement, usage
    stats, and the admin dashboard."""

    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    feature: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )
```

- [ ] **Step 4 : `User.quota_overrides`**

`backend/app/models/user.py` — importer `JSON` de `sqlalchemy`, ajouter :

```python
    quota_overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 5 : Enregistrer + migrations**

`__init__.py` : import + `__all__`. Deux migrations :

```python
# _add_llm_call_log
def upgrade() -> None:
    op.create_table(
        "llm_call_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_llm_call_logs_user_id", "llm_call_logs", ["user_id"])
    op.create_index("ix_llm_call_logs_feature", "llm_call_logs", ["feature"])
    op.create_index("ix_llm_call_logs_created_at", "llm_call_logs", ["created_at"])

def downgrade() -> None:
    op.drop_table("llm_call_logs")

# _add_user_quota_overrides
def upgrade() -> None:
    op.add_column("users", sa.Column("quota_overrides", sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "quota_overrides")
```

Chaîner les `down_revision` (llm_call_log après la tête courante, quota_overrides après llm_call_log).

- [ ] **Step 6 : Vérifier** — `pytest tests/rate_limit/test_llm_quota.py -v` PASS ; `alembic upgrade head --sql >/dev/null`.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/models/llm_call_log.py backend/app/models/user.py backend/app/models/__init__.py backend/alembic/versions/*_add_llm_call_log.py backend/alembic/versions/*_add_user_quota_overrides.py backend/tests/rate_limit/test_llm_quota.py
git commit -m "feat(llm): LlmCallLog table + User.quota_overrides"
```

---

## Task 2 : Capture d'usage tokens (`app/llm/usage.py` + `client.py`)

**Files:**
- Create: `backend/app/llm/__init__.py`, `backend/app/llm/usage.py`, `backend/app/llm/client.py`
- Test: `backend/tests/llm/test_usage_capture.py`

**Interfaces:**
- Produces:
  - `app.llm.usage.capture_usage()` — contextmanager ; à l'intérieur, chaque `messages.create` d'un client construit par `build_anthropic_client` est noté.
  - `app.llm.usage.collected() -> tuple[str | None, int, int]` — `(model_du_premier_appel, somme_input_tokens, somme_output_tokens)` ; `(None, 0, 0)` si rien noté.
  - `app.llm.client.build_anthropic_client(**kwargs) -> UsageRecordingAnthropic` — `kwargs` passés tels quels à `anthropic.Anthropic`. Proxifie `.messages.create` ; délègue tout le reste via `__getattr__`.

- [ ] **Step 1 : Tests qui échouent**

`backend/tests/llm/test_usage_capture.py` :

```python
from app.llm.client import build_anthropic_client
from app.llm.usage import capture_usage, collected


class _FakeUsage:
    def __init__(self, i, o):
        self.input_tokens, self.output_tokens = i, o


class _FakeResp:
    def __init__(self, i, o):
        self.usage = _FakeUsage(i, o)
        self.content = []


class _FakeMessages:
    def create(self, **kw):
        return _FakeResp(100, 50)


class _FakeAnthropic:
    def __init__(self, **kw):
        self.messages = _FakeMessages()


def test_capture_sums_tokens_across_calls(monkeypatch):
    monkeypatch.setattr("app.llm.client.anthropic.Anthropic", _FakeAnthropic)
    client = build_anthropic_client(api_key="x")
    with capture_usage():
        client.messages.create(model="claude-haiku-4-5-20251001", messages=[])
        client.messages.create(model="claude-haiku-4-5-20251001", messages=[])
        assert collected() == ("claude-haiku-4-5-20251001", 200, 100)


def test_no_capture_context_is_noop(monkeypatch):
    monkeypatch.setattr("app.llm.client.anthropic.Anthropic", _FakeAnthropic)
    client = build_anthropic_client(api_key="x")
    client.messages.create(model="m", messages=[])  # must not raise
    assert collected() == (None, 0, 0)


def test_contexts_are_isolated(monkeypatch):
    monkeypatch.setattr("app.llm.client.anthropic.Anthropic", _FakeAnthropic)
    client = build_anthropic_client(api_key="x")
    with capture_usage():
        client.messages.create(model="m", messages=[])
    with capture_usage():
        assert collected() == (None, 0, 0)
```

- [ ] **Step 2 : Vérifier l'échec** — FAIL (modules absents).

- [ ] **Step 3 : `app/llm/usage.py`**

```python
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_calls: ContextVar[list["_Call"] | None] = ContextVar("_llm_calls", default=None)


@dataclass(frozen=True)
class _Call:
    model: str | None
    input_tokens: int
    output_tokens: int


@contextmanager
def capture_usage():
    token = _calls.set([])
    try:
        yield
    finally:
        _calls.reset(token)


def _note(model: str | None, usage) -> None:
    bucket = _calls.get()
    if bucket is None:
        return
    it = int(getattr(usage, "input_tokens", 0) or 0)
    ot = int(getattr(usage, "output_tokens", 0) or 0)
    bucket.append(_Call(model, it, ot))


def collected() -> tuple[str | None, int, int]:
    bucket = _calls.get() or []
    if not bucket:
        return (None, 0, 0)
    return (
        bucket[0].model,
        sum(c.input_tokens for c in bucket),
        sum(c.output_tokens for c in bucket),
    )
```

- [ ] **Step 4 : `app/llm/client.py`**

```python
import anthropic

from app.llm.usage import _note


class _RecordingMessages:
    def __init__(self, inner):
        self._inner = inner

    def create(self, **kwargs):
        response = self._inner.create(**kwargs)
        _note(kwargs.get("model"), getattr(response, "usage", None))
        return response

    def __getattr__(self, name):
        return getattr(self._inner, name)


class UsageRecordingAnthropic:
    """Thin proxy over anthropic.Anthropic that records token usage of every
    messages.create() call into the app.llm.usage ContextVar. All other
    attributes (`.beta`, streaming, etc.) delegate straight through -
    usage for those paths is simply not recorded (acceptable: the 5 analyzers
    in this app only use messages.create)."""

    def __init__(self, inner):
        self._inner = inner
        self.messages = _RecordingMessages(inner.messages)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def build_anthropic_client(**kwargs) -> UsageRecordingAnthropic:
    return UsageRecordingAnthropic(anthropic.Anthropic(**kwargs))
```

- [ ] **Step 5 : Vérifier** — `pytest tests/llm/test_usage_capture.py -v` PASS.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/llm/__init__.py backend/app/llm/usage.py backend/app/llm/client.py backend/tests/llm/test_usage_capture.py
git commit -m "feat(llm): token-usage capture via a ContextVar + client proxy"
```

---

## Task 3 : Rebrancher les 5 fabriques de client Anthropic

**Files:**
- Modify: `backend/app/llm_analyzer/dependencies.py`, `backend/app/compatibility/dependencies.py`, `backend/app/personalization/dependencies.py`, `backend/app/interview_prep/dependencies.py`, `backend/app/ats_adapters/dependencies.py`

**Interfaces:**
- Consumes: `app.llm.client.build_anthropic_client` (Task 2).
- Produces: aucun changement de signature publique — les analyzers reçoivent un `UsageRecordingAnthropic` (compatible en canard avec `anthropic.Anthropic` pour `.messages.create`).

- [ ] **Step 1 : Remplacer dans chaque fichier**

`import anthropic` → `from app.llm.client import build_anthropic_client`.
`anthropic.Anthropic(api_key=..., timeout=..., max_retries=0)` → `build_anthropic_client(api_key=..., timeout=..., max_retries=0)`.
Garder tous les commentaires/valeurs de timeout existants.

- [ ] **Step 2 : Non-régression complète**

Run: `cd backend && pytest -q && ruff check app/ && mypy app`
Expected: suite verte (les tests LLM mockent `client.messages.create` — le proxy est transparent), lint/mypy OK.

- [ ] **Step 3 : Commit**

```bash
git add backend/app/llm_analyzer/dependencies.py backend/app/compatibility/dependencies.py backend/app/personalization/dependencies.py backend/app/interview_prep/dependencies.py backend/app/ats_adapters/dependencies.py
git commit -m "refactor(llm): build all Anthropic clients through the usage-recording proxy"
```

---

## Task 4 : `llm_quota.py` — enforcement, enregistrement, résumé

**Files:**
- Create: `backend/app/rate_limit/llm_quota.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/rate_limit/test_llm_quota.py` (compléter)

**Interfaces:**
- Consumes: `LlmCallLog`, `User`, `settings.llm_monthly_quotas`.
- Produces:
  - `FEATURES: tuple[str, ...]` = `("diagnostic","cv","lettre","compatibility","interview_prep","ats_prefill")`.
  - `FEATURE_LABELS: dict[str, str]` (FR : `{"diagnostic":"diagnostics","cv":"CV générés","lettre":"lettres de motivation","compatibility":"analyses de compatibilité","interview_prep":"préparations d'entretien","ats_prefill":"préremplissages de formulaire"}`).
  - `QuotaExceeded(Exception)` avec `.feature: str`, `.limit: int`, `.reset_date: str` (ISO date), `.as_dict() -> dict` (`{"code":"quota_exceeded","feature":...,"limit":...,"reset_date":...,"message":"Tu as atteint ta limite beta de {limit} {label} ce mois-ci. Elle se réinitialise le {reset_date}."}`).
  - `monthly_limit(user: User, feature: str) -> int`.
  - `used_this_month(db, user_id: int, feature: str) -> int`.
  - `enforce_monthly_quota(db, user: User, feature: str) -> None` — lève `QuotaExceeded` si `used_this_month >= monthly_limit`.
  - `record_llm_call(db, *, user_id: int, feature: str, model: str | None = None, input_tokens: int | None = None, output_tokens: int | None = None) -> None` — `db.add(LlmCallLog(...))` + `db.commit()`.
  - `usage_summary(db, user: User) -> list[dict]` — un dict par feature : `{"feature","label","used","limit","reset_date"}`.

- [ ] **Step 1 : Config**

`backend/app/config.py` — dans `Settings` :

```python
    llm_features_enabled: bool = True
    llm_monthly_quota_diagnostic: int = 7
    llm_monthly_quota_cv: int = 5
    llm_monthly_quota_lettre: int = 5
    llm_monthly_quota_compatibility: int = 13
    llm_monthly_quota_interview_prep: int = 3
    llm_monthly_quota_ats_prefill: int = 10

    @property
    def llm_monthly_quotas(self) -> dict[str, int]:
        return {
            "diagnostic": self.llm_monthly_quota_diagnostic,
            "cv": self.llm_monthly_quota_cv,
            "lettre": self.llm_monthly_quota_lettre,
            "compatibility": self.llm_monthly_quota_compatibility,
            "interview_prep": self.llm_monthly_quota_interview_prep,
            "ats_prefill": self.llm_monthly_quota_ats_prefill,
        }
```

- [ ] **Step 2 : Tests qui échouent**

Ajouter à `backend/tests/rate_limit/test_llm_quota.py` :

```python
import pytest

from app.models.llm_call_log import LlmCallLog
from app.rate_limit.llm_quota import (
    QuotaExceeded,
    enforce_monthly_quota,
    monthly_limit,
    record_llm_call,
    usage_summary,
    used_this_month,
)
from app.utils.time import utcnow


def _user(db, **kw):
    u = User(email="u@e.com", hashed_password="x", **kw)
    db.add(u)
    db.commit()
    return u


def test_default_limit_and_override(db_session):
    u = _user(db_session, quota_overrides={"cv": 20})
    assert monthly_limit(u, "cv") == 20
    assert monthly_limit(u, "diagnostic") == 7  # default from settings


def test_enforce_raises_at_limit(db_session):
    u = _user(db_session)
    for _ in range(7):
        record_llm_call(db_session, user_id=u.id, feature="diagnostic")
    assert used_this_month(db_session, u.id, "diagnostic") == 7
    with pytest.raises(QuotaExceeded) as ei:
        enforce_monthly_quota(db_session, u, "diagnostic")
    assert ei.value.feature == "diagnostic" and ei.value.limit == 7
    assert "réinitialise" in ei.value.as_dict()["message"]


def test_last_month_calls_do_not_count(db_session):
    u = _user(db_session)
    old = LlmCallLog(user_id=u.id, feature="cv")
    db_session.add(old)
    db_session.flush()
    old.created_at = utcnow().replace(day=1) - __import__("datetime").timedelta(days=2)
    db_session.commit()
    assert used_this_month(db_session, u.id, "cv") == 0


def test_usage_summary_shape(db_session):
    u = _user(db_session)
    record_llm_call(db_session, user_id=u.id, feature="cv")
    summary = {row["feature"]: row for row in usage_summary(db_session, u)}
    assert summary["cv"]["used"] == 1 and summary["cv"]["limit"] == 5
    assert set(summary) == {"diagnostic", "cv", "lettre", "compatibility",
                            "interview_prep", "ats_prefill"}
```

- [ ] **Step 3 : Vérifier l'échec** — FAIL (module absent).

- [ ] **Step 4 : Implémenter `llm_quota.py`**

```python
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.llm_call_log import LlmCallLog
from app.models.user import User
from app.utils.time import utcnow

FEATURES = ("diagnostic", "cv", "lettre", "compatibility", "interview_prep", "ats_prefill")
FEATURE_LABELS = {
    "diagnostic": "diagnostics",
    "cv": "CV générés",
    "lettre": "lettres de motivation",
    "compatibility": "analyses de compatibilité",
    "interview_prep": "préparations d'entretien",
    "ats_prefill": "préremplissages de formulaire",
}


def _month_start() -> datetime:
    now = utcnow()
    return datetime(now.year, now.month, 1)


def _next_month_start_date() -> date:
    d = _month_start().date()
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


class QuotaExceeded(Exception):
    def __init__(self, feature: str, limit: int, reset_date: str) -> None:
        self.feature = feature
        self.limit = limit
        self.reset_date = reset_date
        super().__init__(f"quota exceeded for {feature}")

    def as_dict(self) -> dict:
        label = FEATURE_LABELS.get(self.feature, self.feature)
        return {
            "code": "quota_exceeded",
            "feature": self.feature,
            "limit": self.limit,
            "reset_date": self.reset_date,
            "message": (
                f"Tu as atteint ta limite beta de {self.limit} {label} ce mois-ci. "
                f"Elle se réinitialise le {self.reset_date}."
            ),
        }


def monthly_limit(user: User, feature: str) -> int:
    if user.quota_overrides and feature in user.quota_overrides:
        return int(user.quota_overrides[feature])
    return get_settings().llm_monthly_quotas[feature]


def used_this_month(db: Session, user_id: int, feature: str) -> int:
    return db.scalar(
        select(func.count())
        .select_from(LlmCallLog)
        .where(
            LlmCallLog.user_id == user_id,
            LlmCallLog.feature == feature,
            LlmCallLog.created_at >= _month_start(),
        )
    ) or 0


def enforce_monthly_quota(db: Session, user: User, feature: str) -> None:
    if used_this_month(db, user.id, feature) >= monthly_limit(user, feature):
        raise QuotaExceeded(feature, monthly_limit(user, feature),
                            _next_month_start_date().isoformat())


def record_llm_call(db: Session, *, user_id: int, feature: str, model: str | None = None,
                    input_tokens: int | None = None, output_tokens: int | None = None) -> None:
    db.add(LlmCallLog(user_id=user_id, feature=feature, model=model,
                      input_tokens=input_tokens, output_tokens=output_tokens))
    db.commit()


def usage_summary(db: Session, user: User) -> list[dict]:
    reset = _next_month_start_date().isoformat()
    return [
        {
            "feature": f,
            "label": FEATURE_LABELS[f],
            "used": used_this_month(db, user.id, f),
            "limit": monthly_limit(user, f),
            "reset_date": reset,
        }
        for f in FEATURES
    ]
```

- [ ] **Step 5 : Vérifier** — `pytest tests/rate_limit/test_llm_quota.py -v` PASS ; `ruff check app/rate_limit/llm_quota.py`.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/rate_limit/llm_quota.py backend/app/config.py backend/tests/rate_limit/test_llm_quota.py
git commit -m "feat(llm): monthly per-feature quota enforcement + usage summary"
```

---

## Task 5 : Interrupteur global (`AppSetting` + `require_llm_enabled`)

**Files:**
- Create: `backend/app/models/app_setting.py`, `backend/app/llm/switch.py`, `backend/app/llm/dependencies.py`, `backend/scripts/llm_switch.py`, `backend/alembic/versions/<rev>_add_app_setting.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/llm/test_switch.py`

**Interfaces:**
- Produces:
  - `AppSetting` — `key: str(64)` (PK), `value: str(255)`, `updated_at: datetime`.
  - `app.llm.switch.llm_features_enabled(db) -> bool` — si la ligne `app_setting["llm_features_enabled"]` existe → `value == "true"` ; sinon `settings.llm_features_enabled`.
  - `app.llm.switch.set_llm_features_enabled(db, enabled: bool) -> None` — upsert + commit.
  - `app.llm.dependencies.require_llm_enabled(db: Session = Depends(get_db)) -> None` — lève `HTTPException(503, detail={"code":"llm_paused","message":"Cette fonctionnalité est en pause (capacité beta). Réessaie plus tard."})` si désactivé.
  - CLI `python -m scripts.llm_switch {on|off|status}`.

- [ ] **Step 1 : Tests qui échouent**

`backend/tests/llm/test_switch.py` :

```python
import pytest
from fastapi import HTTPException

from app.llm.dependencies import require_llm_enabled
from app.llm.switch import llm_features_enabled, set_llm_features_enabled


def test_default_is_enabled(db_session):
    assert llm_features_enabled(db_session) is True


def test_db_flag_overrides(db_session):
    set_llm_features_enabled(db_session, False)
    assert llm_features_enabled(db_session) is False
    set_llm_features_enabled(db_session, True)
    assert llm_features_enabled(db_session) is True


def test_dependency_raises_503_when_off(db_session):
    set_llm_features_enabled(db_session, False)
    with pytest.raises(HTTPException) as ei:
        require_llm_enabled(db_session)
    assert ei.value.status_code == 503
    assert ei.value.detail["code"] == "llm_paused"
```

- [ ] **Step 2 : Vérifier l'échec** — FAIL.

- [ ] **Step 3 : Modèle + migration** (`app_setting`, PK `key`).

- [ ] **Step 4 : `switch.py`**

```python
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.app_setting import AppSetting
from app.utils.time import utcnow

_KEY = "llm_features_enabled"


def llm_features_enabled(db: Session) -> bool:
    row = db.get(AppSetting, _KEY)
    if row is not None:
        return row.value == "true"
    return get_settings().llm_features_enabled


def set_llm_features_enabled(db: Session, enabled: bool) -> None:
    row = db.get(AppSetting, _KEY)
    if row is None:
        row = AppSetting(key=_KEY, value="true" if enabled else "false", updated_at=utcnow())
        db.add(row)
    else:
        row.value = "true" if enabled else "false"
        row.updated_at = utcnow()
    db.commit()
```

- [ ] **Step 5 : `dependencies.py`**

```python
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.switch import llm_features_enabled


def require_llm_enabled(db: Session = Depends(get_db)) -> None:
    if not llm_features_enabled(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "llm_paused",
                "message": "Cette fonctionnalité est en pause (capacité beta). Réessaie plus tard.",
            },
        )
```

- [ ] **Step 6 : `scripts/llm_switch.py`**

```python
"""Toggle all LLM features. docker compose ... exec backend python -m scripts.llm_switch off"""
import sys

from app.database import SessionLocal
from app.llm.switch import llm_features_enabled, set_llm_features_enabled


def _main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    db = SessionLocal()
    try:
        if cmd == "on":
            set_llm_features_enabled(db, True)
        elif cmd == "off":
            set_llm_features_enabled(db, False)
        print("LLM features:", "ON" if llm_features_enabled(db) else "OFF")
    finally:
        db.close()


if __name__ == "__main__":
    _main()
```

- [ ] **Step 7 : Vérifier** — `pytest tests/llm/ -v` PASS.

- [ ] **Step 8 : Commit**

```bash
git add backend/app/models/app_setting.py backend/app/llm/switch.py backend/app/llm/dependencies.py backend/scripts/llm_switch.py backend/app/models/__init__.py backend/alembic/versions/*_add_app_setting.py backend/tests/llm/test_switch.py
git commit -m "feat(llm): global kill-switch (app_setting flag + require_llm_enabled dependency)"
```

---

## Task 6 : Câbler les endpoints LLM synchrones (diagnostic, compatibility, ats_prefill)

**Files:**
- Modify: `backend/app/routers/diagnostics.py`, `backend/app/routers/job_search.py`, `backend/app/routers/applications.py`
- Test: `backend/tests/routers/test_llm_quota_wiring.py`

**Interfaces:**
- Consumes: `require_llm_enabled` (Task 5), `enforce_monthly_quota` / `record_llm_call` / `QuotaExceeded` (Task 4), `capture_usage` / `collected` (Task 2).
- Produces: chaque endpoint renvoie `503 {code:"llm_paused"}` si l'interrupteur est off, `429 {code:"quota_exceeded",...}` si le quota mensuel est atteint, et écrit **une** ligne `llm_call_log` par appel réussi.

Motif commun à appliquer dans chaque endpoint :

```python
# dans la signature :
    _llm: None = Depends(require_llm_enabled),

# juste après le bloc `check_*_rate_limit` existant :
    try:
        enforce_monthly_quota(db, current_user, "<feature>")
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.as_dict()
        ) from exc

# autour de l'appel analyzer, et à l'endroit du log existant :
    with capture_usage():
        <appel analyzer existant>
    model, itok, otok = collected()
    record_llm_call(db, user_id=current_user.id, feature="<feature>",
                    model=model, input_tokens=itok, output_tokens=otok)
```

- [ ] **Step 1 : Tests qui échouent**

`backend/tests/routers/test_llm_quota_wiring.py` — se servir des mocks d'analyzer déjà utilisés dans `tests/routers/test_diagnostics.py` (les copier/adapter). Exemple pour le diagnostic :

```python
import pytest

from app.llm.switch import set_llm_features_enabled
from app.models.llm_call_log import LlmCallLog
# + les helpers d'auth/fixtures de tests/routers/test_auth.py (invite_code, _register)
# + le mock SemanticAnalyzer de tests/routers/test_diagnostics.py


def test_diagnostic_writes_one_llm_call_log(client, db_session, authed_user, mock_semantic_analyzer):
    _post_a_diagnostic(client)  # helper local, comme dans test_diagnostics.py
    rows = db_session.query(LlmCallLog).filter_by(feature="diagnostic").all()
    assert len(rows) == 1


def test_diagnostic_429_when_monthly_quota_reached(client, db_session, authed_user, mock_semantic_analyzer, monkeypatch):
    monkeypatch.setenv("LLM_MONTHLY_QUOTA_DIAGNOSTIC", "1")
    get_settings.cache_clear()  # from app.config
    _post_a_diagnostic(client)
    resp = _post_a_diagnostic(client)
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "quota_exceeded"


def test_diagnostic_503_when_llm_disabled(client, db_session, authed_user, mock_semantic_analyzer):
    set_llm_features_enabled(db_session, False)
    resp = _post_a_diagnostic(client)
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "llm_paused"
```

(Adapter aux fixtures réelles du repo. Faire au moins : 1 test `writes one log` + 1 test `429 quota` + 1 test `503 switch` par endpoint synchrone.)

- [ ] **Step 2 : Vérifier l'échec** — FAIL (pas encore câblé).

- [ ] **Step 3 : `diagnostics.py`**

- Ajouter `_llm: None = Depends(require_llm_enabled)` à `create_diagnostic`.
- Après le `except RateLimitExceeded`, ajouter le bloc `enforce_monthly_quota(db, current_user, "diagnostic")`.
- Envelopper `semantic = analyzer.analyze(...)` (ligne ~114) dans `with capture_usage():`.
- Après `db.add(diagnostic)` (ligne ~146) et avant `db.commit()` : `model, itok, otok = collected(); record_llm_call(db, user_id=current_user.id, feature="diagnostic", model=model, input_tokens=itok, output_tokens=otok)` — attention : `record_llm_call` fait un `db.commit()` ; ici le `db.commit()` suivant du endpoint devient redondant mais inoffensif. **Alternative propre** : insérer la ligne `LlmCallLog` via `db.add(...)` sans commit ici (le `db.commit()` du endpoint la persiste). → Pour cet endpoint, remplacer l'appel par `db.add(LlmCallLog(user_id=..., feature="diagnostic", model=model, input_tokens=itok, output_tokens=otok))` avant le `db.commit()` existant. Documenter ce choix dans un commentaire.

- [ ] **Step 4 : `job_search.py` (`compatibility-detail`)**

- `_llm: None = Depends(require_llm_enabled)`.
- `enforce_monthly_quota(db, current_user, "compatibility")` après le `except RateLimitExceeded`.
- `with capture_usage():` autour de `detail = analyzer.analyze(...)`.
- Là où `db.add(CompatibilityRequestLog(user_id=current_user.id))` puis `db.commit()` : ajouter juste avant le commit `model, itok, otok = collected(); db.add(LlmCallLog(user_id=current_user.id, feature="compatibility", model=model, input_tokens=itok, output_tokens=otok))`.

- [ ] **Step 5 : `applications.py` (`get_prefilled_form`)**

- `_llm: None = Depends(require_llm_enabled)`.
- `enforce_monthly_quota(db, current_user, "ats_prefill")` après le `except RateLimitExceeded`.
- `with capture_usage():` autour de `answers = custom_field_answerer.answer(...)` (garder le `except CustomFieldAnsweringError: answers = {}`).
- Avant le `db.commit()` qui suit `db.add(PrefilledFormRequestLog(...))` : ajouter `model, itok, otok = collected(); db.add(LlmCallLog(user_id=current_user.id, feature="ats_prefill", model=model, input_tokens=itok, output_tokens=otok))`.

- [ ] **Step 6 : Vérifier**

Run: `cd backend && pytest tests/routers/ tests/rate_limit/ tests/llm/ -q && ruff check app/ && mypy app`
Expected: PASS + lint/mypy OK.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/routers/diagnostics.py backend/app/routers/job_search.py backend/app/routers/applications.py backend/tests/routers/test_llm_quota_wiring.py
git commit -m "feat(llm): enforce kill-switch + monthly quota + log calls on sync LLM endpoints"
```

---

## Task 7 : Câbler les endpoints LLM asynchrones (cv, lettre, interview_prep)

**Files:**
- Modify: `backend/app/routers/personalization.py`, `backend/app/routers/interview_prep.py`, `backend/app/personalization/jobs.py`, `backend/app/interview_prep/jobs.py`
- Test: `backend/tests/routers/test_llm_quota_wiring.py` (compléter), `backend/tests/**` jobs existants

**Interfaces:**
- Le **check** (`require_llm_enabled` + `enforce_monthly_quota`) reste **synchrone dans le router**, avant le `db.commit()` qui précède `background_tasks.add_task(...)` (ne pas déplacer ce commit — deadlock connu).
- Le **`record_llm_call`** se fait **dans la fonction de job**, à côté du `db.add(PersonalizationRequestLog(...))` / `db.add(InterviewPrepRequestLog(...))` existant, avec `capture_usage()` autour des appels du job.

- [ ] **Step 1 : Tests qui échouent** — ajouter à `test_llm_quota_wiring.py` :
  - `generate_cv` renvoie `503` si interrupteur off ; `429 {code:quota_exceeded}` si quota `cv` atteint (mettre `LLM_MONTHLY_QUOTA_CV=1`, lancer 1 job jusqu'au bout via le polling de `tests/routers/test_generation_jobs.py`, relancer).
  - après un job CV réussi : exactement 1 ligne `llm_call_log` `feature="cv"`.
  - idem `interview_prep`.

- [ ] **Step 2 : Vérifier l'échec** — FAIL.

- [ ] **Step 3 : `personalization.py`**

Dans `generate_cv` **et** `generate_lettre` :
- `_llm: None = Depends(require_llm_enabled)` dans la signature.
- après le `except RateLimitExceeded` (avant `diagnostic = _get_owned_diagnostic(...)`), ajouter `enforce_monthly_quota(db, current_user, "cv")` (resp. `"lettre"`).

- [ ] **Step 4 : `personalization/jobs.py`**

Dans `run_cv_generation_job` : envelopper la section qui appelle `rewriter` + `analyzer` dans `with capture_usage():`. À l'endroit de `db.add(PersonalizationRequestLog(user_id=user_id))` (ligne ~178), ajouter avant le `db.commit()` :

```python
model, itok, otok = collected()
db.add(LlmCallLog(user_id=user_id, feature="cv", model=model,
                  input_tokens=itok, output_tokens=otok))
```

Dans `run_letter_generation_job` : idem, `feature="lettre"` (ligne ~270).

- [ ] **Step 5 : `interview_prep.py` + `interview_prep/jobs.py`**

- Router `start_interview_prep` : `_llm: None = Depends(require_llm_enabled)` + `enforce_monthly_quota(db, current_user, "interview_prep")` après le `except RateLimitExceeded`, avant `db.commit()`.
- Job `run_interview_prep_job` : `with capture_usage():` autour de `analyzer.draft_dossier(...)` (et de la phase web-search si elle passe par `analyzer`) ; à côté de `db.add(InterviewPrepRequestLog(user_id=user_id))` (ligne ~148), ajouter `model, itok, otok = collected(); db.add(LlmCallLog(user_id=user_id, feature="interview_prep", model=model, input_tokens=itok, output_tokens=otok))`.

- [ ] **Step 6 : Vérifier**

Run: `cd backend && pytest -q && ruff check app/ && ruff format --check app/ && mypy app`
Expected: suite complète verte.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/routers/personalization.py backend/app/routers/interview_prep.py backend/app/personalization/jobs.py backend/app/interview_prep/jobs.py backend/tests/routers/test_llm_quota_wiring.py
git commit -m "feat(llm): enforce kill-switch + monthly quota + log calls on async generation jobs"
```

---

## Task 8 : `GET /auth/me/usage`

**Files:**
- Modify: `backend/app/routers/auth.py`, `backend/app/schemas/auth.py`
- Test: `backend/tests/routers/test_auth.py` (ajouter)

**Interfaces:**
- Produces: `GET /auth/me/usage` (authentifié) → `list[UsageItemOut]` où `UsageItemOut = {feature: str, label: str, used: int, limit: int, reset_date: str}`.

- [ ] **Step 1 : Test qui échoue**

```python
def test_me_usage_lists_all_features(client, invite_code):
    _register(client, invite_code)
    token = client.post("/auth/login", data={"username": "jane@example.com", "password": "s3cret!1"}).json()["access_token"]
    resp = client.get("/auth/me/usage", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    features = {item["feature"] for item in resp.json()}
    assert features == {"diagnostic", "cv", "lettre", "compatibility", "interview_prep", "ats_prefill"}
    assert all(item["used"] == 0 for item in resp.json())
```

- [ ] **Step 2 : Vérifier l'échec** — 404.

- [ ] **Step 3 : Implémenter**

`schemas/auth.py` : `class UsageItemOut(BaseModel): feature: str; label: str; used: int; limit: int; reset_date: str`.

`routers/auth.py` :

```python
@router.get("/me/usage", response_model=list[UsageItemOut])
def me_usage(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return usage_summary(db, current_user)
```

- [ ] **Step 4 : Vérifier** — `pytest tests/routers/test_auth.py -v` PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/routers/auth.py backend/app/schemas/auth.py backend/tests/routers/test_auth.py
git commit -m "feat(llm): GET /auth/me/usage exposes monthly quota consumption"
```

---

## Task 9 : Frontend — jauges d'utilisation + encart quota

**Files:**
- Modify: `frontend/lib/api.ts`, `frontend/lib/types.ts`, `frontend/app/(app)/profil/page.tsx`
- Create: `frontend/components/account/UsageGauges.tsx`
- Modify: composants d'affichage d'erreur de génération (au moins : le composant qui affiche l'erreur d'un `useGenerationJob`, et la page `diagnostic`).

**Interfaces:**
- Consumes: `GET /auth/me/usage`, erreurs `429 {detail:{code:"quota_exceeded",message,...}}` et `503 {detail:{code:"llm_paused",message}}`.
- Produces:
  - `api.getUsage(token): Promise<UsageItem[]>` (`UsageItem = {feature,label,used,limit,reset_date}`).
  - `ApiError` porte un champ `code?: string` (extrait de `body.detail.code` quand `detail` est un objet).
  - `<UsageGauges />` — liste les 6 features avec une barre `used/limit` et la date de reset.

- [ ] **Step 1 : `lib/api.ts` — gérer un `detail` objet**

Dans `request()`, remplacer l'extraction du détail :

```ts
let detail = `Erreur ${res.status}`;
let code: string | undefined;
try {
  const body = await res.json();
  if (body && typeof body.detail === "object" && body.detail !== null) {
    detail = body.detail.message ?? detail;
    code = body.detail.code;
  } else {
    detail = body.detail ?? detail;
  }
} catch { /* ignore */ }
handleResponseError(res.status, detail, code);
```

`ApiError` gagne `code?: string` ; `handleResponseError(status, detail, code?)` le passe au constructeur.

- [ ] **Step 2 : `api.getUsage` + type**

```ts
export async function getUsage(token: string): Promise<UsageItem[]> {
  return request<UsageItem[]>("/auth/me/usage", {}, token);
}
```

`lib/types.ts` : `export interface UsageItem { feature: string; label: string; used: number; limit: number; reset_date: string; }`.

- [ ] **Step 3 : `<UsageGauges />`**

Composant client : `useAuth()` pour le token, charge `getUsage`, rend une carte par item :

```tsx
<div>
  <p>{item.label}</p>
  <div className="h-2 bg-muted rounded-full overflow-hidden">
    <div className="h-full bg-primary-500 rounded-full"
         style={{ width: `${Math.min(100, (item.used / item.limit) * 100)}%` }} />
  </div>
  <p className="text-xs text-muted-foreground">
    {item.used} / {item.limit} · réinitialisation le {item.reset_date}
  </p>
</div>
```

Titre de section : « Ton utilisation ce mois-ci (beta) ».

- [ ] **Step 4 : Insérer dans `/profil`**

Ajouter `<UsageGauges />` dans une nouvelle section de `app/(app)/profil/page.tsx`.

- [ ] **Step 5 : Encart quota/pause dans l'affichage d'erreur**

Là où une erreur de génération est rendue (diagnostic, CV, lettre, prépa entretien, compatibilité), quand `err instanceof ApiError && (err.code === "quota_exceeded" || err.code === "llm_paused")` : afficher un encart neutre (icône info, pas rouge) avec `err.message`, au lieu du bandeau d'erreur générique. Un petit helper `isQuotaOrPauseError(err)` dans `lib/utils.ts`.

- [ ] **Step 6 : Build + vérif navigateur**

Run: `cd frontend && npm run typecheck && npm run build`
Puis (backend+frontend up) : mettre `LLM_MONTHLY_QUOTA_DIAGNOSTIC=1` dans `backend/.env`, rebuild backend, faire 2 diagnostics → le 2ᵉ montre l'encart « quota atteint » (pas une erreur rouge) ; `python -m scripts.llm_switch off` → une génération montre l'encart « en pause » ; `on` → rétabli ; `/profil` montre les jauges. Console propre.

- [ ] **Step 7 : Commit**

```bash
git add frontend/lib/api.ts frontend/lib/types.ts frontend/lib/utils.ts frontend/components/account/UsageGauges.tsx "frontend/app/(app)/profil/page.tsx" frontend/components/
git commit -m "feat(llm): usage gauges on the profile page + dedicated quota/pause notices"
```

---

## Self-Review

**Couverture du spec §4 :**

| Exigence | Task |
|---|---|
| §4.1 quota mensuel/feature en plus des limites horaires conservées | Tasks 4, 6, 7 (limites horaires non touchées) |
| §4.2 `llm_call_log` unifié, 1 ligne/action, tokens sommés | Tasks 1, 2, 6, 7 |
| §4.2 `record_llm_call` câblé aux 6 sites | Tasks 6 (diagnostic, compatibility, ats_prefill) + 7 (cv, lettre, interview_prep) |
| §4.2 tables de log existantes conservées | oui (rate-limit horaire inchangé) |
| §4.3 `enforce_monthly_quota` avant l'appel, `429 {code:quota_exceeded, reset_date}` | Tasks 4, 6, 7 |
| §4.3 `User.quota_overrides` prioritaire | Task 1 + Task 4 (`monthly_limit`) |
| §4.4 6 clés de config + défauts (7/5/5/13/3/10) | Task 4 Step 1 |
| §4.5 `LLM_FEATURES_ENABLED` env + flag DB `app_setting` + `require_llm_enabled` → `503 {code:llm_paused}` ; précédence DB | Task 5 |
| §4.5 bascule sans redémarrage (CLI + endpoint admin) | Task 5 (`scripts/llm_switch.py`) ; endpoint admin en Beta 6 |
| §4.6 plafond console Anthropic | hors code — RUNBOOK (Beta 1 §5 + note ici) |
| §4.7 encart « quota atteint », jauge `/me/usage` | Tasks 8, 9 |
| §4.8 pas de changement de modèle | respecté (Task 3 ne fait que proxifier) |

**Placeholders :** aucun `TBD`/`TODO`. Les migrations Tasks 5 disent « calqué » mais donnent PK/colonnes exactes dans Interfaces.

**Cohérence des noms :** `capture_usage` / `collected` / `_note`, `build_anthropic_client` / `UsageRecordingAnthropic`, `LlmCallLog` (table `llm_call_logs`), `AppSetting` (table `app_setting` — **attention : nom de table au singulier ici, pluriel pour les logs — garder ce choix**), `enforce_monthly_quota` / `record_llm_call` / `monthly_limit` / `used_this_month` / `usage_summary` / `QuotaExceeded.as_dict()`, `llm_features_enabled` / `set_llm_features_enabled` / `require_llm_enabled`, features `diagnostic|cv|lettre|compatibility|interview_prep|ats_prefill`, codes d'erreur `quota_exceeded` / `llm_paused`. Identiques entre tasks.

**Décision d'implémentation notée :** pour les endpoints **synchrones** (Task 6), écrire la ligne `LlmCallLog` via `db.add(...)` **sans `commit` propre** (le `db.commit()` du endpoint la persiste), pour ne pas multiplier les commits ni interférer avec la transaction. `record_llm_call` (avec commit) est réservé aux **jobs de fond** (Task 7) où c'est le motif existant de `*RequestLog`.

**Ordre d'exécution :** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9.

**Dépendance vers Beta 6 :** l'endpoint `POST /admin/llm-toggle` et l'UI de bascule sont dans Beta 6 ; Beta 3 est autonome grâce à `scripts/llm_switch.py`.
