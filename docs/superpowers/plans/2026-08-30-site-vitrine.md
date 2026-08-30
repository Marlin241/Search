# Site vitrine public — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le redirect de `/` par une landing publique FR qui présente le produit, avec CTA « Se connecter » / « Demander un accès », un formulaire de demande d'accès maîtrisé, et le renvoi d'un visiteur connecté vers `/dashboard`.

**Architecture:** `app/page.tsx` devient un server component statique (plus de redirect JS). `proxy.ts` renvoie un visiteur déjà authentifié de `/` vers `/dashboard`. Le formulaire « Demander un accès » poste sur un nouvel endpoint public `POST /access-requests` (honeypot + throttle IP réutilisant `auth_throttle`, réponse toujours 204, notif Resend à l'admin non bloquante) ; les demandes sont visibles dans un nouvel onglet de `/admin`. Le nom du produit est centralisé dans `lib/brand.ts` pour un renommage trivial ultérieur.

**Tech Stack:** Next 16.3.2 (App Router, Turbopack), React, Tailwind + design system maison (`components/ui/*`, `app/globals.css`), framer-motion ; FastAPI, SQLAlchemy, Alembic, pytest ; Resend.

**Spec:** `docs/superpowers/specs/2026-08-30-site-vitrine-design.md`

## Global Constraints

- **Frontend = Next 16, APIs cassées vs training data.** Lire le guide concerné dans `frontend/node_modules/next/dist/docs/01-app/` AVANT d'écrire du code frontend. Le bloc « This is NOT the Next.js you know » de `frontend/AGENTS.md` est réécrit par `next dev` — le committer avec le travail, ne pas le combattre.
- **FR uniquement.** Toute copie visible en français. Pas d'i18n câblée.
- **Nom produit** : `"Search"` (provisoire), toujours via `lib/brand.ts` — jamais en dur. Le badge « v3 » disparaît.
- **Design system produit** : primaire indigo `hsl(239 84% 67%)`, accent teal `hsl(172 66% 50%)`, polices Outfit (`font-display`) + Inter (`font-sans`). Classes utilitaires réelles : `.gradient-hero`, `.gradient-text`, `.gradient-primary`, `.glass`, `animate-fade-in`. **Pas** d'alignement sur le vert de yokkutelabs.com.
- **Landing en `noindex`** pour l'instant (`robots: { index: false, follow: false }`).
- **Mobile-first** : le visiteur type est sur téléphone. Aucun débordement horizontal, cibles tactiles ≥ 44 px.
- **Backend sans volume mount** : après toute modif backend, `docker compose up -d --build backend` depuis la racine, puis `docker logs search-backend-1` + `curl http://localhost:8000/docs`.
- **Commits scopés** : `git add <chemins>` explicites, jamais `git add -A`. Ne pas emporter de fichiers sales non liés (il peut y avoir un `backend/..env.swp` traînant — le laisser).
- **Message de commit** : finir par
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01QvHhwKEBXa6Y2M99QcXF4v
  ```
- **Branche** : `feature/site-vitrine` (déjà créée depuis `feature/beta-launch`). Ne pas merger dans `main`.
- **Tests backend** : `cd backend && ./venv/bin/pytest` (ou `pytest` si venv activé). Pattern : fixtures locales par fichier calquées sur `tests/routers/test_feedback.py` / `test_admin.py`, ou `tests/_helpers.register_and_login`.
- **Vérif navigateur réelle obligatoire** pour le frontend (règle projet) : `claude-in-chrome` contre la stack dockerisée, console comprise, + viewport mobile.

---

## File Structure

**Backend — créés :**
- `backend/app/models/access_request.py` — modèle `AccessRequest`.
- `backend/alembic/versions/<rev>_add_access_request.py` — migration.
- `backend/app/schemas/access_request.py` — `AccessRequestIn`, `AdminAccessRequestOut`.
- `backend/app/routers/access_requests.py` — endpoint public `POST /access-requests`.
- `backend/tests/routers/test_access_requests.py` — tests endpoint public.
- `backend/tests/routers/test_admin_access_requests.py` — tests endpoints admin.

**Backend — modifiés :**
- `backend/app/models/__init__.py` — enregistrer `AccessRequest`.
- `backend/app/rate_limit/auth_throttle.py` — entrée `"access_request"` dans `_LIMITS`.
- `backend/app/notifications/resend_client.py` — `send_access_request_notification()`.
- `backend/app/routers/admin.py` — `GET /admin/access-requests`, `POST /admin/access-requests/{id}/handled`.
- `backend/app/schemas/admin.py` — import/ré-export de `AdminAccessRequestOut`.
- `backend/app/main.py` — `app.include_router(access_requests.router)`.

**Frontend — créés :**
- `frontend/lib/brand.ts` — constantes de marque.
- `frontend/components/common/Logo.tsx` — logo partagé.
- `frontend/components/marketing/MarketingHeader.tsx`
- `frontend/components/marketing/Hero.tsx`
- `frontend/components/marketing/ProblemSection.tsx`
- `frontend/components/marketing/FeatureGrid.tsx`
- `frontend/components/marketing/HowItWorks.tsx`
- `frontend/components/marketing/AccessSection.tsx`
- `frontend/components/marketing/AccessRequestForm.tsx`
- `frontend/components/marketing/MarketingFooter.tsx`
- `frontend/components/marketing/UiMockup.tsx` — maquette stylisée du hero.
- `frontend/app/opengraph-image.tsx` — image OG générée (next/og).
- `frontend/components/admin/AccessRequestsTab.tsx`

**Frontend — modifiés :**
- `frontend/app/page.tsx` — devient la landing (server component).
- `frontend/proxy.ts` — règle `/` connecté → `/dashboard` + `matcher`.
- `frontend/app/layout.tsx` — `metadata` depuis `brand.ts`.
- `frontend/components/layout/Sidebar.tsx` — `<Logo>`, plus de « v3 ».
- `frontend/app/(auth)/login/page.tsx` — `<Logo>` / `PRODUCT_NAME` au lieu de « Search ».
- `frontend/components/common/LegalFooter.tsx` — email de contact depuis `brand.ts`.
- `frontend/lib/api.ts` — `requestAccess()` + bloc `admin` étendu.
- `frontend/lib/types.ts` — type `AdminAccessRequest`.
- `frontend/app/(app)/admin/page.tsx` — nouvel onglet.

**Docs — modifiés :**
- `docs/RUNBOOK.md` — purge `access_requests` (§7 RGPD).
- `docs/CHECKLIST-LANCEMENT.md` — ligne « landing publique vérifiée ».

---

## Task 1: Centraliser la marque + composant Logo + retrait « v3 »

**Files:**
- Create: `frontend/lib/brand.ts`
- Create: `frontend/components/common/Logo.tsx`
- Modify: `frontend/components/layout/Sidebar.tsx:5-30`
- Modify: `frontend/app/(auth)/login/page.tsx:6-11,83-90`
- Modify: `frontend/app/layout.tsx:19-23`
- Modify: `frontend/components/common/LegalFooter.tsx`

**Interfaces:**
- Produces:
  - `frontend/lib/brand.ts` : `PRODUCT_NAME: string`, `TAGLINE: string`, `PARENT_NAME: string`, `PARENT_URL: string`, `CONTACT_EMAIL: string`.
  - `frontend/components/common/Logo.tsx` : `export function Logo({ className, wordmark = true }: { className?: string; wordmark?: boolean }): JSX.Element` — pastille dégradée avec l'icône `Sparkles` (lucide) + wordmark `PRODUCT_NAME` en `font-display`.

- [ ] **Step 1: Lire le guide Next pertinent**

Lire `frontend/node_modules/next/dist/docs/01-app/01-getting-started/14-metadata-and-og-images.md` (section `metadata` statique) et vérifier la forme actuelle de l'objet `Metadata` (title/description/openGraph/robots).

- [ ] **Step 2: Créer `frontend/lib/brand.ts`**

```ts
/**
 * Identité de marque du produit, centralisée.
 * Le nom définitif n'est pas encore choisi : "Search" est provisoire.
 * Tout affichage du nom passe par ces constantes — jamais de "Search" en dur.
 */
export const PRODUCT_NAME = "Search";
export const TAGLINE =
  "Le copilote IA pour décrocher ton job — pensé pour Dakar et l'Afrique de l'Ouest.";
export const PARENT_NAME = "Yokkute Labs";
export const PARENT_URL = "https://yokkutelabs.com";
export const CONTACT_EMAIL = "solution@yokkutelabs.com";
```

- [ ] **Step 3: Créer `frontend/components/common/Logo.tsx`**

```tsx
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { PRODUCT_NAME } from "@/lib/brand";

export function Logo({
  className,
  wordmark = true,
}: {
  className?: string;
  wordmark?: boolean;
}) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-primary-600 to-accent text-white shadow-soft">
        <Sparkles className="h-5 w-5" />
      </span>
      {wordmark && (
        <span className="font-display text-xl font-bold tracking-tight text-foreground">
          {PRODUCT_NAME}
        </span>
      )}
    </span>
  );
}
```

- [ ] **Step 4: Remplacer la marque dans `Sidebar.tsx`**

Dans `frontend/components/layout/Sidebar.tsx`, remplacer le bloc `{/* Brand */}` (le `<Link href="/dashboard">` contenant la pastille + `<span>Search</span>` + `<span>v3</span>`) par :

```tsx
        {/* Brand */}
        <Link href="/dashboard" className="px-3">
          <Logo />
        </Link>
