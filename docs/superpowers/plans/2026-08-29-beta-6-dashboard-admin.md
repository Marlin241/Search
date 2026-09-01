# Beta — Plan 6 : Dashboard admin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner à l'utilisateur (seul admin) une zone `/admin` pour voir les inscrits et leur activité LLM, ajuster un quota, désactiver un compte, gérer les codes d'invitation, basculer l'interrupteur LLM, et lire les retours in-app.

**Architecture:** Un booléen `users.is_admin` (+ `users.is_active`) ; une dépendance `get_current_admin` derrière laquelle vit **tout** `app/routers/admin.py` (préfixe `/admin`). Les endpoints réutilisent les briques des plans précédents : `usage_summary` / `monthly_limit` (Beta 3), `generate_codes` / `list_codes` / `revoke_code` (Beta 2), `set_llm_features_enabled` (Beta 3). Le frontend a un segment `/admin` protégé par `proxy.ts` **et** par un garde `is_admin` ; une seule page à onglets (lecture d'abord, quelques actions).

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Next 16, pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-lancement-beta-design.md` — §7 en entier (7.1 accès, 7.2 endpoints & écrans). Crée aussi le modèle `Feedback` (spec §8.1) dont l'admin lit les lignes ; le `POST /feedback` public + le widget sont en Beta 7.

## Global Constraints

- **Branche** `feature/beta-launch`, jamais `main`. Commits scopés.
- **Migrations additives** : `users.is_admin` / `users.is_active` avec `server_default` (`false` / `true`) pour s'appliquer aux lignes existantes ; nouvelle table `feedback`.
- **Tout `/admin/*` est derrière `get_current_admin`** — aucun endpoint admin accessible à un compte normal (→ `403`). Un compte non-admin ne doit rien apprendre de l'existence des routes.
- **Aucun graphique** — tableaux + compteurs. Réutiliser `framer-motion` / `lucide-react` / les composants `ui/` existants.
- **Un seul admin** — pas de système de rôles. `is_admin` posé à la main en base.
- **Datetimes naïfs UTC** ; `app.utils.time.utcnow()`.
- **Pas de nouvelle dépendance.**
- **Après modif backend testée** : rebuild du conteneur backend.

---

## File Structure

**Créés :**
- `backend/app/models/feedback.py` — `Feedback`.
- `backend/app/routers/admin.py` — routeur `/admin`.
- `backend/app/schemas/admin.py` — schémas de réponse/entrée admin.
- `backend/alembic/versions/<rev>_add_user_admin_flags.py`
- `backend/alembic/versions/<rev>_add_feedback.py`
- `backend/tests/routers/test_admin.py`
- `frontend/app/(app)/admin/layout.tsx` — garde `is_admin`.
- `frontend/app/(app)/admin/page.tsx` — page à onglets.
- `frontend/components/admin/` — `OverviewTab.tsx`, `UsersTab.tsx`, `InvitesTab.tsx`, `FeedbackTab.tsx`.

**Modifiés :**
- `backend/app/models/user.py` — `is_admin: bool`, `is_active: bool`.
- `backend/app/models/__init__.py` — `Feedback`.
- `backend/app/auth/dependencies.py` — `get_current_admin` ; `get_current_user` rejette `is_active is False`.
- `backend/app/routers/auth.py` — `login` rejette un compte désactivé (`403`).
- `backend/app/schemas/auth.py` — `UserOut` gagne `is_admin: bool`.
- `backend/app/main.py` — `app.include_router(admin.router)`.
- `frontend/lib/types.ts` — `User.is_admin` ; types admin.
- `frontend/lib/api.ts` — fonctions admin.
- `frontend/proxy.ts` — `/admin` dans `PROTECTED_PREFIXES` + `matcher`.
- `frontend/lib/navConfig.ts` — `ADMIN_NAV_ITEM`.
- `frontend/components/layout/Sidebar.tsx` (+ `MobileNav.tsx` si pertinent) — afficher `ADMIN_NAV_ITEM` si `user?.is_admin`.
- `docs/RUNBOOK.md` — section « Admin ».

---

## Task 1 : `users.is_admin` / `users.is_active` + `get_current_admin`

**Files:**
- Modify: `backend/app/models/user.py`, `backend/app/auth/dependencies.py`, `backend/app/routers/auth.py`, `backend/app/schemas/auth.py`
- Create: `backend/alembic/versions/<rev>_add_user_admin_flags.py`
- Test: `backend/tests/routers/test_admin.py` (créé ici)

**Interfaces:**
- Produces:
  - `User.is_admin: bool` (`default=False`, `server_default=sa.text("false")`), `User.is_active: bool` (`default=True`, `server_default=sa.text("true")`).
  - `app.auth.dependencies.get_current_admin(current_user: User = Depends(get_current_user)) -> User` — `403 "Accès réservé."` si `not current_user.is_admin`.
  - `get_current_user` lève `401` (message générique existant) si `current_user.is_active is False`.
  - `login` lève `403 "Ce compte est désactivé."` si `not user.is_active`.
  - `UserOut.is_admin: bool`.

- [ ] **Step 1 : Tests qui échouent**

`backend/tests/routers/test_admin.py` :

```python
import pytest

from app.models.user import User
from scripts.invites import generate_codes


@pytest.fixture()
def admin_headers(client, db_session):
    (code,) = generate_codes(db_session, count=1, note="admin")
    client.post("/auth/register", json={
        "email": "admin@e.com", "password": "s3cret!1", "invite_code": code, "accept_terms": True})
    db_session.query(User).filter_by(email="admin@e.com").update({"is_admin": True})
    db_session.commit()
    token = client.post("/auth/login", data={"username": "admin@e.com", "password": "s3cret!1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_headers(client, db_session):
    (code,) = generate_codes(db_session, count=1, note="u")
    client.post("/auth/register", json={
        "email": "u@e.com", "password": "s3cret!1", "invite_code": code, "accept_terms": True})
    token = client.post("/auth/login", data={"username": "u@e.com", "password": "s3cret!1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_me_reports_is_admin(client, admin_headers):
    assert client.get("/auth/me", headers=admin_headers).json()["is_admin"] is True


def test_admin_overview_forbidden_for_normal_user(client, user_headers):
    assert client.get("/admin/overview", headers=user_headers).status_code == 403


def test_disabled_account_cannot_login(client, db_session, user_headers):
    db_session.query(User).filter_by(email="u@e.com").update({"is_active": False})
    db_session.commit()
    assert client.post("/auth/login", data={"username": "u@e.com", "password": "s3cret!1"}).status_code == 403
```

- [ ] **Step 2 : Vérifier l'échec** — colonnes absentes / route `/admin/overview` 404 (le test 403 échouera en 404 pour l'instant — acceptable, il passera après Task 3 ; garder ce test ici mais le marquer `xfail` jusqu'à Task 3, ou le déplacer). **Recommandé : garder `test_me_reports_is_admin` + `test_disabled_account_cannot_login` ici, déplacer `test_admin_overview_forbidden_for_normal_user` en Task 3.**

- [ ] **Step 3 : Colonnes + migration**

`user.py` — après `consent_version` :

```python
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default=text("true"))
```

(importer `Boolean`, `text` de `sqlalchemy`.)

Migration :

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))

def downgrade() -> None:
    op.drop_column("users", "is_active")
    op.drop_column("users", "is_admin")
```

- [ ] **Step 4 : `get_current_admin` + rejets `is_active`**

`auth/dependencies.py` :

```python
def get_current_user(...):
    ...
    user = db.query(User).filter(User.email == email).first()
    if user is None or user.is_active is False:
        raise credentials_exception
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé.")
    return current_user
```

`routers/auth.py` `login` : après avoir vérifié le mot de passe, avant de créer le token :

```python
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ce compte est désactivé.")
```

- [ ] **Step 5 : `UserOut.is_admin`**

`schemas/auth.py` : `class UserOut(BaseModel): id: int; email: str; is_admin: bool = False; model_config = {"from_attributes": True}`.

- [ ] **Step 6 : Vérifier**

Run: `cd backend && pytest tests/routers/test_admin.py tests/routers/test_auth.py tests/auth/ -v && ruff check app/ && mypy app`
Expected: PASS (hors le test déplacé en Task 3).

- [ ] **Step 7 : Commit**

```bash
git add backend/app/models/user.py backend/app/auth/dependencies.py backend/app/routers/auth.py backend/app/schemas/auth.py backend/alembic/versions/*_add_user_admin_flags.py backend/tests/routers/test_admin.py
git commit -m "feat(admin): users.is_admin / is_active + get_current_admin dependency"
```

---

## Task 2 : Modèle `Feedback`

**Files:**
- Create: `backend/app/models/feedback.py`, `backend/alembic/versions/<rev>_add_feedback.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/routers/test_admin.py` (indirect, via Task 4)

**Interfaces:**
- Produces: `Feedback` — `id`, `user_id: int | None` (FK `users.id`, `ondelete="SET NULL"`), `page: str(255)`, `message: str` (Text), `created_at: datetime` (index), `handled_at: datetime | None`.

- [ ] **Step 1 : Modèle**

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    page: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

> Note : `account_deletion.delete_account` (Beta 4) délie déjà `invite_codes` mais **pas** `feedback`. Comme `user_id` est `SET NULL`, un feedback survit anonymisé à la suppression de compte — comportement voulu (on garde le retour, pas l'identité). Si Beta 4 est déjà exécuté, ajouter `db.execute(update(Feedback).where(Feedback.user_id == uid).values(user_id=None))` dans `delete_account` — sinon le FK SQLite non appliqué laisserait un `user_id` pendouillant en test. **Action : ajouter cette ligne à `delete_account` dans cette task** et un test dans `tests/auth/test_account_deletion.py`.

- [ ] **Step 2 : Migration + enregistrement `__init__.py`** (table `feedback`, index `created_at`).

- [ ] **Step 3 : Patch `delete_account`** (cf. note ci-dessus) + test « feedback de l'user est anonymisé, pas supprimé ».

- [ ] **Step 4 : Vérifier**

Run: `cd backend && pytest tests/auth/test_account_deletion.py -q && alembic upgrade head --sql >/dev/null`

- [ ] **Step 5 : Commit**

```bash
git add backend/app/models/feedback.py backend/app/models/__init__.py backend/alembic/versions/*_add_feedback.py backend/app/auth/account_deletion.py backend/tests/auth/test_account_deletion.py
git commit -m "feat(admin): Feedback model (+ anonymise on account deletion)"
```

---

## Task 3 : `admin.py` — overview, users, quota, désactivation

**Files:**
- Create: `backend/app/routers/admin.py`, `backend/app/schemas/admin.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/routers/test_admin.py`

**Interfaces:**
- Consumes: `get_current_admin` (Task 1), `usage_summary` / `monthly_limit` / `FEATURES` (Beta 3), `llm_features_enabled` (Beta 3).
- Produces (tous derrière `get_current_admin`, préfixe `/admin`) :
  - `GET /admin/overview` → `{ users_total, users_active_7d, llm_calls_this_month: {feature: count}, tokens_this_month: {input, output}, llm_features_enabled: bool }`.
  - `GET /admin/users` → `list[AdminUserOut]` : `{ id, email, created_at, is_admin, is_active, invite_note, consent_version, consent_accepted_at, last_activity_at, usage: [UsageItemOut] }`. `invite_note` = `note` du `InviteCode` où `used_by_user_id == user.id` (ou `null`). `last_activity_at` = `max(created_at)` sur `llm_call_logs` de l'user (ou `null`).
  - `GET /admin/users/{id}` → même forme + `quota_overrides: dict | null`.
  - `PATCH /admin/users/{id}/quota` — body `{ feature: str, limit: int | null }` (`feature ∈ FEATURES`) → met à jour `user.quota_overrides[feature]` (ou le retire si `limit is null` ; `quota_overrides` devient `null` si vide). Renvoie le `AdminUserOut`.
  - `PATCH /admin/users/{id}/active` — body `{ active: bool }` → set `user.is_active`. Interdit de se désactiver soi-même (`400`). Renvoie `AdminUserOut`.

- [ ] **Step 1 : Tests qui échouent**

Ajouter à `tests/routers/test_admin.py` (+ le test déplacé de Task 1) :

```python
def test_admin_overview_forbidden_for_normal_user(client, user_headers):
    assert client.get("/admin/overview", headers=user_headers).status_code == 403


def test_overview_counts_users(client, admin_headers, user_headers):
    body = client.get("/admin/overview", headers=admin_headers).json()
    assert body["users_total"] >= 2
    assert "llm_features_enabled" in body


def test_users_list_includes_invite_note_and_usage(client, admin_headers):
    rows = client.get("/admin/users", headers=admin_headers).json()
    admin_row = next(r for r in rows if r["email"] == "admin@e.com")
    assert admin_row["invite_note"] == "admin"
    assert len(admin_row["usage"]) == 6


def test_patch_quota_sets_override(client, db_session, admin_headers):
    from app.models.user import User
    uid = db_session.query(User).filter_by(email="admin@e.com").one().id
    resp = client.patch(f"/admin/users/{uid}/quota", headers=admin_headers, json={"feature": "cv", "limit": 25})
    assert resp.status_code == 200
    assert db_session.get(User, uid).quota_overrides == {"cv": 25}
    client.patch(f"/admin/users/{uid}/quota", headers=admin_headers, json={"feature": "cv", "limit": None})
    db_session.expire_all()
    assert db_session.get(User, uid).quota_overrides in (None, {})


def test_cannot_disable_self(client, db_session, admin_headers):
    from app.models.user import User
    uid = db_session.query(User).filter_by(email="admin@e.com").one().id
    assert client.patch(f"/admin/users/{uid}/active", headers=admin_headers, json={"active": False}).status_code == 400
```

- [ ] **Step 2 : Vérifier l'échec** — 404.

- [ ] **Step 3 : Schémas** (`schemas/admin.py`)

```python
from pydantic import BaseModel

from app.schemas.auth import UsageItemOut


class AdminUserOut(BaseModel):
    id: int
    email: str
    created_at: str
    is_admin: bool
    is_active: bool
    invite_note: str | None
    consent_version: str | None
    consent_accepted_at: str | None
    last_activity_at: str | None
    quota_overrides: dict | None = None
    usage: list[UsageItemOut]


class QuotaPatchIn(BaseModel):
    feature: str
    limit: int | None


class ActivePatchIn(BaseModel):
    active: bool
```

- [ ] **Step 4 : Routeur** (`routers/admin.py`) — implémenter les 5 endpoints. Points d'attention :
  - `_to_admin_user_out(db, user)` centralise la construction (invite_note via `InviteCode`, last_activity via `func.max(LlmCallLog.created_at)`, `usage=usage_summary(db, user)`, dates en `.isoformat()` ou `None`).
  - `PATCH /quota` : valider `feature in FEATURES` (`422` sinon) ; muter une **copie** de `quota_overrides` puis réassigner (SQLAlchemy ne détecte pas la mutation in-place d'un `JSON`).
  - `PATCH /active` : `if user_id == current_admin.id and not payload.active: 400`.
  - `overview` : `llm_calls_this_month` = `group_by(LlmCallLog.feature)` filtré `created_at >= month_start` ; `tokens_this_month` = `func.sum(input_tokens/output_tokens)` sur la même fenêtre.

- [ ] **Step 5 : Enregistrer le routeur**

`main.py` : `from app.routers import (... , admin, ...)` + `app.include_router(admin.router)`.

- [ ] **Step 6 : Vérifier**

Run: `cd backend && pytest tests/routers/test_admin.py -v && ruff check app/ && mypy app`
Expected: PASS.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/routers/admin.py backend/app/schemas/admin.py backend/app/main.py backend/tests/routers/test_admin.py
git commit -m "feat(admin): /admin overview + users list/detail + quota override + enable/disable"
```

---

## Task 4 : `admin.py` — invitations, interrupteur LLM, feedback

**Files:**
- Modify: `backend/app/routers/admin.py`, `backend/app/schemas/admin.py`
- Test: `backend/tests/routers/test_admin.py`

**Interfaces:**
- Consumes: `generate_codes` / `list_codes` / `revoke_code` (Beta 2 `scripts.invites`), `set_llm_features_enabled` / `llm_features_enabled` (Beta 3 `app.llm.switch`), `Feedback` (Task 2).
- Produces :
  - `GET /admin/invites` → `list[AdminInviteOut]` : `{ code, note, created_at, expires_at, used_by_email, used_at }`.
  - `POST /admin/invites` — body `{ count: int (1..50), note: str | null }` → `{ codes: [str] }`.
  - `DELETE /admin/invites/{code}` → `204` si révoqué, `409` si déjà utilisé / inconnu.
  - `POST /admin/llm-toggle` — body `{ enabled: bool }` → `{ enabled: bool }` (état effectif après bascule).
  - `GET /admin/feedback` → `list[AdminFeedbackOut]` : `{ id, user_email, page, message, created_at, handled_at }` (tri `created_at` desc).
  - `POST /admin/feedback/{id}/handled` → marque `handled_at = utcnow()` → `204`.

- [ ] **Step 1 : Tests qui échouent** — ajouter :

```python
def test_generate_and_revoke_invites(client, admin_headers):
    codes = client.post("/admin/invites", headers=admin_headers, json={"count": 3, "note": "vague 2"}).json()["codes"]
    assert len(codes) == 3
    listing = client.get("/admin/invites", headers=admin_headers).json()
    assert any(row["code"] == codes[0] and row["note"] == "vague 2" for row in listing)
    assert client.delete(f"/admin/invites/{codes[0]}", headers=admin_headers).status_code == 204


def test_llm_toggle(client, admin_headers):
    assert client.post("/admin/llm-toggle", headers=admin_headers, json={"enabled": False}).json()["enabled"] is False
    assert client.get("/admin/overview", headers=admin_headers).json()["llm_features_enabled"] is False
    client.post("/admin/llm-toggle", headers=admin_headers, json={"enabled": True})


def test_feedback_list_and_handle(client, db_session, admin_headers):
    from app.models.feedback import Feedback
    db_session.add(Feedback(user_id=None, page="/offres", message="super utile"))
    db_session.commit()
    rows = client.get("/admin/feedback", headers=admin_headers).json()
    assert rows[0]["message"] == "super utile"
    assert client.post(f"/admin/feedback/{rows[0]['id']}/handled", headers=admin_headers).status_code == 204
```

- [ ] **Step 2 : Vérifier l'échec** — 404.

- [ ] **Step 3 : Implémenter** les 6 endpoints dans `admin.py` (+ schémas `AdminInviteOut`, `AdminFeedbackOut`, `InviteCreateIn`, `LlmToggleIn` dans `schemas/admin.py`). `used_by_email` / `user_email` : `LEFT JOIN users`.

- [ ] **Step 4 : Vérifier**

Run: `cd backend && pytest -q && ruff check app/ && ruff format --check app/ && mypy app`
Expected: suite complète verte.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/routers/admin.py backend/app/schemas/admin.py backend/tests/routers/test_admin.py
git commit -m "feat(admin): invite management, LLM kill-switch toggle, feedback inbox"
```

---

## Task 5 : Frontend — segment `/admin`

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/api.ts`, `frontend/proxy.ts`, `frontend/lib/navConfig.ts`, `frontend/components/layout/Sidebar.tsx`
- Create: `frontend/app/(app)/admin/layout.tsx`, `frontend/app/(app)/admin/page.tsx`, `frontend/components/admin/{OverviewTab,UsersTab,InvitesTab,FeedbackTab}.tsx`

**Interfaces:**
- Consumes: tous les endpoints `/admin/*` + `GET /auth/me` (champ `is_admin`).
- Produces:
  - `User.is_admin: boolean` (type).
  - `api.admin.*` : `getOverview(token)`, `getUsers(token)`, `patchUserQuota(token, id, feature, limit)`, `patchUserActive(token, id, active)`, `getInvites(token)`, `createInvites(token, count, note)`, `revokeInvite(token, code)`, `toggleLlm(token, enabled)`, `getFeedback(token)`, `markFeedbackHandled(token, id)`.
  - `/admin` — page à 4 onglets (Vue d'ensemble / Utilisateurs / Invitations / Feedback).

- [ ] **Step 1 : Types + API**

`lib/types.ts` : `User.is_admin: boolean` ; `AdminUser`, `AdminInvite`, `AdminFeedback`, `AdminOverview` (miroir des schémas backend).
`lib/api.ts` : regrouper les fonctions sous un objet `export const admin = { ... }` (chacune = `request(...)` avec le token). `createInvites` renvoie `{ codes: string[] }`.

- [ ] **Step 2 : `proxy.ts` + garde**

`proxy.ts` : ajouter `"/admin"` à `PROTECTED_PREFIXES` et au `matcher` (`/admin/:path*`).
`app/(app)/admin/layout.tsx` (`"use client"`) :

```tsx
"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!isLoading && !user?.is_admin) router.replace("/dashboard");
  }, [isLoading, user, router]);
  if (isLoading || !user?.is_admin) return null;
  return <>{children}</>;
}
```

- [ ] **Step 3 : Nav conditionnelle**

`lib/navConfig.ts` : `export const ADMIN_NAV_ITEM: NavItem = { href: "/admin", label: "Admin", mobileLabel: "Admin", icon: Shield };` (importer `Shield` de lucide-react).
`Sidebar.tsx` : si `user?.is_admin`, rendre `ADMIN_NAV_ITEM` après `NAV_ITEMS`. (Idem `MobileNav.tsx` si l'espace le permet, sinon desktop seulement.)

- [ ] **Step 4 : Page à onglets**

`app/(app)/admin/page.tsx` (`"use client"`) : un `useState` d'onglet actif + rendu conditionnel des 4 composants `components/admin/*`. Style : réutiliser le pattern d'onglets de `app/(app)/offres/[savedJobId]/page.tsx` (workspace tabs) si présent, sinon des boutons simples.

- **`OverviewTab`** : 4 compteurs (`users_total`, `users_active_7d`, total appels LLM ce mois, tokens ce mois) + une ligne « Fonctionnalités LLM : ON/OFF » avec un `<Button>` de bascule (`toggleLlm`).
- **`UsersTab`** : tableau (email, inscrit le, note d'invitation, dernier usage, actif). Clic sur une ligne → panneau latéral / accordéon : les 6 jauges d'usage (`used/limit`), un champ « override » par feature (`patchUserQuota`), un bouton « Désactiver / Réactiver » (`patchUserActive`).
- **`InvitesTab`** : formulaire (nombre + note) → `createInvites` → **affiche les codes générés en clair** (à copier) ; tableau des codes existants avec statut (libre / utilisé par `email`) + bouton « Révoquer » sur les codes libres.
- **`FeedbackTab`** : liste (date, email ou « anonyme », page, message) ; bouton « Marquer traité » → `markFeedbackHandled` ; les traités passent en grisé / bas de liste.

- [ ] **Step 5 : Build + vérif navigateur**

Run: `cd frontend && npm run typecheck && npm run build`
Puis (stack up, compte admin promu via SQL — cf. runbook Task 6) : ouvrir `/admin`, vérifier les 4 onglets ; un compte non-admin sur `/admin` est redirigé vers `/dashboard` et l'entrée de nav « Admin » n'apparaît pas ; générer 2 codes, en révoquer un ; basculer l'interrupteur LLM et vérifier l'effet sur une génération ; ajuster un quota `cv` d'un user de test et vérifier via `/admin/users/{id}`. Console propre.

- [ ] **Step 6 : Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/proxy.ts frontend/lib/navConfig.ts frontend/components/layout/Sidebar.tsx "frontend/app/(app)/admin/" frontend/components/admin/
git commit -m "feat(admin): /admin dashboard — overview, users, invites, feedback tabs"
```

---

## Task 6 : Runbook — section admin

**Files:**
- Modify: `docs/RUNBOOK.md`

- [ ] **Step 1 : Ajouter**

```markdown
## Admin

- Se donner les droits admin (une fois) :
  `docker compose -f docker-compose.prod.yml exec db psql -U postgres -d ats_diagnostic -c "UPDATE users SET is_admin = true WHERE email = 'guyroland879@gmail.com';"`
- Dashboard : https://beta.yokkutelabs.com/admin (visible seulement pour un
  compte `is_admin`).
- Codes d'invitation : onglet Invitations (ou CLI
  `docker compose ... exec backend python -m scripts.invites generate --count 15 --note "vague 1"`).
- Interrupteur LLM : onglet Vue d'ensemble (ou CLI
  `docker compose ... exec backend python -m scripts.llm_switch off`).
- Ajuster le quota d'un testeur : onglet Utilisateurs > ligne > override par
  fonctionnalité.
- Désactiver un compte : onglet Utilisateurs > Désactiver (le compte ne peut
  plus se connecter ; données conservées).
```

- [ ] **Step 2 : Commit**

```bash
git add docs/RUNBOOK.md
git commit -m "docs(runbook): admin section (promote admin, invites, kill-switch, quotas)"
```

---

## Self-Review

**Couverture du spec §7 :**

| Exigence | Task |
|---|---|
| §7.1 `is_admin` + positionné en base | Task 1 + runbook (Task 6) |
| §7.1 `get_current_admin` → 403 | Task 1 |
| §7.1 `app/routers/admin.py` préfixe `/admin`, tout derrière le garde | Tasks 3, 4 |
| §7.1 frontend `/admin` protégé par `proxy.ts` + garde `is_admin` | Task 5 (Steps 2) |
| §7.1 `is_admin` dans `UserOut` / `/auth/me` | Task 1 Step 5 |
| §7.2 Vue d'ensemble (users, actifs 7j, appels LLM/feature, tokens, état interrupteur) | Task 3 (`/admin/overview`) + Task 5 `OverviewTab` |
| §7.2 Utilisateurs (email, inscription, note code, consentement, dernière activité, usage, quotas) | Task 3 (`/admin/users`) + Task 5 `UsersTab` |
| §7.2 détail user + `PATCH quota` + désactiver | Task 3 + Task 5 |
| §7.2 Feedback (liste, marquer traité) | Task 2 (modèle) + Task 4 (`/admin/feedback`) + Task 5 `FeedbackTab` |
| §7.2 Codes d'invitation (générer + note, lister, révoquer) | Task 4 + Task 5 `InvitesTab` |
| §7.2 Interrupteur LLM (`POST /admin/llm-toggle`) | Task 4 |
| §7.2 CLI `scripts/invites.py` reste dispo | oui (Beta 2, inchangé) |

**Placeholders :** aucun `TBD` de code. Les migrations donnent les colonnes/`server_default` exacts.

**Cohérence des noms :** `get_current_admin`, `is_admin` / `is_active`, `AdminUserOut` / `AdminInviteOut` / `AdminFeedbackOut` / `QuotaPatchIn` / `ActivePatchIn` / `InviteCreateIn` / `LlmToggleIn`, routes `/admin/{overview,users,users/{id},users/{id}/quota,users/{id}/active,invites,invites/{code},llm-toggle,feedback,feedback/{id}/handled}`, `api.admin.*` (frontend), `ADMIN_NAV_ITEM`, `Feedback` (table `feedback`). Identiques entre tasks.

**Dépendances inter-plans :** requiert Beta 2 (`scripts.invites`, `InviteCode`, consentement) et Beta 3 (`usage_summary`, `monthly_limit`, `FEATURES`, `app.llm.switch`). **À exécuter après Beta 2 et Beta 3.** Beta 4 : la note de Task 2 patche `delete_account` pour anonymiser `feedback` — si Beta 4 n'est pas encore fait, appliquer ce patch quand Beta 4 l'est (renvoi croisé à ajouter dans Beta 4 au moment de l'exécution).

**Ordre d'exécution :** 1 → 2 → 3 → 4 → 5 → 6.
