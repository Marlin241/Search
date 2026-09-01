# Beta — Plan 2 : Durcissement de l'authentification & de l'accès — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fermer l'inscription par codes d'invitation nominatifs, recueillir le consentement, durcir le cookie de session et le CORS, limiter le bruteforce sur `/auth/*`, et ajouter un flux minimal de réinitialisation de mot de passe.

**Architecture:** Trois nouvelles tables append-only/état (`invite_code`, `auth_attempt`, `password_reset_token`) + deux colonnes de consentement sur `users`. `POST /auth/register` exige désormais un `invite_code` valide et `accept_terms=true`, dans une seule transaction verrouillée sur la ligne du code. Un module `app/rate_limit/auth_throttle.py` (DB-backed, comme les limiters existants) compte les tentatives par (action, identifiant, fenêtre). La réinitialisation passe par un token à usage unique (SHA-256 stocké) envoyé par email via le client Resend existant. Côté frontend : champ code + case de consentement à l'inscription, pages `/mot-de-passe-oublie` et `/reset-password`, et le cookie `search_app_token` devient `Secure` (+ `HttpOnly` posé par un route handler Next).

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, `secrets`, `hashlib`, bcrypt (déjà là), Resend (déjà câblé), Next 16 (App Router), pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-lancement-beta-design.md` — §3 en entier (3.1 codes d'invitation, 3.2 consentement, 3.3 cookie & CORS, 3.4 throttle, 3.5 reset mot de passe, 3.6 JWT).

## Global Constraints

- **Branche** `feature/beta-launch`, jamais `main`. Commits scopés (`git add <chemins>`), jamais `git add -A`.
- **Migrations Alembic additives uniquement** : nouvelles tables, colonnes **nullable** (rollback = code only, cf. Beta 1). `down_revision` = la migration précédente (`git log` / `alembic heads` pour la tête courante — au moment d'écrire, `aa7c6563c94a`, à revérifier).
- **Datetimes naïfs UTC** : `datetime.utcnow` en `default=` de colonne, `app.utils.time.utcnow()` dans le code, comme tout le projet. `tests/**` ignore `DTZ001` (déjà configuré).
- **Un modèle = un fichier** dans `app/models/`, importé dans `app/models/__init__.py` (+ `__all__`).
- **Le backend ne fait confiance qu'au header `Authorization: Bearer`** — le cookie `search_app_token` reste un simple miroir pour le garde `proxy.ts`. Ne pas introduire d'auth par cookie côté backend.
- **`requirements.txt`** : aucune nouvelle dépendance (tout est en stdlib ou déjà présent).
- **Après modif backend testée en réel** : `docker compose -f docker-compose.prod.yml up -d --build backend` (ou le compose de dev en local) + `docker logs search-backend-1`.
- **Messages d'erreur en français** (comme l'existant : « Cet email est déjà utilisé. », etc.).
- **Nommage** : `feature`/action de throttle ∈ `login | register | forgot_password`.

---

## File Structure

**Créés :**
- `backend/app/models/invite_code.py` — `InviteCode`.
- `backend/app/models/auth_attempt.py` — `AuthAttempt` (log de tentatives pour le throttle).
- `backend/app/models/password_reset_token.py` — `PasswordResetToken`.
- `backend/app/rate_limit/auth_throttle.py` — comptage des tentatives + `AuthThrottleExceeded`.
- `backend/app/auth/invites.py` — validation/consommation d'un code (`redeem_invite_code`).
- `backend/app/auth/consent.py` — `CURRENT_TERMS_VERSION` + helper.
- `backend/app/auth/password_reset.py` — création/vérification de token (hash, expiration, usage unique).
- `backend/app/auth/http.py` — `client_ip(request)` (parse `X-Forwarded-For`).
- `backend/scripts/__init__.py` (si absent) + `backend/scripts/invites.py` — CLI de gestion des codes.
- `backend/alembic/versions/<rev>_add_invite_code.py`
- `backend/alembic/versions/<rev>_add_user_consent_columns.py`
- `backend/alembic/versions/<rev>_add_auth_attempt.py`
- `backend/alembic/versions/<rev>_add_password_reset_token.py`
- `backend/tests/auth/test_invites.py`
- `backend/tests/auth/test_auth_throttle.py`
- `backend/tests/auth/test_password_reset.py`
- `backend/tests/routers/test_auth_password_reset.py`
- `frontend/app/api/session/route.ts` — pose/supprime le cookie `HttpOnly` côté serveur.
- `frontend/app/(auth)/mot-de-passe-oublie/page.tsx`
- `frontend/app/(auth)/reset-password/page.tsx`

**Modifiés :**
- `backend/app/models/user.py` — colonnes `consent_accepted_at`, `consent_version` ; relation `invite_code` inverse (optionnelle).
- `backend/app/schemas/auth.py` — `UserCreate` gagne `invite_code`, `accept_terms` ; nouveaux schémas `ForgotPasswordIn`, `ResetPasswordIn`.
- `backend/app/routers/auth.py` — `register` (code + consentement + throttle), `login` (throttle), nouveaux endpoints `forgot-password` / `reset-password`.
- `backend/app/notifications/resend_client.py` — `send_password_reset_email(to_email, reset_url)`.
- `backend/app/config.py` — `environment: str = "development"`, `password_reset_token_ttl_minutes: int = 60`.
- `backend/app/main.py` — le CORS lit déjà `settings.cors_origins` ; rien à changer côté code (valeur via `.env`, cf. Beta 1). Ajouter juste un commentaire.
- `backend/tests/routers/test_auth.py` — tous les `POST /auth/register` existants passent maintenant par un code + `accept_terms` (fixture `invite_code`).
- `frontend/context/AuthContext.tsx` — `register(email, password, inviteCode)` ; cookie via le route handler ; `Secure` en prod.
- `frontend/lib/api.ts` — `register` signature + `forgotPassword`, `resetPassword`.
- `frontend/app/(auth)/login/page.tsx` — champ code d'invitation + case consentement (mode inscription) + lien « Mot de passe oublié ? ».
- `frontend/proxy.ts` — ajouter `/mot-de-passe-oublie` et `/reset-password` à `AUTH_PATHS` (redirigent vers `/dashboard` si déjà connecté) ; les laisser hors des préfixes protégés.

**Non modifiés (volontairement) :** `app/auth/security.py` (le JWT 24 h reste), `app/auth/dependencies.py`.

---

## Task 1 : Modèle `InviteCode` + migration

**Files:**
- Create: `backend/app/models/invite_code.py`, `backend/alembic/versions/<rev>_add_invite_code.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/auth/test_invites.py` (créé ici, complété Task 3)

**Interfaces:**
- Produces: `InviteCode` — colonnes `id`, `code: str(32) unique index`, `note: str(255) | None`, `created_at: datetime`, `expires_at: datetime | None`, `used_by_user_id: int | None` (FK `users.id`, `ondelete="SET NULL"`), `used_at: datetime | None`.

- [ ] **Step 1 : Écrire le test qui échoue**

`backend/tests/auth/test_invites.py` :

```python
from datetime import timedelta

from app.models.invite_code import InviteCode
from app.utils.time import utcnow


def test_invite_code_row_roundtrips(db_session):
    code = InviteCode(code="abc123", note="pour Awa", expires_at=utcnow() + timedelta(days=30))
    db_session.add(code)
    db_session.commit()
    fetched = db_session.query(InviteCode).filter_by(code="abc123").one()
    assert fetched.used_by_user_id is None
    assert fetched.used_at is None
    assert fetched.note == "pour Awa"
```

- [ ] **Step 2 : Vérifier l'échec**

Run: `cd backend && pytest tests/auth/test_invites.py -v`
Expected: FAIL (`ModuleNotFoundError: app.models.invite_code`).

- [ ] **Step 3 : Écrire le modèle**

`backend/app/models/invite_code.py` :

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InviteCode(Base):
    """One-time, nominative registration code. Consumed atomically by
    app.auth.invites.redeem_invite_code inside the /auth/register txn."""

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4 : Enregistrer le modèle**

Dans `backend/app/models/__init__.py` : ajouter l'import `from app.models.invite_code import InviteCode` (ordre alphabétique, après `interview_prep_request_log`) et `"InviteCode"` dans `__all__`.

- [ ] **Step 5 : Générer la migration**

Run: `cd backend && alembic revision -m "add invite_code"`
Puis remplir `upgrade()` / `downgrade()` (calqué sur `aa7c6563c94a_add_crawled_listing.py`) :

```python
def upgrade() -> None:
    op.create_table(
        "invite_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("used_by_user_id", sa.Integer(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["used_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_invite_codes_code", "invite_codes", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invite_codes_code", table_name="invite_codes")
    op.drop_table("invite_codes")
```

Mettre `down_revision` à la tête courante (`alembic heads`).

- [ ] **Step 6 : Vérifier le test + la migration**

Run: `cd backend && pytest tests/auth/test_invites.py -v && alembic upgrade head --sql >/dev/null && echo "migration OK"`
Expected: PASS + « migration OK ».

- [ ] **Step 7 : Commit**

```bash
git add backend/app/models/invite_code.py backend/app/models/__init__.py backend/alembic/versions/*_add_invite_code.py backend/tests/auth/test_invites.py
git commit -m "feat(auth): InviteCode model + migration"
```

---

## Task 2 : CLI `scripts/invites.py`

**Files:**
- Create: `backend/scripts/__init__.py` (si absent), `backend/scripts/invites.py`
- Test: `backend/tests/auth/test_invites.py` (ajouter)

**Interfaces:**
- Consumes: `InviteCode`, `app.database.SessionLocal`.
- Produces:
  - `generate_codes(db, count: int, note: str | None, ttl_days: int = 30) -> list[str]` — insère `count` codes (`secrets.token_urlsafe(9)`), renvoie les chaînes.
  - `list_codes(db) -> list[InviteCode]`.
  - `revoke_code(db, code: str) -> bool` — supprime un code **non utilisé** ; `False` s'il est déjà consommé ou inconnu.
  - CLI : `python -m scripts.invites generate --count N [--note "..."]` | `list` | `revoke <code>`.

- [ ] **Step 1 : Test qui échoue**

Ajouter à `backend/tests/auth/test_invites.py` :

```python
from scripts.invites import generate_codes, list_codes, revoke_code


def test_generate_codes_creates_unique_unused_codes(db_session):
    codes = generate_codes(db_session, count=3, note="batch 1")
    assert len(codes) == 3 == len(set(codes))
    rows = list_codes(db_session)
    assert {r.code for r in rows} == set(codes)
    assert all(r.used_at is None and r.note == "batch 1" for r in rows)


def test_revoke_unused_code_succeeds_used_code_fails(db_session):
    (code,) = generate_codes(db_session, count=1, note=None)
    assert revoke_code(db_session, code) is True
    assert revoke_code(db_session, "nope") is False
```

- [ ] **Step 2 : Vérifier l'échec**

Run: `cd backend && pytest tests/auth/test_invites.py -v`
Expected: FAIL (`ModuleNotFoundError: scripts.invites`).

- [ ] **Step 3 : Implémenter**

`backend/scripts/invites.py` :

```python
"""Manage beta invite codes. Run inside the container:
    docker compose -f docker-compose.prod.yml exec backend python -m scripts.invites generate --count 15 --note "vague 1"
"""
import argparse
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.invite_code import InviteCode
from app.utils.time import utcnow


def generate_codes(db: Session, count: int, note: str | None, ttl_days: int = 30) -> list[str]:
    codes: list[str] = []
    for _ in range(count):
        value = secrets.token_urlsafe(9)
        db.add(InviteCode(code=value, note=note, expires_at=utcnow() + timedelta(days=ttl_days)))
        codes.append(value)
    db.commit()
    return codes


def list_codes(db: Session) -> list[InviteCode]:
    return db.query(InviteCode).order_by(InviteCode.created_at).all()


def revoke_code(db: Session, code: str) -> bool:
    row = db.query(InviteCode).filter_by(code=code).one_or_none()
    if row is None or row.used_at is not None:
        return False
    db.delete(row)
    db.commit()
    return True


def _main() -> None:
    parser = argparse.ArgumentParser(prog="scripts.invites")
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--count", type=int, required=True)
    g.add_argument("--note", default=None)
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("code")

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.cmd == "generate":
            for c in generate_codes(db, args.count, args.note):
                print(c)
        elif args.cmd == "list":
            for row in list_codes(db):
                status = f"used by user {row.used_by_user_id}" if row.used_at else "unused"
                print(f"{row.code}\t{status}\t{row.note or ''}")
        elif args.cmd == "revoke":
            print("revoked" if revoke_code(db, args.code) else "not revocable (unknown or already used)")
    finally:
        db.close()


if __name__ == "__main__":
    _main()
```

Créer `backend/scripts/__init__.py` (vide) s'il n'existe pas.

- [ ] **Step 4 : Vérifier**

Run: `cd backend && pytest tests/auth/test_invites.py -v`
Expected: PASS (tous).

- [ ] **Step 5 : Commit**

```bash
git add backend/scripts/
git commit -m "feat(auth): scripts.invites CLI (generate/list/revoke)"
```

---

## Task 3 : Inscription — code d'invitation + consentement

**Files:**
- Create: `backend/app/auth/invites.py`, `backend/app/auth/consent.py`
- Modify: `backend/app/models/user.py`, `backend/app/schemas/auth.py`, `backend/app/routers/auth.py`, `backend/app/config.py`, `backend/tests/routers/test_auth.py`
- Create: `backend/alembic/versions/<rev>_add_user_consent_columns.py`
- Test: `backend/tests/routers/test_auth.py` (mise à jour + ajouts)

**Interfaces:**
- Consumes: `InviteCode` (Task 1).
- Produces:
  - `app.auth.consent.CURRENT_TERMS_VERSION: str` (= `"2026-09"`).
  - `app.auth.invites.redeem_invite_code(db, code: str) -> InviteCode` — `SELECT ... FOR UPDATE` (non-SQLite) sur la ligne ; lève `InviteCodeError` (message FR) si absente / `used_at` non nul / `expires_at` passé. **Ne commit pas** (le fait l'appelant). Renvoie la ligne pour que l'appelant y pose `used_by_user_id` / `used_at`.
  - `UserCreate` : `email: EmailStr`, `password: str [8..72]`, `invite_code: str`, `accept_terms: bool`.
  - `User.consent_accepted_at: datetime | None`, `User.consent_version: str | None`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Dans `backend/tests/routers/test_auth.py`, ajouter en haut une fixture et adapter les appels :

```python
import pytest

from scripts.invites import generate_codes


@pytest.fixture()
def invite_code(db_session):
    (code,) = generate_codes(db_session, count=1, note="test")
    return code


def _register(client, invite_code, email="jane@example.com", password="s3cret!1"):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "invite_code": invite_code,
            "accept_terms": True,
        },
    )
```

Remplacer les `client.post("/auth/register", json={...})` existants par `_register(client, invite_code, ...)` (garder les assertions). Ajouter :

```python
def test_register_without_invite_code_returns_422(client):
    resp = client.post("/auth/register", json={"email": "x@e.com", "password": "s3cret!1", "accept_terms": True})
    assert resp.status_code == 422


def test_register_with_unknown_code_returns_400(client):
    resp = client.post("/auth/register", json={
        "email": "x@e.com", "password": "s3cret!1", "invite_code": "bogus", "accept_terms": True})
    assert resp.status_code == 400


def test_register_without_accept_terms_returns_422(client, invite_code):
    resp = client.post("/auth/register", json={
        "email": "x@e.com", "password": "s3cret!1", "invite_code": invite_code, "accept_terms": False})
    assert resp.status_code == 422


def test_register_consumes_code_and_stamps_consent(client, db_session, invite_code):
    assert _register(client, invite_code).status_code == 201
    from app.models.invite_code import InviteCode
    from app.models.user import User
    row = db_session.query(InviteCode).filter_by(code=invite_code).one()
    assert row.used_at is not None and row.used_by_user_id is not None
    user = db_session.query(User).filter_by(email="jane@example.com").one()
    assert user.consent_version == "2026-09" and user.consent_accepted_at is not None


def test_code_cannot_be_reused(client, invite_code):
    assert _register(client, invite_code, email="a@e.com").status_code == 201
    assert _register(client, invite_code, email="b@e.com").status_code == 400
```

- [ ] **Step 2 : Vérifier l'échec**

Run: `cd backend && pytest tests/routers/test_auth.py -v`
Expected: FAIL (schéma sans `invite_code`, colonnes de consentement absentes, code non consommé).

- [ ] **Step 3 : Colonnes de consentement + migration**

`backend/app/models/user.py` — ajouter après `created_at` :

```python
    consent_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
```

Migration `<rev>_add_user_consent_columns.py` :

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("consent_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("consent_version", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "consent_version")
    op.drop_column("users", "consent_accepted_at")
```

- [ ] **Step 4 : `consent.py` + `invites.py`**

`backend/app/auth/consent.py` :

```python
CURRENT_TERMS_VERSION = "2026-09"
```

`backend/app/auth/invites.py` :

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invite_code import InviteCode
from app.utils.time import utcnow


class InviteCodeError(Exception):
    """Raised when an invite code is unknown, already used, or expired."""


def redeem_invite_code(db: Session, code: str) -> InviteCode:
    query = select(InviteCode).where(InviteCode.code == code)
    if db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    row = db.execute(query).scalar_one_or_none()
    if row is None:
        raise InviteCodeError("Code d'invitation invalide.")
    if row.used_at is not None:
        raise InviteCodeError("Ce code d'invitation a déjà été utilisé.")
    if row.expires_at is not None and row.expires_at < utcnow():
        raise InviteCodeError("Ce code d'invitation a expiré.")
    return row
```

- [ ] **Step 5 : Schéma + router**

`backend/app/schemas/auth.py` — `UserCreate` :

```python
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    invite_code: str = Field(min_length=1)
    accept_terms: bool

    @field_validator("accept_terms")
    @classmethod
    def _must_accept(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Vous devez accepter les conditions.")
        return v
```

(importer `field_validator` depuis `pydantic`.)

`backend/app/routers/auth.py` — `register` :

```python
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
    check_auth_throttle(db, action="register", identifier=client_ip(request))  # Task 4

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet email est déjà utilisé.")

    try:
        code_row = redeem_invite_code(db, payload.invite_code)
    except InviteCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        consent_accepted_at=utcnow(),
        consent_version=CURRENT_TERMS_VERSION,
    )
    db.add(user)
    db.flush()  # user.id
    code_row.used_by_user_id = user.id
    code_row.used_at = utcnow()
    db.commit()
    db.refresh(user)
    return user
```

(La ligne `check_auth_throttle` est neutralisée tant que Task 4 n'est pas faite — commenter puis décommenter ; ou faire Task 4 avant Task 3. **Recommandé : Task 4 avant Task 3.**)

- [ ] **Step 6 : Config**

`backend/app/config.py` — ajouter `environment: str = "development"` (utilisé par Beta 5) — inoffensif ici.

- [ ] **Step 7 : Vérifier toute la suite auth**

Run: `cd backend && pytest tests/routers/test_auth.py tests/auth/ -v && ruff check app/ && ruff format --check app/`
Expected: PASS + lint OK.

- [ ] **Step 8 : Commit**

```bash
git add backend/app/auth/invites.py backend/app/auth/consent.py backend/app/models/user.py backend/app/schemas/auth.py backend/app/routers/auth.py backend/app/config.py backend/alembic/versions/*_add_user_consent_columns.py backend/tests/routers/test_auth.py
git commit -m "feat(auth): registration requires a valid invite code and consent"
```

---

## Task 4 : Throttle bruteforce sur `/auth/*`

**Files:**
- Create: `backend/app/models/auth_attempt.py`, `backend/app/rate_limit/auth_throttle.py`, `backend/app/auth/http.py`, `backend/alembic/versions/<rev>_add_auth_attempt.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/routers/auth.py`
- Test: `backend/tests/auth/test_auth_throttle.py`

**Interfaces:**
- Produces:
  - `AuthAttempt` — `id`, `action: str(32) index`, `identifier: str(255) index`, `created_at: datetime index`.
  - `app.auth.http.client_ip(request: Request) -> str` — premier segment de `X-Forwarded-For`, sinon `request.client.host`, sinon `"unknown"`.
  - `app.rate_limit.auth_throttle.AuthThrottleExceeded(Exception)` (message FR).
  - `record_auth_attempt(db, *, action: str, identifier: str) -> None` — insère + `commit`.
  - `check_auth_throttle(db, *, action: str, identifier: str) -> None` — lève `AuthThrottleExceeded` si le nombre de `AuthAttempt` (même action+identifier) dans la fenêtre dépasse le seuil. Seuils : `login` 8 / 15 min ; `register` 5 / 60 min ; `forgot_password` 5 / 60 min.
  - `clear_auth_attempts(db, *, action: str, identifier: str) -> None` — purge (appelé au succès du login).

- [ ] **Step 1 : Tests qui échouent**

`backend/tests/auth/test_auth_throttle.py` :

```python
import pytest

from app.rate_limit.auth_throttle import (
    AuthThrottleExceeded,
    check_auth_throttle,
    clear_auth_attempts,
    record_auth_attempt,
)


def test_login_allows_up_to_8_then_blocks(db_session):
    for _ in range(8):
        check_auth_throttle(db_session, action="login", identifier="a@e.com|1.2.3.4")
        record_auth_attempt(db_session, action="login", identifier="a@e.com|1.2.3.4")
    with pytest.raises(AuthThrottleExceeded):
        check_auth_throttle(db_session, action="login", identifier="a@e.com|1.2.3.4")


def test_clear_resets_the_counter(db_session):
    for _ in range(8):
        record_auth_attempt(db_session, action="login", identifier="k")
    clear_auth_attempts(db_session, action="login", identifier="k")
    check_auth_throttle(db_session, action="login", identifier="k")  # no raise


def test_separate_identifiers_do_not_interfere(db_session):
    for _ in range(8):
        record_auth_attempt(db_session, action="login", identifier="k1")
    check_auth_throttle(db_session, action="login", identifier="k2")  # no raise
```

- [ ] **Step 2 : Vérifier l'échec** — `pytest tests/auth/test_auth_throttle.py -v` → FAIL (module absent).

- [ ] **Step 3 : Modèle + migration**

`backend/app/models/auth_attempt.py` :

```python
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuthAttempt(Base):
    """Append-only log of auth attempts, used only by
    app.rate_limit.auth_throttle to rate-limit /auth/*."""

    __tablename__ = "auth_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    identifier: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )
```

Migration : `op.create_table("auth_attempts", …)` + 3 index (`action`, `identifier`, `created_at`). Enregistrer dans `__init__.py`.

- [ ] **Step 4 : `client_ip`**

`backend/app/auth/http.py` :

```python
from fastapi import Request


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
```

- [ ] **Step 5 : `auth_throttle.py`**

```python
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth_attempt import AuthAttempt
from app.utils.time import utcnow

_LIMITS = {
    "login": (8, timedelta(minutes=15)),
    "register": (5, timedelta(minutes=60)),
    "forgot_password": (5, timedelta(minutes=60)),
}


class AuthThrottleExceeded(Exception):
    pass


def record_auth_attempt(db: Session, *, action: str, identifier: str) -> None:
    db.add(AuthAttempt(action=action, identifier=identifier))
    db.commit()


def check_auth_throttle(db: Session, *, action: str, identifier: str) -> None:
    max_count, window = _LIMITS[action]
    since = utcnow() - window
    count = db.scalar(
        select(func.count())
        .select_from(AuthAttempt)
        .where(
            AuthAttempt.action == action,
            AuthAttempt.identifier == identifier,
            AuthAttempt.created_at >= since,
        )
    )
    if count is not None and count >= max_count:
        raise AuthThrottleExceeded(
            "Trop de tentatives. Réessaie dans quelques minutes."
        )


def clear_auth_attempts(db: Session, *, action: str, identifier: str) -> None:
    db.query(AuthAttempt).filter_by(action=action, identifier=identifier).delete()
    db.commit()
```

- [ ] **Step 6 : Câbler dans `login` + `register`**

`backend/app/routers/auth.py` — `login` :

```python
@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    identifier = f"{form_data.username.lower()}|{client_ip(request)}"
    try:
        check_auth_throttle(db, action="login", identifier=identifier)
    except AuthThrottleExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))

    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        record_auth_attempt(db, action="login", identifier=identifier)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe incorrect.")

    clear_auth_attempts(db, action="login", identifier=identifier)
    return Token(access_token=create_access_token(subject=user.email))
```

Dans `register` : décommenter/activer `check_auth_throttle(db, action="register", identifier=client_ip(request))` en tête, et `record_auth_attempt(... "register" ...)` juste avant chaque `raise HTTPException` (409 / 400). Convertir `AuthThrottleExceeded` en `429`.

- [ ] **Step 7 : Test d'intégration throttle login**

Ajouter à `tests/routers/test_auth.py` :

```python
def test_login_blocks_after_8_failures(client, invite_code):
    _register(client, invite_code, email="j@e.com")
    for _ in range(8):
        client.post("/auth/login", data={"username": "j@e.com", "password": "wrong"})
    resp = client.post("/auth/login", data={"username": "j@e.com", "password": "wrong"})
    assert resp.status_code == 429
```

- [ ] **Step 8 : Vérifier**

Run: `cd backend && pytest tests/auth/ tests/routers/test_auth.py -v && ruff check app/`
Expected: PASS + lint OK.

- [ ] **Step 9 : Commit**

```bash
git add backend/app/models/auth_attempt.py backend/app/rate_limit/auth_throttle.py backend/app/auth/http.py backend/app/models/__init__.py backend/app/routers/auth.py backend/alembic/versions/*_add_auth_attempt.py backend/tests/auth/test_auth_throttle.py backend/tests/routers/test_auth.py
git commit -m "feat(auth): DB-backed brute-force throttle on /auth/login and /auth/register"
```

---

## Task 5 : Réinitialisation de mot de passe (backend)

**Files:**
- Create: `backend/app/models/password_reset_token.py`, `backend/app/auth/password_reset.py`, `backend/alembic/versions/<rev>_add_password_reset_token.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/schemas/auth.py`, `backend/app/routers/auth.py`, `backend/app/notifications/resend_client.py`, `backend/app/config.py`
- Test: `backend/tests/auth/test_password_reset.py`, `backend/tests/routers/test_auth_password_reset.py`

**Interfaces:**
- Produces:
  - `PasswordResetToken` — `id`, `user_id: int` (FK `users.id`, `ondelete="CASCADE"`), `token_hash: str(64) index`, `created_at`, `expires_at`, `used_at: datetime | None`.
  - `app.auth.password_reset.create_reset_token(db, user: User) -> str` — invalide (marque `used_at`) les tokens actifs de l'user, crée un nouveau token (valeur = `secrets.token_urlsafe(32)`, stockée hashée SHA-256), TTL = `settings.password_reset_token_ttl_minutes`. Renvoie la **valeur en clair** (jamais restockée). Commit.
  - `app.auth.password_reset.consume_reset_token(db, token: str, new_password: str) -> bool` — hash → recherche ligne non utilisée, non expirée → set `hashed_password`, `used_at`, invalide les autres tokens de l'user, commit. `False` si token invalide.
  - `resend_client.send_password_reset_email(to_email: str, reset_url: str) -> None`.
  - `ForgotPasswordIn { email: EmailStr }`, `ResetPasswordIn { token: str, password: str [8..72] }`.
  - `POST /auth/forgot-password` → **toujours 204** (throttlé, pas d'énumération). `POST /auth/reset-password` → 204 si OK, 400 sinon.

- [ ] **Step 1 : Tests unitaires qui échouent**

`backend/tests/auth/test_password_reset.py` :

```python
from datetime import timedelta

from app.auth.password_reset import consume_reset_token, create_reset_token
from app.auth.security import verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.utils.time import utcnow


def _user(db):
    u = User(email="u@e.com", hashed_password="x")
    db.add(u)
    db.commit()
    return u


def test_create_then_consume_sets_new_password(db_session):
    u = _user(db_session)
    token = create_reset_token(db_session, u)
    assert consume_reset_token(db_session, token, "newpass12") is True
    db_session.refresh(u)
    assert verify_password("newpass12", u.hashed_password)


def test_token_is_single_use(db_session):
    u = _user(db_session)
    token = create_reset_token(db_session, u)
    consume_reset_token(db_session, token, "newpass12")
    assert consume_reset_token(db_session, token, "another12") is False


def test_expired_token_rejected(db_session):
    u = _user(db_session)
    token = create_reset_token(db_session, u)
    row = db_session.query(PasswordResetToken).filter_by(user_id=u.id).one()
    row.expires_at = utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert consume_reset_token(db_session, token, "newpass12") is False


def test_creating_a_second_token_invalidates_the_first(db_session):
    u = _user(db_session)
    t1 = create_reset_token(db_session, u)
    create_reset_token(db_session, u)
    assert consume_reset_token(db_session, t1, "newpass12") is False
```

- [ ] **Step 2 : Vérifier l'échec** — FAIL (modules absents).

- [ ] **Step 3 : Modèle + migration** (calqué sur les précédents ; index sur `token_hash`).

- [ ] **Step 4 : `password_reset.py`**

```python
import hashlib
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.config import get_settings
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.utils.time import utcnow


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _invalidate_active(db: Session, user_id: int) -> None:
    now = utcnow()
    for row in db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None)
    ):
        row.used_at = now


def create_reset_token(db: Session, user: User) -> str:
    _invalidate_active(db, user.id)
    token = secrets.token_urlsafe(32)
    ttl = get_settings().password_reset_token_ttl_minutes
    db.add(PasswordResetToken(
        user_id=user.id, token_hash=_hash(token),
        expires_at=utcnow() + timedelta(minutes=ttl),
    ))
    db.commit()
    return token


def consume_reset_token(db: Session, token: str, new_password: str) -> bool:
    row = db.query(PasswordResetToken).filter_by(token_hash=_hash(token)).one_or_none()
    if row is None or row.used_at is not None or row.expires_at < utcnow():
        return False
    user = db.get(User, row.user_id)
    if user is None:
        return False
    user.hashed_password = hash_password(new_password)
    row.used_at = utcnow()
    _invalidate_active(db, user.id)
    db.commit()
    return True
```

`config.py` : `password_reset_token_ttl_minutes: int = 60`.

- [ ] **Step 5 : Email**

`resend_client.py` — ajouter :

```python
def send_password_reset_email(to_email: str, reset_url: str) -> None:
    safe = _safe_href(reset_url)
    html_body = (
        "<p>Tu as demandé à réinitialiser ton mot de passe.</p>"
        f'<p><a href="{safe}">Choisir un nouveau mot de passe</a></p>'
        "<p>Ce lien expire dans 1 heure. Si tu n'es pas à l'origine de cette "
        "demande, ignore cet email.</p>"
    )
    _send_email(to_email, "Réinitialisation de ton mot de passe", html_body)
```

- [ ] **Step 6 : Endpoints**

`backend/app/routers/auth.py` :

```python
@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(payload: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)) -> Response:
    identifier = f"{payload.email.lower()}|{client_ip(request)}"
    try:
        check_auth_throttle(db, action="forgot_password", identifier=identifier)
    except AuthThrottleExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    record_auth_attempt(db, action="forgot_password", identifier=identifier)

    user = db.query(User).filter(User.email == payload.email).first()
    if user is not None:
        token = create_reset_token(db, user)
        url = f"{get_settings().frontend_base_url}/reset-password?token={token}"
        try:
            send_password_reset_email(user.email, url)
        except EmailSendError:
            pass  # ne bloque pas ; l'incident remonte via GlitchTip (Beta 5)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)) -> Response:
    if not consume_reset_token(db, payload.token, payload.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lien invalide ou expiré.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 7 : Tests d'intégration**

`backend/tests/routers/test_auth_password_reset.py` :

```python
import pytest

from scripts.invites import generate_codes


@pytest.fixture()
def registered(client, db_session):
    (code,) = generate_codes(db_session, count=1, note="t")
    client.post("/auth/register", json={
        "email": "u@e.com", "password": "s3cret!1", "invite_code": code, "accept_terms": True})
    return "u@e.com"


def test_forgot_password_always_204(client, registered):
    assert client.post("/auth/forgot-password", json={"email": registered}).status_code == 204
    assert client.post("/auth/forgot-password", json={"email": "nobody@e.com"}).status_code == 204


def test_full_reset_flow(client, db_session, registered, monkeypatch):
    sent = {}
    monkeypatch.setattr(
        "app.routers.auth.send_password_reset_email",
        lambda to, url: sent.update(to=to, url=url),
    )
    client.post("/auth/forgot-password", json={"email": registered})
    token = sent["url"].split("token=")[1]
    assert client.post("/auth/reset-password", json={"token": token, "password": "brandnew1"}).status_code == 204
    assert client.post("/auth/login", data={"username": registered, "password": "brandnew1"}).status_code == 200


def test_reset_with_bad_token_returns_400(client):
    assert client.post("/auth/reset-password", json={"token": "nope", "password": "brandnew1"}).status_code == 400
```

- [ ] **Step 8 : Vérifier**

Run: `cd backend && pytest tests/auth/ tests/routers/test_auth.py tests/routers/test_auth_password_reset.py -v && ruff check app/ && mypy app`
Expected: PASS + lint/mypy OK.

- [ ] **Step 9 : Commit**

```bash
git add backend/app/models/password_reset_token.py backend/app/auth/password_reset.py backend/app/models/__init__.py backend/app/schemas/auth.py backend/app/routers/auth.py backend/app/notifications/resend_client.py backend/app/config.py backend/alembic/versions/*_add_password_reset_token.py backend/tests/auth/test_password_reset.py backend/tests/routers/test_auth_password_reset.py
git commit -m "feat(auth): minimal password-reset flow (token by email, single-use, 1h TTL)"
```

---

## Task 6 : Cookie de session `Secure` + `HttpOnly` (frontend)

**Files:**
- Create: `frontend/app/api/session/route.ts`
- Modify: `frontend/context/AuthContext.tsx`, `frontend/proxy.ts`

**Interfaces:**
- Produces: `POST /api/session { token }` → pose le cookie `search_app_token` `HttpOnly; Secure(en prod); SameSite=Lax; Path=/; Max-Age=86400`. `DELETE /api/session` → le supprime. Le domaine du cookie n'est **pas** fixé (host-only) — `beta` et `api.beta` sont des hôtes distincts, seul `beta` a besoin du cookie (c'est là que tourne `proxy.ts`).

- [ ] **Step 1 : Route handler**

`frontend/app/api/session/route.ts` :

```ts
import { NextRequest, NextResponse } from "next/server";

const COOKIE = "search_app_token";
const MAX_AGE = 60 * 60 * 24;

export async function POST(req: NextRequest) {
  const { token } = await req.json();
  if (typeof token !== "string" || !token) {
    return NextResponse.json({ error: "missing token" }, { status: 400 });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE,
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE, "", { path: "/", maxAge: 0 });
  return res;
}
```

- [ ] **Step 2 : `AuthContext.tsx`**

Remplacer `setTokenCookie` / `clearTokenCookie` (qui font `document.cookie = …`) par des appels au route handler :

```ts
async function setTokenCookie(token: string) {
  await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

async function clearTokenCookie() {
  await fetch("/api/session", { method: "DELETE" });
}
```

Adapter les appelants : `logout` devient `async` (ou `void clearTokenCookie()`), le `useEffect` de restauration `await`e `setTokenCookie`. `localStorage` reste la source du token pour le header `Authorization` (inchangé).

- [ ] **Step 3 : `proxy.ts`**

Ajouter `"/mot-de-passe-oublie"` et `"/reset-password"` à `AUTH_PATHS` et au `matcher` (redirection vers `/dashboard` si déjà connecté). Ne **pas** les mettre dans `PROTECTED_PREFIXES`.

- [ ] **Step 4 : Build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: OK.

- [ ] **Step 5 : Commit**

```bash
git add frontend/app/api/session/route.ts frontend/context/AuthContext.tsx frontend/proxy.ts
git commit -m "feat(auth): session cookie set HttpOnly+Secure via a Next route handler"
```

---

## Task 7 : Inscription + mot de passe oublié (frontend)

**Files:**
- Modify: `frontend/lib/api.ts`, `frontend/context/AuthContext.tsx`, `frontend/app/(auth)/login/page.tsx`
- Create: `frontend/app/(auth)/mot-de-passe-oublie/page.tsx`, `frontend/app/(auth)/reset-password/page.tsx`

**Interfaces:**
- Consumes: `POST /auth/register` (avec `invite_code`, `accept_terms`), `POST /auth/forgot-password`, `POST /auth/reset-password` (Task 5).
- Produces:
  - `api.register(email, password, inviteCode: string): Promise<User>`
  - `api.forgotPassword(email: string): Promise<void>`
  - `api.resetPassword(token: string, password: string): Promise<void>`
  - `useAuth().register(email, password, inviteCode)`.

- [ ] **Step 1 : `lib/api.ts`**

```ts
export async function register(email: string, password: string, inviteCode: string): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, invite_code: inviteCode, accept_terms: true }),
  });
}

export async function forgotPassword(email: string): Promise<void> {
  await request<void>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
}

export async function resetPassword(token: string, password: string): Promise<void> {
  await request<void>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) });
}
```

- [ ] **Step 2 : `AuthContext.tsx`**

`register` : signature `(email, password, inviteCode)` → `await api.register(email, password, inviteCode); await loginFn(email, password);`. Mettre à jour l'interface `AuthState`.

- [ ] **Step 3 : `login/page.tsx`**

En mode inscription (`!isLogin`) :
- ajouter un `<Input label="Code d'invitation" value={inviteCode} onChange=... required />` ;
- ajouter une case à cocher obligatoire : `J'accepte les <a href="/conditions">conditions d'utilisation</a> et la <a href="/confidentialite">politique de confidentialité</a>` (pages créées en Beta 4 — les liens peuvent 404 d'ici là, acceptable) ; bloquer la soumission si non cochée (message FR) ;
- passer `inviteCode` à `register(email, password, inviteCode)`.

En mode connexion : ajouter sous le champ mot de passe un lien `<a href="/mot-de-passe-oublie">Mot de passe oublié ?</a>`.

- [ ] **Step 4 : `mot-de-passe-oublie/page.tsx`**

Formulaire à un champ email → `api.forgotPassword(email)` → message générique : « Si un compte existe pour cette adresse, un email de réinitialisation vient d'être envoyé. » (afficher ce message quoi qu'il arrive). Réutiliser `Input` / `Button` / le style de `login/page.tsx`.

- [ ] **Step 5 : `reset-password/page.tsx`**

`"use client"`, lit `token` via `useSearchParams()`. Deux champs (mot de passe + confirmation, min 8, égalité) → `api.resetPassword(token, password)` → succès : message + `router.push("/login")` ; erreur : « Lien invalide ou expiré, redemande-en un. » + lien vers `/mot-de-passe-oublie`.

- [ ] **Step 6 : Build + vérif navigateur**

Run: `cd frontend && npm run typecheck && npm run build`
Puis (backend + frontend up, cf. [[dev-workflow-feedback]] : vérif navigateur réelle) : générer un code via `python -m scripts.invites generate --count 1`, s'inscrire avec (case cochée), se déconnecter, « mot de passe oublié », récupérer le lien dans les logs backend (ou un `monkeypatch`/inbox Resend de test), réinitialiser, se reconnecter avec le nouveau mot de passe. Console navigateur propre.

- [ ] **Step 7 : Commit**

```bash
git add frontend/lib/api.ts frontend/context/AuthContext.tsx "frontend/app/(auth)/login/page.tsx" "frontend/app/(auth)/mot-de-passe-oublie/page.tsx" "frontend/app/(auth)/reset-password/page.tsx"
git commit -m "feat(auth): invite-code + consent on signup, forgot/reset password pages"
```

---

## Self-Review

**Couverture du spec §3 :**

| Exigence | Task |
|---|---|
| §3.1 modèle `InviteCode` + migration | Task 1 |
| §3.1 `register` valide+consomme dans une txn verrouillée (`FOR UPDATE`) | Task 3 (`redeem_invite_code`) |
| §3.1 script admin generate/list/revoke | Task 2 |
| §3.2 colonnes `consent_*` + `CURRENT_TERMS_VERSION` + `accept_terms` obligatoire | Task 3 |
| §3.3 cookie `Secure` + `HttpOnly` via route handler | Task 6 |
| §3.3 `CORS_ORIGINS` prod | Beta 1 `.env` + commentaire Task 3 Step 6 (code inchangé, déjà branché sur `settings`) |
| §3.4 throttle login (8/15min), register (5/h), forgot (5/h) | Task 4 + Task 5 |
| §3.5 `PasswordResetToken` + `/forgot-password` (204 toujours) + `/reset-password` + email + pages | Task 5 + Task 7 |
| §3.6 JWT 24 h inchangé | aucune modif (constat Self-Review) |

**Placeholders :** aucun `TBD`/`TODO`. Les migrations Tasks 4 et 5 disent « calqué sur les précédents » **et** donnent la structure exacte des colonnes/index dans le bloc Interfaces — l'implémenteur a le contenu.

**Cohérence des noms :** `redeem_invite_code`, `InviteCodeError`, `CURRENT_TERMS_VERSION` (= `"2026-09"`), `check_auth_throttle` / `record_auth_attempt` / `clear_auth_attempts` / `AuthThrottleExceeded`, `client_ip`, `create_reset_token` / `consume_reset_token`, `send_password_reset_email`, `/api/session`, actions `login|register|forgot_password` — identiques entre tasks et Self-Review.

**Ordre d'exécution imposé :** Task 1 → **Task 4 avant Task 3** (le `register` de Task 3 appelle `check_auth_throttle`/`client_ip`) → Task 2 (utilisé par les tests de Task 3) → Task 3 → Task 5 → Task 6 → Task 7. *Recommandation : 1, 2, 4, 3, 5, 6, 7.*

**Dépendances externes vers d'autres plans :** les liens `/conditions` et `/confidentialite` (Task 7 Step 3) sont créés en Beta 4 — 404 temporaire tolérée. Le champ `is_admin` et l'observabilité GlitchTip (référencée dans le `except EmailSendError: pass`) arrivent en Beta 3/5.