```

Ajouter l'import `import { Logo } from "@/components/common/Logo";` et retirer l'import `Sparkles` s'il n'est plus utilisé ailleurs dans le fichier (il l'est encore pour rien d'autre ici — vérifier ; `LogOut` reste utilisé).

- [ ] **Step 5: Remplacer la marque dans `login/page.tsx`**

Dans `frontend/app/(auth)/login/page.tsx`, le panneau gauche (`{/* LEFT panel - Hero (Talya style) */}`) contient :

```tsx
          <div className="flex items-center gap-3 mb-16">
            <div className="p-2 bg-white/15 rounded-xl backdrop-blur-md">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <span className="text-2xl font-display font-bold tracking-tight">Search</span>
          </div>
```

Remplacer uniquement le texte `Search` par `{PRODUCT_NAME}` (garder le style blanc sur fond dégradé — ne pas utiliser `<Logo>` ici car le wordmark de `<Logo>` est `text-foreground`, illisible sur ce fond). Ajouter `import { PRODUCT_NAME } from "@/lib/brand";`.

- [ ] **Step 6: Metadata depuis `brand.ts` dans `app/layout.tsx`**

Remplacer le bloc `export const metadata` par :

```tsx
import { PRODUCT_NAME, TAGLINE } from "@/lib/brand";

export const metadata: Metadata = {
  title: `${PRODUCT_NAME} — recherche d'emploi assistée par IA`,
  description: TAGLINE,
};
```

- [ ] **Step 7: Email de contact depuis `brand.ts` dans `LegalFooter.tsx`**

Remplacer `href="mailto:contact@yokkutelabs.com"` par `` href={`mailto:${CONTACT_EMAIL}`} `` et ajouter `import { CONTACT_EMAIL } from "@/lib/brand";`.

- [ ] **Step 8: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS, aucune erreur TS, build complet.

- [ ] **Step 9: Vérif navigateur**

`docker compose up -d --build frontend` puis, connecté, ouvrir `/dashboard` : la sidebar affiche le logo **sans** badge « v3 ». Ouvrir `/login` (en navigation privée) : le panneau gauche affiche le nom produit. Console sans erreur.

- [ ] **Step 10: Commit**

```bash
git add frontend/lib/brand.ts frontend/components/common/Logo.tsx \
  frontend/components/layout/Sidebar.tsx frontend/app/\(auth\)/login/page.tsx \
  frontend/app/layout.tsx frontend/components/common/LegalFooter.tsx frontend/AGENTS.md
git commit -m "$(cat <<'EOF'
refactor(brand): centralise le nom produit dans lib/brand.ts, retire le badge v3

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QvHhwKEBXa6Y2M99QcXF4v
EOF
)"
```

---

## Task 2: Modèle `AccessRequest` + migration

**Files:**
- Create: `backend/app/models/access_request.py`
- Create: `backend/alembic/versions/<rev>_add_access_request.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/test_access_request.py`

**Interfaces:**
- Produces: `app.models.access_request.AccessRequest` — colonnes `id: int` (PK), `email: str` (`String(320)`, non null, indexée non unique), `note: str` (`Text`, non null, `default=""`), `source_ip: str | None` (`String(64)`, nullable), `created_at: datetime` (non null, `default=utcnow`, indexée), `handled_at: datetime | None` (nullable).

- [ ] **Step 1: Écrire le test du modèle**

`backend/tests/models/test_access_request.py` :

```python
from app.models.access_request import AccessRequest
from app.utils.time import utcnow


def test_access_request_row_roundtrips(db_session):
    row = AccessRequest(email="a@b.com", note="je cherche un poste de dev", source_ip="1.2.3.4")
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(AccessRequest).one()
    assert fetched.email == "a@b.com"
    assert fetched.note == "je cherche un poste de dev"
    assert fetched.source_ip == "1.2.3.4"
    assert fetched.handled_at is None
    assert fetched.created_at is not None


def test_access_request_note_defaults_empty(db_session):
    row = AccessRequest(email="c@d.com")
    db_session.add(row)
    db_session.commit()
    assert db_session.query(AccessRequest).one().note == ""
```

- [ ] **Step 2: Lancer le test — échec attendu**

Run: `cd backend && ./venv/bin/pytest tests/models/test_access_request.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.access_request'`

- [ ] **Step 3: Créer le modèle**

`backend/app/models/access_request.py` (calqué sur `app/models/feedback.py`) :

```python
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utcnow


class AccessRequest(Base):
    """Demande d'accès à la beta déposée depuis la landing publique.
    Non rattachée à un utilisateur : la beta est sur invitation, l'admin
    traite les demandes à la main (génère un code, contacte la personne)."""

    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, index=True, nullable=False
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Enregistrer le modèle**

Dans `backend/app/models/__init__.py`, ajouter (ordre alphabétique) `from app.models.access_request import AccessRequest` en tête de liste et `"AccessRequest",` en tête de `__all__`.

- [ ] **Step 5: Lancer le test — succès attendu**

Run: `cd backend && ./venv/bin/pytest tests/models/test_access_request.py -v`
Expected: PASS

- [ ] **Step 6: Générer la migration**

Trouver la tête Alembic courante :

Run: `cd backend && ./venv/bin/alembic heads`

Créer `backend/alembic/versions/<rev>_add_access_request.py` (calqué sur `alembic/versions/99fe683ffb98_add_feedback.py`), avec `down_revision` = la tête retournée ci-dessus, un `revision` neuf (12 hex), et :

```python
def upgrade() -> None:
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_access_requests_email", "access_requests", ["email"])
    op.create_index(
        "ix_access_requests_created_at", "access_requests", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_access_requests_created_at", table_name="access_requests")
    op.drop_index("ix_access_requests_email", table_name="access_requests")
    op.drop_table("access_requests")
```

- [ ] **Step 7: Vérifier la migration contre Postgres**

Run: `docker compose up -d --build backend && docker logs search-backend-1 --tail 30`
Expected: le log montre `alembic upgrade head` sans erreur ; `curl -s http://localhost:8000/health` → 200.
Vérifier la table : `docker exec search-db-1 psql -U postgres -d ats_diagnostic -c "\d access_requests"`

- [ ] **Step 8: Suite complète + commit**

Run: `cd backend && ./venv/bin/pytest -q`
Expected: PASS (tout vert, +2 tests).

```bash
git add backend/app/models/access_request.py backend/app/models/__init__.py \
  backend/alembic/versions/*_add_access_request.py backend/tests/models/test_access_request.py
git commit -m "$(cat <<'EOF'
feat(access-request): modèle AccessRequest + migration

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QvHhwKEBXa6Y2M99QcXF4v
EOF
)"
```

---

## Task 3: Endpoint public `POST /access-requests`

**Files:**
- Create: `backend/app/schemas/access_request.py`
- Create: `backend/app/routers/access_requests.py`
- Modify: `backend/app/rate_limit/auth_throttle.py:8-13`
- Modify: `backend/app/notifications/resend_client.py`
- Modify: `backend/app/main.py:103-115`
- Test: `backend/tests/routers/test_access_requests.py`

**Interfaces:**
- Consumes: `AccessRequest` (Task 2) ; `app.auth.http.client_ip(request) -> str` ; `app.rate_limit.auth_throttle.check_auth_throttle(db, *, action, identifier)` / `record_auth_attempt(...)` / `AuthThrottleExceeded` ; `app.notifications.resend_client.EmailSendError`.
- Produces:
  - `app.schemas.access_request.AccessRequestIn` : `email: EmailStr`, `note: str = ""` (`max_length=1000`), `company: str = ""` (honeypot).
  - `app.schemas.access_request.AdminAccessRequestOut` : `id: int`, `email: str`, `note: str`, `created_at: str`, `handled_at: str | None`.
  - `app.notifications.resend_client.send_access_request_notification(admin_email: str, from_email: str, note: str) -> None`.
  - Route `POST /access-requests` → `204` toujours (sauf `422` validation, `429` throttle).
  - Entrée `_LIMITS["access_request"] = (5, timedelta(minutes=60))`.

- [ ] **Step 1: Écrire les tests de l'endpoint**

`backend/tests/routers/test_access_requests.py` :

```python
import pytest

from app.models.access_request import AccessRequest


def _payload(**over):
    base = {"email": "cand@example.com", "note": "dev backend, dispo tout de suite"}
    base.update(over)
    return base


def test_valid_request_stores_row_and_returns_204(client, db_session, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_notification",
        lambda *a, **k: calls.append((a, k)),
    )
    resp = client.post("/access-requests", json=_payload(email="CAND@Example.com  "))
    assert resp.status_code == 204
    row = db_session.query(AccessRequest).one()
    assert row.email == "cand@example.com"  # normalisé minuscule + trim
    assert row.note == "dev backend, dispo tout de suite"
    assert row.handled_at is None
    assert len(calls) == 1


def test_honeypot_filled_is_silently_dropped(client, db_session):
    resp = client.post("/access-requests", json=_payload(company="Acme Corp"))
    assert resp.status_code == 204
    assert db_session.query(AccessRequest).count() == 0


def test_invalid_email_is_422(client):
    assert client.post("/access-requests", json=_payload(email="pas-un-email")).status_code == 422


def test_note_too_long_is_422(client):
    assert client.post("/access-requests", json=_payload(note="x" * 1001)).status_code == 422


def test_rate_limited_after_5_in_an_hour(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_notification",
        lambda *a, **k: None,
    )
    for i in range(5):
        assert client.post("/access-requests", json=_payload(email=f"u{i}@e.com")).status_code == 204
    resp = client.post("/access-requests", json=_payload(email="u6@e.com"))
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "rate_limited"


def test_email_failure_does_not_break_request(client, db_session, monkeypatch):
    def boom(*a, **k):
        from app.notifications.resend_client import EmailSendError
        raise EmailSendError("nope")
    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_notification", boom
    )
    resp = client.post("/access-requests", json=_payload())
    assert resp.status_code == 204
    assert db_session.query(AccessRequest).count() == 1


def test_no_admin_email_configured_still_204(client, db_session, monkeypatch):
    # send_access_request_notification est appelée mais no-op si admin_email vide ;
    # ici on la laisse s'exécuter réellement (settings.admin_notify_email == "").
    resp = client.post("/access-requests", json=_payload())
    assert resp.status_code == 204
    assert db_session.query(AccessRequest).count() == 1
```

- [ ] **Step 2: Lancer — échec attendu**

Run: `cd backend && ./venv/bin/pytest tests/routers/test_access_requests.py -v`
Expected: FAIL — 404 sur `/access-requests` (route absente).

- [ ] **Step 3: Ajouter l'entrée de throttle**

Dans `backend/app/rate_limit/auth_throttle.py`, `_LIMITS` :

```python
_LIMITS: dict[str, tuple[int, timedelta]] = {
    "login": (8, timedelta(minutes=15)),
    "register": (5, timedelta(minutes=60)),
    "forgot_password": (5, timedelta(minutes=60)),
    "access_request": (5, timedelta(minutes=60)),
}
```

- [ ] **Step 4: Ajouter la fonction de notification**

Dans `backend/app/notifications/resend_client.py`, après `send_feedback_notification` :

```python
def send_access_request_notification(
    admin_email: str, from_email: str, note: str
) -> None:
    """Notify the admin of a new beta access request from the landing page.
    No-op when no admin email is configured."""
    if not admin_email:
        return
    body = (
        f"<p><strong>Email :</strong> {html.escape(from_email)}</p>"
        f"<p><strong>Message :</strong></p>"
        f"<p>{html.escape(note) or '<em>(vide)</em>'}</p>"
    )
    _send_email(admin_email, "Nouvelle demande d'accès à la beta", body)
```

- [ ] **Step 5: Créer le schéma**

`backend/app/schemas/access_request.py` :

```python
from pydantic import BaseModel, EmailStr, Field


class AccessRequestIn(BaseModel):
    email: EmailStr
    note: str = Field(default="", max_length=1000)
    # Honeypot : un vrai humain laisse ce champ vide ; un bot le remplit.
    company: str = ""


class AdminAccessRequestOut(BaseModel):
    id: int
    email: str
    note: str
    created_at: str
    handled_at: str | None
```

- [ ] **Step 6: Créer le routeur**

`backend/app/routers/access_requests.py` :

```python
import logging

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.http import client_ip
from app.config import get_settings
from app.database import get_db
from app.models.access_request import AccessRequest
from app.notifications.resend_client import (
    EmailSendError,
    send_access_request_notification,
)
from app.rate_limit.auth_throttle import (
    AuthThrottleExceeded,
    check_auth_throttle,
    record_auth_attempt,
)
from app.schemas.access_request import AccessRequestIn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/access-requests", tags=["access-requests"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def create_access_request(
    payload: AccessRequestIn,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    # Honeypot rempli → on fait comme si de rien n'était (pas d'indice au bot).
    if payload.company.strip():
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    ip = client_ip(request)
    try:
        check_auth_throttle(db, action="access_request", identifier=ip)
    except AuthThrottleExceeded:
        return Response(
            content='{"detail":{"code":"rate_limited","message":"Trop de demandes. Réessaie plus tard."}}',
            media_type="application/json",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    record_auth_attempt(db, action="access_request", identifier=ip)

    db.add(
        AccessRequest(
            email=payload.email.strip().lower(),
            note=payload.note.strip()[:1000],
            source_ip=ip,
        )
    )
    db.commit()

    try:
        send_access_request_notification(
            get_settings().admin_notify_email, payload.email, payload.note
        )
    except EmailSendError:
        logger.exception("access request notification email failed")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

> Note : `EmailStr` n'expose pas `.strip()` directement sur tous les chemins — `payload.email` est déjà une `str` validée ici, donc `.strip().lower()` fonctionne. Si mypy proteste, `str(payload.email).strip().lower()`.

- [ ] **Step 7: Enregistrer le routeur**

Dans `backend/app/main.py`, à côté des autres `include_router` (après `feedback.router`) :

```python
from app.routers import access_requests  # avec les autres imports de routers
...
app.include_router(access_requests.router)
```

Placer `app.include_router(access_requests.router)` **avant** `register_exception_handlers(app)`.

- [ ] **Step 8: Lancer les tests — succès attendu**

Run: `cd backend && ./venv/bin/pytest tests/routers/test_access_requests.py -v`
Expected: PASS (7 tests).

- [ ] **Step 9: Suite complète + lint**

Run: `cd backend && ./venv/bin/pytest -q && ./venv/bin/ruff check app tests && ./venv/bin/ruff format --check app tests`
Expected: PASS.

- [ ] **Step 10: Vérif Docker**

Run: `docker compose up -d --build backend && docker logs search-backend-1 --tail 20`
Puis : `curl -s -X POST http://localhost:8000/access-requests -H 'content-type: application/json' -d '{"email":"test@example.com","note":"hello"}' -i | head -1`
Expected: `HTTP/1.1 204 No Content`. Vérifier la ligne : `docker exec search-db-1 psql -U postgres -d ats_diagnostic -c "SELECT email, note FROM access_requests;"`

- [ ] **Step 11: Commit**

```bash
git add backend/app/schemas/access_request.py backend/app/routers/access_requests.py \
  backend/app/rate_limit/auth_throttle.py backend/app/notifications/resend_client.py \
  backend/app/main.py backend/tests/routers/test_access_requests.py
git commit -m "$(cat <<'EOF'
feat(access-request): endpoint public POST /access-requests (honeypot + throttle + notif)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QvHhwKEBXa6Y2M99QcXF4v
EOF
)"
```

---

## Task 4: Endpoints admin des demandes d'accès

**Files:**
- Modify: `backend/app/routers/admin.py`
- Modify: `backend/app/schemas/admin.py`
- Test: `backend/tests/routers/test_admin_access_requests.py`

**Interfaces:**
- Consumes: `AccessRequest` (Task 2) ; `AdminAccessRequestOut` (Task 3) ; helpers existants `_iso()`, `get_current_admin` (déjà appliqué au routeur `admin`).
- Produces:
  - `GET /admin/access-requests` (query `pending: bool = False`) → `list[AdminAccessRequestOut]`, tri `created_at` desc.
  - `POST /admin/access-requests/{request_id}/handled` → `204` ; pose `handled_at` si absent (idempotent) ; `404` si inconnu.

- [ ] **Step 1: Écrire les tests**

`backend/tests/routers/test_admin_access_requests.py` (réutilise les fixtures `admin_headers` / `user_headers` — les copier depuis `tests/routers/test_admin.py`, elles sont locales par fichier) :

```python
import pytest

from app.models.access_request import AccessRequest
from app.models.user import User
from scripts.invites import generate_codes


@pytest.fixture()
def admin_headers(client, db_session):
    (code,) = generate_codes(db_session, count=1, note="admin")
    client.post(
        "/auth/register",
        json={"email": "admin@e.com", "password": "s3cret!1",
              "invite_code": code, "accept_terms": True},
    )
    db_session.query(User).filter_by(email="admin@e.com").update({"is_admin": True})
    db_session.commit()
    token = client.post(
        "/auth/login", data={"username": "admin@e.com", "password": "s3cret!1"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_headers(client, db_session):
    (code,) = generate_codes(db_session, count=1, note="u")
    client.post(
        "/auth/register",
        json={"email": "u@e.com", "password": "s3cret!1",
              "invite_code": code, "accept_terms": True},
    )
    token = client.post(
        "/auth/login", data={"username": "u@e.com", "password": "s3cret!1"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed(db_session, n=3):
    for i in range(n):
        db_session.add(AccessRequest(email=f"c{i}@e.com", note=f"note {i}"))
    db_session.commit()


def test_list_requires_admin(client, user_headers):
    assert client.get("/admin/access-requests", headers=user_headers).status_code == 403


def test_list_returns_all_desc(client, db_session, admin_headers):
    _seed(db_session)
    rows = client.get("/admin/access-requests", headers=admin_headers).json()
    assert [r["email"] for r in rows] == ["c2@e.com", "c1@e.com", "c0@e.com"]


def test_list_pending_filters_handled(client, db_session, admin_headers):
    _seed(db_session, 2)
    first = db_session.query(AccessRequest).order_by(AccessRequest.id).first()
    client.post(f"/admin/access-requests/{first.id}/handled", headers=admin_headers)
    rows = client.get("/admin/access-requests?pending=true", headers=admin_headers).json()
    assert len(rows) == 1
    assert rows[0]["email"] == "c1@e.com"


def test_mark_handled_sets_timestamp_and_is_idempotent(client, db_session, admin_headers):
    _seed(db_session, 1)
    rid = db_session.query(AccessRequest).one().id
    assert client.post(f"/admin/access-requests/{rid}/handled", headers=admin_headers).status_code == 204
    db_session.expire_all()
    first_ts = db_session.query(AccessRequest).one().handled_at
    assert first_ts is not None
    assert client.post(f"/admin/access-requests/{rid}/handled", headers=admin_headers).status_code == 204
    db_session.expire_all()
    assert db_session.query(AccessRequest).one().handled_at == first_ts


def test_mark_handled_unknown_id_404(client, admin_headers):
    assert client.post("/admin/access-requests/999/handled", headers=admin_headers).status_code == 404
```

- [ ] **Step 2: Lancer — échec attendu**

Run: `cd backend && ./venv/bin/pytest tests/routers/test_admin_access_requests.py -v`
Expected: FAIL — 404 sur les routes admin.

- [ ] **Step 3: Ré-exporter le schéma**

Dans `backend/app/schemas/admin.py`, ajouter `from app.schemas.access_request import AdminAccessRequestOut` (ou dupliquer la classe si le fichier n'importe pas d'autres schémas — vérifier le style du fichier ; l'import est préférable). S'assurer que `admin.py` (routeur) peut faire `from app.schemas.admin import ... AdminAccessRequestOut ...`.

- [ ] **Step 4: Ajouter les endpoints**

Dans `backend/app/routers/admin.py`, ajouter les imports `from app.models.access_request import AccessRequest` et `AdminAccessRequestOut` dans le bloc `from app.schemas.admin import (...)`. Puis, à la fin du fichier :

```python
@router.get("/access-requests", response_model=list[AdminAccessRequestOut])
def list_access_requests(
    pending: bool = False, db: Session = Depends(get_db)
) -> list[AdminAccessRequestOut]:
    stmt = select(AccessRequest).order_by(AccessRequest.created_at.desc())
    if pending:
        stmt = stmt.where(AccessRequest.handled_at.is_(None))
    return [
        AdminAccessRequestOut(
            id=r.id,
            email=r.email,
            note=r.note,
            created_at=_iso(r.created_at) or "",
            handled_at=_iso(r.handled_at),
        )
        for r in db.scalars(stmt)
    ]


@router.post(
    "/access-requests/{request_id}/handled",
    status_code=status.HTTP_204_NO_CONTENT,
)
def mark_access_request_handled(
    request_id: int, db: Session = Depends(get_db)
) -> Response:
    row = db.get(AccessRequest, request_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Demande introuvable."
        )
    if row.handled_at is None:
        row.handled_at = utcnow()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Lancer les tests — succès attendu**

Run: `cd backend && ./venv/bin/pytest tests/routers/test_admin_access_requests.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Suite complète + lint + commit**

Run: `cd backend && ./venv/bin/pytest -q && ./venv/bin/ruff check app tests && ./venv/bin/ruff format --check app tests`
Expected: PASS.

```bash
git add backend/app/routers/admin.py backend/app/schemas/admin.py \
  backend/tests/routers/test_admin_access_requests.py
git commit -m "$(cat <<'EOF'
feat(admin): endpoints de consultation des demandes d'accès

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QvHhwKEBXa6Y2M99QcXF4v
EOF
)"
```

---

## Task 5: Frontend — API + onglet admin « Demandes d'accès »

**Files:**
- Modify: `frontend/lib/api.ts` (helper `requestAccess` + bloc `admin`)
- Modify: `frontend/lib/types.ts`
- Create: `frontend/components/admin/AccessRequestsTab.tsx`
- Modify: `frontend/app/(app)/admin/page.tsx`

**Interfaces:**
- Consumes: `POST /access-requests`, `GET /admin/access-requests`, `POST /admin/access-requests/{id}/handled` (Tasks 3-4) ; `request<T>()` de `lib/api.ts` (token optionnel — un appel sans token n'envoie pas d'`Authorization`).
- Produces:
  - `frontend/lib/types.ts` : `interface AdminAccessRequest { id: number; email: string; note: string; created_at: string; handled_at: string | null }`.
  - `frontend/lib/api.ts` : `export async function requestAccess(email: string, note: string): Promise<void>` ; `admin.getAccessRequests(token, pendingOnly?: boolean): Promise<AdminAccessRequest[]>` ; `admin.markAccessRequestHandled(token, id: number): Promise<void>`.
  - `frontend/components/admin/AccessRequestsTab.tsx` : `export function AccessRequestsTab(): JSX.Element`.

- [ ] **Step 1: Type `AdminAccessRequest`**

Dans `frontend/lib/types.ts`, après `AdminFeedback` :

```ts
export interface AdminAccessRequest {
  id: number;
  email: string;
  note: string;
  created_at: string;
  handled_at: string | null;
}
```

- [ ] **Step 2: `requestAccess` + méthodes admin dans `lib/api.ts`**

Ajouter l'import du type dans le bloc d'imports de types en tête de fichier (`type AdminAccessRequest`).

Fonction publique (près des autres exports de haut niveau, par ex. après le bloc `/* ─── Auth ─── */` ou dans une section `/* ─── Access requests ─── */`) :

```ts
/* ─── Demande d'accès (public, sans token) ─── */
export async function requestAccess(email: string, note: string): Promise<void> {
  await request<void>("/access-requests", {
    method: "POST",
    body: JSON.stringify({ email, note, company: "" }),
  });
}
```

Dans `export const admin = { ... }`, ajouter :

```ts
  getAccessRequests: (
    token: string,
    pendingOnly = false
  ): Promise<AdminAccessRequest[]> =>
    request<AdminAccessRequest[]>(
      `/admin/access-requests${pendingOnly ? "?pending=true" : ""}`,
      {},
      token
    ),

  markAccessRequestHandled: (token: string, id: number): Promise<void> =>
    request<void>(
      `/admin/access-requests/${id}/handled`,
      { method: "POST" },
      token
    ),
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: PASS.

- [ ] **Step 4: Créer `AccessRequestsTab.tsx`**

`frontend/components/admin/AccessRequestsTab.tsx` — calqué sur `components/admin/FeedbackTab.tsx` :

```tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Copy } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { admin } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { AdminAccessRequest } from "@/lib/types";

export function AccessRequestsTab() {
  const { token } = useAuth();
  const [items, setItems] = useState<AdminAccessRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    admin
      .getAccessRequests(token)
      .then(setItems)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Erreur de chargement.")
      );
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const sorted = useMemo(() => {
    if (!items) return null;
    return [...items].sort((a, b) => {
      if (!!a.handled_at !== !!b.handled_at) return a.handled_at ? 1 : -1;
      return b.created_at.localeCompare(a.created_at);
    });
  }, [items]);

  const markHandled = async (id: number) => {
    if (!token) return;
    try {
      await admin.markAccessRequestHandled(token, id);
      setItems(
        (prev) =>
          prev?.map((r) =>
            r.id === id ? { ...r, handled_at: new Date().toISOString() } : r
          ) ?? prev
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec.");
    }
  };

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!sorted) return <p className="text-sm text-muted-foreground">Chargement…</p>;
  if (sorted.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucune demande d&apos;accès pour l&apos;instant.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {sorted.map((r) => (
        <Card key={r.id} className={cn(r.handled_at && "opacity-60")}>
          <CardContent className="space-y-2 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs text-muted-foreground">
                <button
                  type="button"
                  onClick={() => navigator.clipboard?.writeText(r.email)}
                  className="inline-flex items-center gap-1 font-medium text-foreground hover:underline"
                  title="Copier l'email"
                >
                  {r.email}
                  <Copy className="h-3 w-3" />
                </button>
                {" · "}
                {formatRelativeTime(r.created_at)}
              </div>
              {r.handled_at ? (
                <span className="flex items-center gap-1 text-xs text-success">
                  <Check className="h-3.5 w-3.5" /> Traité
                </span>
              ) : (
                <Button size="sm" variant="outline" onClick={() => markHandled(r.id)}>
                  Marquer traité
                </Button>
              )}
            </div>
            {r.note && (
              <p className="whitespace-pre-wrap text-sm text-foreground">{r.note}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

> Le bouton « copier l'email » remplace le « Générer un code » : le flux reste manuel (l'admin colle l'email dans l'onglet Invitations comme note). Simple, pas de couplage inter-onglets.

- [ ] **Step 5: Brancher l'onglet dans `admin/page.tsx`**

Dans `frontend/app/(app)/admin/page.tsx` :
- Import : `import { AccessRequestsTab } from "@/components/admin/AccessRequestsTab";` et ajouter `Inbox` à l'import lucide.
- `type Tab = "overview" | "users" | "invites" | "access" | "feedback";`
- Dans `TABS`, insérer avant `feedback` : `{ id: "access", label: "Demandes d'accès", icon: Inbox },`
- Ajouter le rendu : `{tab === "access" && <AccessRequestsTab />}`

- [ ] **Step 6: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS.

- [ ] **Step 7: Vérif navigateur**

`docker compose up -d --build frontend`. Connecté en admin (`UPDATE users SET is_admin=true WHERE email='...'` si besoin), ouvrir `/admin` → onglet « Demandes d'accès ». Créer une demande via `curl` (voir Task 3 Step 10), recharger l'onglet : la ligne apparaît. Cliquer « Marquer traité » → passe en « Traité » et grisé. Recharger : l'état persiste.

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/api.ts frontend/lib/types.ts \
  frontend/components/admin/AccessRequestsTab.tsx frontend/app/\(app\)/admin/page.tsx frontend/AGENTS.md
git commit -m "$(cat <<'EOF'
feat(admin): onglet Demandes d'accès dans le dashboard admin

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QvHhwKEBXa6Y2M99QcXF4v
EOF
)"
```

---

## Task 6: La landing publique

**Files:**
- Modify: `frontend/app/page.tsx` (réécriture complète)
- Create: `frontend/app/opengraph-image.tsx`
- Create: `frontend/components/marketing/MarketingHeader.tsx`
- Create: `frontend/components/marketing/Hero.tsx`
- Create: `frontend/components/marketing/UiMockup.tsx`
- Create: `frontend/components/marketing/ProblemSection.tsx`
- Create: `frontend/components/marketing/FeatureGrid.tsx`
- Create: `frontend/components/marketing/HowItWorks.tsx`
- Create: `frontend/components/marketing/AccessSection.tsx`
- Create: `frontend/components/marketing/AccessRequestForm.tsx`
- Create: `frontend/components/marketing/MarketingFooter.tsx`

**Interfaces:**
- Consumes: `requestAccess()` (Task 5) ; `lib/brand.ts` (Task 1) ; `Logo` (Task 1) ; `components/ui/{Button,Input,Textarea,Card}` ; `toast` de `sonner` (déjà utilisé — vérifier l'import exact dans un composant existant, ex. `components/feedback/FeedbackButton.tsx`).
- Produces: la route `/` rend la landing pour un visiteur anonyme.

- [ ] **Step 1: Lire les guides Next**

Lire `frontend/node_modules/next/dist/docs/01-app/01-getting-started/14-metadata-and-og-images.md` en entier (métadonnées statiques + `opengraph-image.tsx` via `ImageResponse` / `next/og`), et parcourir `.../03-api-reference/03-file-conventions/01-metadata/` pour la forme de l'objet `Metadata` (champ `robots`, `openGraph`). Repérer un composant client existant qui importe `toast` (`grep -rn "from \"sonner\"" frontend/components`).

- [ ] **Step 2: `AccessRequestForm.tsx` (le cœur interactif)**

`frontend/components/marketing/AccessRequestForm.tsx` :

```tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { requestAccess } from "@/lib/api";

export function AccessRequestForm() {
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [company, setCompany] = useState(""); // honeypot
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      toast.error("Indique ton email.");
      return;
    }
    setSubmitting(true);
    try {
      await requestAccess(email.trim(), note.trim());
      setDone(true);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Une erreur est survenue. Réessaie."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="rounded-2xl border border-success/30 bg-success/10 p-6 text-center">
        <p className="font-display text-lg font-semibold text-foreground">
          Merci, c&apos;est noté.
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          On te recontacte dès qu&apos;une place se libère.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {/* Honeypot : hors écran, jamais display:none seul, invisible aux humains */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-[-9999px] h-0 w-0 overflow-hidden"
      >
        <label>
          Entreprise
          <input
            type="text"
            tabIndex={-1}
            autoComplete="off"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
        </label>
      </div>

      <Input
        label="Ton email"
        type="email"
        placeholder="prenom.nom@exemple.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <Textarea
        label="Où en es-tu dans ta recherche ? (optionnel)"
        placeholder="Ex : développeur back-end à Dakar, en poste, je regarde ailleurs."
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={3}
      />
      <Button type="submit" variant="primary" size="lg" fullWidth isLoading={submitting}>
        Demander un accès
      </Button>
      <p className="text-center text-xs text-muted-foreground">
        Beta fermée — on ouvre l&apos;accès progressivement.
      </p>
    </form>
  );
}
```

> Vérifier les props réelles de `Input` / `Textarea` / `Button` (`label`, `isLoading`, `fullWidth`, `variant`, `size`) dans `components/ui/` — le `login/page.tsx` les utilise déjà ainsi, mais confirmer `Textarea` accepte `label` et `rows`.

- [ ] **Step 3: `UiMockup.tsx` (visuel du hero, pur présentational)**

`frontend/components/marketing/UiMockup.tsx` — reprend le vocabulaire visuel de la carte flottante de `login/page.tsx` (score, offre, barre). Statique, HTML/CSS uniquement, `aria-hidden`.

```tsx
export function UiMockup() {
  return (
    <div
      aria-hidden="true"
      className="glass rounded-3xl border border-border/60 p-5 shadow-2xl"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground">
          Score de compatibilité
        </span>
        <span className="rounded-full bg-success px-2 py-0.5 text-xs font-bold text-white">
          92%
        </span>
      </div>
      <p className="mt-2 text-sm font-medium text-foreground">
        Développeur back-end · Sonatel (Dakar)
      </p>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full w-[92%] rounded-full bg-gradient-to-r from-primary-600 to-accent" />
      </div>
      <div className="mt-4 space-y-2 border-t border-border/60 pt-4">
        <p className="text-xs font-semibold text-muted-foreground">
          Mots-clés manquants sur ton CV
        </p>
        <div className="flex flex-wrap gap-1.5">
          {["CI/CD", "PostgreSQL", "REST", "Docker"].map((k) => (
            <span
              key={k}
              className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
            >
              {k}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Les sections présentational**

Créer les composants suivants (server components, pas de `"use client"`), en s'appuyant sur `lib/brand.ts` et le design system. Contenu FR exact ci-dessous.

`MarketingHeader.tsx` :
```tsx
import Link from "next/link";
import { Logo } from "@/components/common/Logo";

export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-2 sm:gap-3">
          <Link
            href="/login"
            className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            Se connecter
          </Link>
          <a
            href="#acces"
            className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground shadow-soft hover:bg-primary-600"
          >
            Demander un accès
          </a>
        </nav>
      </div>
    </header>
  );
}
```

`Hero.tsx` :
```tsx
import Link from "next/link";
import { TAGLINE } from "@/lib/brand";
import { UiMockup } from "./UiMockup";

export function Hero() {
  return (
    <section className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:items-center lg:py-24">
      <div>
        <h1 className="font-display text-4xl font-bold leading-tight text-foreground sm:text-5xl">
          {TAGLINE}
        </h1>
        <p className="mt-5 text-base text-muted-foreground sm:text-lg">
          Analyse ATS de ton CV, offres locales scorées pour ton profil, CV et
          lettres générés par IA, préparation d&apos;entretien : tout au même
          endroit.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <a
            href="#acces"
            className="rounded-xl bg-primary px-6 py-3 text-center text-sm font-semibold text-primary-foreground shadow-soft hover:bg-primary-600"
          >
            Demander un accès
          </a>
          <Link
            href="/login"
            className="rounded-xl border border-border px-6 py-3 text-center text-sm font-semibold text-foreground hover:bg-muted/60"
          >
            J&apos;ai un code — me connecter
          </Link>
        </div>
      </div>
      <div className="lg:pl-8">
        <UiMockup />
      </div>
    </section>
  );
}
```

`ProblemSection.tsx` :
```tsx
export function ProblemSection() {
  return (
    <section className="border-y border-border/60 bg-muted/30">
      <div className="mx-auto max-w-3xl px-4 py-14 text-center sm:px-6">
        <p className="font-display text-xl font-semibold text-foreground sm:text-2xl">
          Chercher un emploi à Dakar, c&apos;est des offres éparpillées sur dix
          sites, un CV jamais adapté au poste, et des entretiens préparés à
          l&apos;aveugle.
        </p>
        <p className="mt-3 text-sm text-muted-foreground">
          On a construit l&apos;outil qu&apos;on aurait voulu avoir.
        </p>
      </div>
    </section>
  );
}
```

`FeatureGrid.tsx` (icônes lucide : `ScanSearch`, `MapPin`, `FileText`, `MessagesSquare`) :
```tsx
import { ScanSearch, MapPin, FileText, MessagesSquare } from "lucide-react";

const FEATURES = [
  {
    icon: ScanSearch,
    title: "Diagnostic ATS instantané",
    body: "Score de lisibilité de ton CV et liste des mots-clés manquants, en quelques secondes.",
  },
  {
    icon: MapPin,
    title: "Offres locales, scorées pour toi",
    body: "Emploi Dakar, France Travail, offres remote… agrégées, avec un score de compatibilité par offre.",
  },
  {
    icon: FileText,
    title: "CV & lettre générés par IA",
    body: "Personnalisés pour l'offre visée, éditables, transparents sur ce qui a été modifié.",
  },
  {
    icon: MessagesSquare,
    title: "Préparation d'entretien IA",
    body: "Questions probables, recherche sur l'entreprise, checklist de coaching avant le jour J.",
  },
];

export function FeatureGrid() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <h2 className="font-display text-2xl font-bold text-foreground sm:text-3xl">
        Ce que tu peux faire
      </h2>
      <div className="mt-8 grid gap-5 sm:grid-cols-2">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <div key={title} className="rounded-2xl border border-border/60 bg-card p-6">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Icon className="h-5 w-5" />
            </span>
            <h3 className="mt-4 font-display text-lg font-semibold text-foreground">
              {title}
            </h3>
            <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
```

`HowItWorks.tsx` :
```tsx
const STEPS = [
  { n: 1, title: "Dépose ton CV", body: "Un PDF suffit. On l'analyse immédiatement." },
  { n: 2, title: "Reçois ton diagnostic et tes offres", body: "Score ATS, mots-clés manquants, et les offres locales compatibles avec ton profil." },
  { n: 3, title: "Postule mieux", body: "Génère un CV et une lettre adaptés à chaque offre, prépare l'entretien, suis tes candidatures." },
];

export function HowItWorks() {
  return (
    <section className="border-t border-border/60 bg-muted/30">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="font-display text-2xl font-bold text-foreground sm:text-3xl">
          Comment ça marche
        </h2>
        <div className="mt-8 grid gap-6 sm:grid-cols-3">
          {STEPS.map(({ n, title, body }) => (
            <div key={n}>
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary font-display text-sm font-bold text-primary-foreground">
                {n}
              </span>
              <h3 className="mt-3 font-display text-lg font-semibold text-foreground">
                {title}
              </h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
```

`AccessSection.tsx` :
```tsx
import { AccessRequestForm } from "./AccessRequestForm";

export function AccessSection() {
  return (
    <section id="acces" className="mx-auto max-w-lg px-4 py-20 sm:px-6">
      <div className="text-center">
        <h2 className="font-display text-2xl font-bold text-foreground sm:text-3xl">
          Rejoindre la beta
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          On ouvre l&apos;accès progressivement à un petit groupe de chercheurs
          d&apos;emploi à Dakar. Laisse-nous ton email.
        </p>
      </div>
      <div className="relative mt-8">
        <AccessRequestForm />
      </div>
    </section>
  );
}
```

`MarketingFooter.tsx` :
```tsx
import { PARENT_NAME, PARENT_URL, CONTACT_EMAIL } from "@/lib/brand";

export function MarketingFooter() {
  return (
    <footer className="border-t border-border/60 bg-card">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>
          Un produit{" "}
          <a href={PARENT_URL} className="font-medium text-foreground hover:underline" target="_blank" rel="noopener noreferrer">
            {PARENT_NAME}
          </a>{" "}
          · Version beta
        </p>
        <nav className="flex flex-wrap gap-x-4 gap-y-1">
          <a href="/conditions" className="hover:underline">Conditions d&apos;utilisation</a>
          <a href="/confidentialite" className="hover:underline">Politique de confidentialité</a>
          <a href={`mailto:${CONTACT_EMAIL}`} className="hover:underline">Contact</a>
        </nav>
      </div>
    </footer>
  );
}
```

- [ ] **Step 5: Réécrire `app/page.tsx`**

```tsx
import type { Metadata } from "next";
import { PRODUCT_NAME, TAGLINE } from "@/lib/brand";
import { MarketingHeader } from "@/components/marketing/MarketingHeader";
import { Hero } from "@/components/marketing/Hero";
import { ProblemSection } from "@/components/marketing/ProblemSection";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { AccessSection } from "@/components/marketing/AccessSection";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";

export const metadata: Metadata = {
  title: `${PRODUCT_NAME} — recherche d'emploi assistée par IA`,
  description: TAGLINE,
  robots: { index: false, follow: false },
  openGraph: {
    title: `${PRODUCT_NAME} — recherche d'emploi assistée par IA`,
    description: TAGLINE,
    type: "website",
    locale: "fr_FR",
  },
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <MarketingHeader />
      <main>
        <Hero />
        <ProblemSection />
        <FeatureGrid />
        <HowItWorks />
        <AccessSection />
      </main>
      <MarketingFooter />
    </div>
  );
}
```

> **Important** : `app/page.tsx` n'est plus `"use client"` et n'importe plus `useAuth`/`useRouter`. Le renvoi du visiteur connecté vers `/dashboard` est fait par `proxy.ts` (Task 7). Vérifier dans le guide Next qu'un `page.tsx` server component sous le root layout (qui, lui, est client via `AuthProvider`) est autorisé — ça l'est ; le layout reste un client boundary, la page peut être un RSC enfant.

- [ ] **Step 6: `opengraph-image.tsx`**

Suivre le guide lu au Step 1 (section OG image générée). `frontend/app/opengraph-image.tsx` :

```tsx
import { ImageResponse } from "next/og";
import { PRODUCT_NAME, TAGLINE } from "@/lib/brand";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 80,
          background: "linear-gradient(135deg, #4f46e5, #14b8a6)",
          color: "white",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ fontSize: 40, fontWeight: 700 }}>{PRODUCT_NAME}</div>
        <div style={{ fontSize: 60, fontWeight: 800, marginTop: 24, lineHeight: 1.1 }}>
          {TAGLINE}
        </div>
      </div>
    ),
    size
  );
}
```

> Si le guide indique une API différente en Next 16 (nom d'export, `next/og` vs `next/server`), suivre le guide.

- [ ] **Step 7: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS. Le build doit lister `/` comme route statique (ou dynamique si `opengraph-image` force le runtime — acceptable).

- [ ] **Step 8: Vérif navigateur réelle (critique)**

`docker compose up -d --build frontend`. Avec `claude-in-chrome` :
- **Anonyme** (pas de cookie / navigation privée) → `http://localhost:3000/` affiche la landing complète (header, hero + maquette, problème, 4 features, 3 étapes, formulaire, footer). Console **sans erreur**.
- **Viewport mobile** (~390 px) : pas de scroll horizontal, hero en une colonne (maquette sous le texte), features en une colonne, CTA header atteignables, formulaire utilisable.
- Le lien « Demander un accès » du header scrolle vers `#acces`.
- Soumettre le formulaire avec un vrai email → le formulaire est remplacé par le message de remerciement, pas d'erreur console, `POST /api/access-requests` → 204 dans l'onglet réseau.
- Ouvrir `/admin` (connecté admin) → la demande apparaît dans « Demandes d'accès ».
- POST direct avec honeypot rempli : `curl -s -X POST http://localhost:3000/api/access-requests -H 'content-type: application/json' -d '{"email":"bot@x.com","note":"x","company":"Acme"}' -i | head -1` → 204, et **aucune** nouvelle ligne en base (vérif SQL).
- Enregistrer un GIF de la soumission : `access_request_flow.gif`.

- [ ] **Step 9: Commit**

```bash
git add frontend/app/page.tsx frontend/app/opengraph-image.tsx \
  frontend/components/marketing/ frontend/AGENTS.md
git commit -m "$(cat <<'EOF'
feat(vitrine): landing publique sur / (présentation produit + demande d'accès)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QvHhwKEBXa6Y2M99QcXF4v
EOF
)"
```

---

## Task 7: Redirect du visiteur connecté + docs

**Files:**
- Modify: `frontend/proxy.ts`
- Modify: `docs/RUNBOOK.md` (§7 RGPD)
- Modify: `docs/CHECKLIST-LANCEMENT.md`

**Interfaces:**
- Consumes: rien de nouveau.
- Produces: `GET /` avec cookie `search_app_token` → `307` vers `/dashboard`.

- [ ] **Step 1: Lire le guide proxy**

Lire `frontend/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md` (sections *Matcher*, *NextResponse*). Confirmer qu'un `matcher` peut contenir `"/"` exact.

- [ ] **Step 2: Ajouter la règle dans `proxy.ts`**

Dans `frontend/proxy.ts`, dans la fonction `proxy`, **avant** le bloc `isProtectedPath` :

```ts
  // Visiteur déjà connecté qui arrive sur la vitrine → direct dans l'app.
  if (pathname === "/" && hasToken) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
```

Et ajouter `"/"` au tableau `config.matcher` :

```ts
export const config = {
  matcher: [
    "/",
    "/dashboard/:path*",
    // … reste inchangé
  ],
};
```

- [ ] **Step 3: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS.

- [ ] **Step 4: Vérif navigateur**

`docker compose up -d --build frontend`.
- **Connecté** : ouvrir `http://localhost:3000/` → redirigé immédiatement vers `/dashboard`, **sans** flash de la landing.
- **Anonyme** : `/` → la landing s'affiche (pas de redirect vers `/login`).
- Régression : `/login` connecté → toujours `/dashboard` ; `/dashboard` anonyme → toujours `/login?from=/dashboard`.

- [ ] **Step 5: RUNBOOK — purge `access_requests`**

Dans `docs/RUNBOOK.md`, section §7 (RGPD / suppression), ajouter :

```markdown
### Demandes d'accès (table `access_requests`)

Les demandes déposées depuis la landing ne sont pas rattachées à un compte.
Purge périodique des demandes non converties (> 90 j) :

    docker exec search-db-1 psql -U postgres -d ats_diagnostic -c \
      "DELETE FROM access_requests WHERE handled_at IS NULL AND created_at < now() - interval '90 days';"

Sur demande de suppression (droit à l'effacement) d'une personne qui avait
demandé un accès :

    docker exec search-db-1 psql -U postgres -d ats_diagnostic -c \
      "DELETE FROM access_requests WHERE email = 'la-personne@example.com';"
```

- [ ] **Step 6: CHECKLIST-LANCEMENT — ligne vitrine**

Dans `docs/CHECKLIST-LANCEMENT.md`, ajouter dans la section de vérification navigateur (ou une nouvelle sous-section « Landing publique ») :

```markdown
- [ ] `/` en anonyme affiche la landing (pas le formulaire de login), sur desktop **et** téléphone
- [ ] `/` en tant qu'utilisateur connecté redirige vers `/dashboard`
- [ ] le formulaire « Demander un accès » enregistre bien (visible dans /admin ▸ Demandes d'accès) et envoie l'email de notif à ADMIN_NOTIFY_EMAIL
- [ ] liens footer (Conditions, Confidentialité, Contact) fonctionnels
```

- [ ] **Step 7: Commit**

```bash
git add frontend/proxy.ts frontend/AGENTS.md docs/RUNBOOK.md docs/CHECKLIST-LANCEMENT.md
git commit -m "$(cat <<'EOF'
feat(vitrine): visiteur connecté sur / renvoyé vers /dashboard + docs

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QvHhwKEBXa6Y2M99QcXF4v
EOF
)"
```

---

## Task 8: Vérification bout-en-bout + revue

**Files:** aucun (sauf correctifs).

- [ ] **Step 1: Suite backend complète**

Run: `cd backend && ./venv/bin/pytest -q && ./venv/bin/ruff check app tests && ./venv/bin/ruff format --check app tests`
Expected: tout vert (≈ +15 tests vs point de départ).

- [ ] **Step 2: Frontend**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS.

- [ ] **Step 3: Parcours complet en navigateur (stack dockerisée à jour)**

`docker compose up -d --build`. Rejouer avec `claude-in-chrome` :
1. Anonyme `/` → landing OK desktop + mobile, console propre.
2. Formulaire demande d'accès → 204 + remerciement ; ligne dans `/admin`.
3. Honeypot → 204, rien en base.
4. 6ᵉ soumission rapide depuis la même IP → toast d'erreur « Trop de demandes ».
5. `/login` → panneau gauche affiche le nom produit, `/dashboard` sidebar sans « v3 ».
6. Connecté `/` → `/dashboard` sans flash.
7. Liens légaux + lien Yokkute Labs OK.

- [ ] **Step 4: Revue de code**

Invoquer `superpowers:requesting-code-review` sur le diff `feature/beta-launch..feature/site-vitrine`. Traiter les retours (patterns connus à surveiller : échappement HTML dans les emails, pas de secret loggé, `source_ip` non exposé côté client — `AdminAccessRequestOut` ne le contient pas, bien).

- [ ] **Step 5: Mémoire projet**

Mettre à jour `~/.claude/projects/-home-roland-Documents-Search/memory/talya_rebuild_project.md` : nouveau chantier « site vitrine » sur `feature/site-vitrine` (depuis `feature/beta-launch`), statut, `feature/talya-inspired-rebuild` supprimée, nom produit encore à choisir (décision différée, token `lib/brand.ts`).

---

## Self-Review

**1. Couverture spec :**

| Élément de spec | Tâche |
|---|---|
| `app/page.tsx` → server component landing | Task 6 |
| Visiteur connecté sur `/` → `/dashboard` (proxy) | Task 7 |
| `components/marketing/*` + `<Logo>` + `lib/brand.ts` | Tasks 1, 6 |
| Contenu 7 sections (header/hero/problème/features/how/access/footer) | Task 6 |
| Maquette UI stylisée (pas de capture) | Task 6 (`UiMockup`) |
| Identité visuelle produit (indigo/teal, Outfit/Inter, utilitaires) | Tasks 1, 6 (classes corrigées : `.gradient-hero`, `.gradient-text`) |
| `noindex` + metadata + OG | Task 6 |
| Modèle `AccessRequest` + migration | Task 2 |
| `POST /access-requests` public (honeypot, throttle 5/h, toujours 204, notif Resend non bloquante) | Task 3 |
| Endpoints admin + onglet `/admin` | Tasks 4, 5 |
| `requestAccess()` sans token | Task 5 |
| Retrait « v3 » + « Search » en dur → token | Task 1 |
| RGPD : purge `access_requests` au RUNBOOK | Task 7 |
| Tests backend (happy/honeypot/rate-limit/422/email-fail/admin) | Tasks 2-4 |
| Vérif navigateur réelle + mobile + GIF | Tasks 6, 8 |
| Séquencement en commits scopés | toutes |
| Ligne CHECKLIST-LANCEMENT | Task 7 |

Pas de trou identifié.

**2. Placeholders :** aucun `TBD`/`TODO` ; chaque étape de code porte le code réel. Les rares « vérifier X dans le guide/fichier » sont des contrôles d'exactitude Next 16 explicitement demandés par les contraintes du projet, pas des blancs.

**3. Cohérence des types :**
- `AccessRequestIn` (`email`, `note`, `company`) — cohérent Tasks 3, 5, 6.
- `AdminAccessRequestOut` (`id`, `email`, `note`, `created_at: str`, `handled_at: str | null`) — défini Task 3, consommé Tasks 4, 5 ; le type frontend `AdminAccessRequest` (Task 5) a la même forme.
- `send_access_request_notification(admin_email, from_email, note)` — signature identique Task 3 (définition) et Task 3 Step 6 (appel).
- `requestAccess(email, note)` / `admin.getAccessRequests(token, pendingOnly?)` / `admin.markAccessRequestHandled(token, id)` — définis Task 5, consommés Tasks 5, 6.
- `_LIMITS["access_request"]` — ajouté Task 3, utilisé implicitement par `check_auth_throttle` Task 3.
- `Logo({ className?, wordmark? })` — défini Task 1, utilisé Tasks 1 (Sidebar), 6 (MarketingHeader).

Cohérent.
