# Beta — Plan 7 : Feedback in-app, polish & vérification de lancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un bouton de feedback in-app relié à une table + une notification email, un handler d'erreurs global qui ne laisse jamais fuir de traceback, un bandeau beta, une passe sur les messages FR, puis la vérification de bout en bout et le passage de la checklist de lancement.

**Architecture:** `POST /feedback` (authentifié) écrit une ligne `Feedback` (modèle créé en Beta 6) et envoie une notification à `ADMIN_NOTIFY_EMAIL` via le client Resend existant. Un `<FeedbackButton />` flottant (modale `message` + `pathname` courant) est monté dans l'`AppShell`. Un `@app.exception_handler(Exception)` dans `main.py` renvoie un `500` générique FR + l'`event_id` GlitchTip ; les `HTTPException` explicites passent inchangées. Un `<BetaBanner />` dismissible (localStorage). Enfin : vérification navigateur réelle du parcours complet sur le serveur + `docs/CHECKLIST-LANCEMENT.md` coché.

**Tech Stack:** FastAPI, SQLAlchemy 2, Resend (déjà câblé), `sentry-sdk` (Beta 5), Next 16, `sonner` (déjà monté), pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-lancement-beta-design.md` — §8 (8.1 feedback, 8.2 handler d'erreurs, 8.3 bandeau beta, 8.4 états vides/erreurs, 8.5 amorçage) et §9.2 (checklist pré-lancement).

## Global Constraints

- **Branche** `feature/beta-launch`, jamais `main`. Commits scopés.
- **Requiert Beta 6** (modèle `Feedback`, `is_admin`, onglet Feedback de l'admin). Requiert Beta 5 (`sentry_sdk` pour l'`event_id`). Idéalement dernier plan exécuté.
- **Aucune migration** (le modèle `Feedback` vient de Beta 6).
- **Le handler global ne doit pas avaler les `HTTPException`** ni les `RequestValidationError` (422) — seulement les exceptions non gérées.
- **Messages FR**, aucun texte anglais visible à l'écran.
- **`requirements.txt`** : aucune nouvelle dépendance.
- **Après modif backend testée** : rebuild du conteneur backend.
- La **checklist de lancement (Task 6) est bloquante** : le beta ne s'ouvre pas tant qu'elle n'est pas entièrement cochée.

---

## File Structure

**Créés :**
- `backend/app/routers/feedback.py` — `POST /feedback`.
- `backend/app/schemas/feedback.py` — `FeedbackIn`.
- `backend/app/errors.py` — `register_exception_handlers(app)`.
- `backend/tests/routers/test_feedback.py`
- `backend/tests/test_error_handler.py`
- `frontend/components/feedback/FeedbackButton.tsx`
- `frontend/components/common/BetaBanner.tsx`
- `docs/CHECKLIST-LANCEMENT.md`

**Modifiés :**
- `backend/app/notifications/resend_client.py` — `send_feedback_notification(admin_email, from_user, page, message)`.
- `backend/app/config.py` — `admin_notify_email: str = ""`.
- `backend/app/main.py` — `register_exception_handlers(app)` + `app.include_router(feedback.router)`.
- `backend/.env.example` — `+ ADMIN_NOTIFY_EMAIL=`.
- `frontend/lib/api.ts` — `sendFeedback(token, page, message)`.
- `frontend/components/layout/AppShell.tsx` — monter `<FeedbackButton />` et `<BetaBanner />`.
- `docs/RUNBOOK.md` — pointeur vers la checklist + amorçage des crawlers.

---

## Task 1 : `POST /feedback` + notification

**Files:**
- Create: `backend/app/routers/feedback.py`, `backend/app/schemas/feedback.py`
- Modify: `backend/app/notifications/resend_client.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/.env.example`
- Test: `backend/tests/routers/test_feedback.py`

**Interfaces:**
- Produces:
  - `FeedbackIn { page: str (max 255), message: str (min 1, max 5000) }`.
  - `POST /feedback` (authentifié) → insère `Feedback(user_id=current_user.id, page=payload.page, message=payload.message)`, commit, puis `send_feedback_notification(...)` (échec loggé, non bloquant) → `204`.
  - `resend_client.send_feedback_notification(admin_email: str, from_user: str, page: str, message: str) -> None` — no-op si `admin_email` vide.

- [ ] **Step 1 : Tests qui échouent**

`backend/tests/routers/test_feedback.py` :

```python
import pytest

from scripts.invites import generate_codes


@pytest.fixture()
def authed(client, db_session):
    (code,) = generate_codes(db_session, count=1, note="t")
    client.post("/auth/register", json={
        "email": "u@e.com", "password": "s3cret!1", "invite_code": code, "accept_terms": True})
    token = client.post("/auth/login", data={"username": "u@e.com", "password": "s3cret!1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_feedback_requires_auth(client):
    assert client.post("/feedback", json={"page": "/offres", "message": "x"}).status_code == 401


def test_feedback_stores_row_and_notifies(client, db_session, authed, monkeypatch):
    calls = []
    monkeypatch.setattr("app.routers.feedback.send_feedback_notification",
                        lambda *a, **k: calls.append((a, k)))
    resp = client.post("/feedback", json={"page": "/offres", "message": "très utile"}, headers=authed)
    assert resp.status_code == 204
    from app.models.feedback import Feedback
    row = db_session.query(Feedback).one()
    assert row.message == "très utile" and row.page == "/offres" and row.user_id is not None
    assert len(calls) == 1


def test_feedback_empty_message_422(client, authed):
    assert client.post("/feedback", json={"page": "/x", "message": ""}, headers=authed).status_code == 422


def test_feedback_notification_failure_is_non_blocking(client, authed, monkeypatch):
    from app.notifications.resend_client import EmailSendError
    def _boom(*a, **k): raise EmailSendError("down")
    monkeypatch.setattr("app.routers.feedback.send_feedback_notification", _boom)
    assert client.post("/feedback", json={"page": "/x", "message": "y"}, headers=authed).status_code == 204
```

- [ ] **Step 2 : Vérifier l'échec** — 404.

- [ ] **Step 3 : Implémenter**

`schemas/feedback.py` : `class FeedbackIn(BaseModel): page: str = Field(max_length=255); message: str = Field(min_length=1, max_length=5000)`.

`config.py` : `admin_notify_email: str = ""`. `.env.example` : `ADMIN_NOTIFY_EMAIL=`.

`resend_client.py` :

```python
def send_feedback_notification(admin_email: str, from_user: str, page: str, message: str) -> None:
    if not admin_email:
        return
    body = (
        f"<p><strong>De :</strong> {html.escape(from_user)}</p>"
        f"<p><strong>Page :</strong> {html.escape(page)}</p>"
        f"<p>{html.escape(message)}</p>"
    )
    _send_email(admin_email, "Nouveau retour beta", body)
```

`routers/feedback.py` :

```python
import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.feedback import Feedback
from app.models.user import User
from app.notifications.resend_client import EmailSendError, send_feedback_notification
from app.schemas.feedback import FeedbackIn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def submit_feedback(payload: FeedbackIn, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)) -> Response:
    db.add(Feedback(user_id=current_user.id, page=payload.page, message=payload.message))
    db.commit()
    try:
        send_feedback_notification(
            get_settings().admin_notify_email, current_user.email, payload.page, payload.message
        )
    except EmailSendError:
        logger.exception("feedback notification email failed")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

`main.py` : `app.include_router(feedback.router)`.

- [ ] **Step 4 : Vérifier** — `pytest tests/routers/test_feedback.py -v` PASS ; `ruff check` ; `mypy`.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/routers/feedback.py backend/app/schemas/feedback.py backend/app/notifications/resend_client.py backend/app/config.py backend/app/main.py backend/.env.example backend/tests/routers/test_feedback.py
git commit -m "feat(feedback): POST /feedback stores a row + emails the admin"
```

---

## Task 2 : Handler d'erreurs global

**Files:**
- Create: `backend/app/errors.py`, `backend/tests/test_error_handler.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `register_exception_handlers(app: FastAPI) -> None` — enregistre **un seul** handler pour `Exception` :
  - capture via `sentry_sdk.capture_exception(exc)` → récupère `event_id` (`None` si Sentry non initialisé) ;
  - renvoie `JSONResponse(500, {"detail": "Une erreur est survenue. L'équipe a été notifiée.", "error_id": <event_id | null>})`.
  - Les `HTTPException` et `RequestValidationError` **ne sont pas** interceptées (FastAPI garde ses handlers par défaut : messages FR déjà en place, 422 de validation inchangé).

- [ ] **Step 1 : Tests qui échouent**

`backend/tests/test_error_handler.py` :

```python
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import register_exception_handlers


def _app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internals")

    @app.get("/teapot")
    def teapot():
        raise HTTPException(status_code=418, detail="Je suis une théière.")

    return app


def test_unhandled_exception_returns_generic_500():
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "Une erreur est survenue. L'équipe a été notifiée."
    assert "secret internals" not in resp.text
    assert "error_id" in body


def test_http_exception_is_untouched():
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/teapot")
    assert resp.status_code == 418
    assert resp.json()["detail"] == "Je suis une théière."
```

- [ ] **Step 2 : Vérifier l'échec** — `ModuleNotFoundError: app.errors`.

- [ ] **Step 3 : Implémenter `errors.py`**

```python
import logging

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        event_id = sentry_sdk.capture_exception(exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Une erreur est survenue. L'équipe a été notifiée.",
                "error_id": event_id,
            },
        )
```

- [ ] **Step 4 : Câbler dans `main.py`**

Après `app = FastAPI(...)` et les `include_router` : `from app.errors import register_exception_handlers` + `register_exception_handlers(app)`.

- [ ] **Step 5 : Vérifier**

Run: `cd backend && pytest tests/test_error_handler.py -q && pytest -q && ruff check app/ && mypy app`
Expected: suite complète verte (vérifier qu'aucun test existant ne comptait sur un `500` avec traceback).

- [ ] **Step 6 : Commit**

```bash
git add backend/app/errors.py backend/app/main.py backend/tests/test_error_handler.py
git commit -m "feat(errors): global handler — generic FR 500 + GlitchTip event id, HTTPException untouched"
```

---

## Task 3 : `<FeedbackButton />` + `<BetaBanner />`

**Files:**
- Create: `frontend/components/feedback/FeedbackButton.tsx`, `frontend/components/common/BetaBanner.tsx`
- Modify: `frontend/lib/api.ts`, `frontend/components/layout/AppShell.tsx`

**Interfaces:**
- Consumes: `POST /feedback`.
- Produces:
  - `api.sendFeedback(token: string, page: string, message: string): Promise<void>`.
  - `<FeedbackButton />` — bouton flottant bas-droite (au-dessus du `MobileNav`), ouvre une modale (`<Dialog>`), `textarea` + envoi ; `page` = `usePathname()` ; succès → `toast.success("Merci pour ton retour !")` + ferme.
  - `<BetaBanner />` — bandeau haut, dismissible, persistant `localStorage["beta_banner_dismissed"]`.

- [ ] **Step 1 : `lib/api.ts`**

```ts
export async function sendFeedback(token: string, page: string, message: string): Promise<void> {
  await request<void>("/feedback", { method: "POST", body: JSON.stringify({ page, message }) }, token);
}
```

- [ ] **Step 2 : `<BetaBanner />`** (`"use client"`)

```tsx
"use client";
import { useEffect, useState } from "react";
import { X } from "lucide-react";

const KEY = "beta_banner_dismissed";

export function BetaBanner() {
  const [hidden, setHidden] = useState(true);
  useEffect(() => {
    try { setHidden(localStorage.getItem(KEY) === "1"); } catch { setHidden(false); }
  }, []);
  if (hidden) return null;
  return (
    <div className="bg-primary-600 text-white text-xs px-4 py-2 flex items-center justify-between">
      <span>
        Version beta — certaines parties sont encore brutes. Un souci, une idée ?
        Utilise le bouton « Donner mon avis » ou le groupe WhatsApp.
      </span>
      <button aria-label="Fermer" onClick={() => { try { localStorage.setItem(KEY, "1"); } catch {} setHidden(true); }}>
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
```

- [ ] **Step 3 : `<FeedbackButton />`** (`"use client"`)

Bouton `fixed bottom-20 right-4 lg:bottom-4 z-40` (icône `MessageSquarePlus`), ouvre `<Dialog>` (réutiliser `@/components/ui/Dialog`), `textarea` (obligatoire), bouton « Envoyer » → `await sendFeedback(token, pathname, message)` → `toast.success(...)` + reset + close. Erreur → `toast.error("Échec de l'envoi, réessaie.")`. Ne rien afficher si `!token` (utilisateur non connecté).

- [ ] **Step 4 : Monter dans `AppShell`**

```tsx
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
        <BetaBanner />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <div className="flex flex-1 flex-col h-full min-w-0 overflow-hidden">
            <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-8 sm:py-8 pb-24 lg:pb-8 w-full max-w-6xl mx-auto">
              {children}
            </main>
          </div>
        </div>
        <MobileNav />
        <FeedbackButton />
      </div>
    </RequireAuth>
  );
}
```

(Adapter la structure flex existante — le point clé : `BetaBanner` en haut, `FeedbackButton` en overlay.)

- [ ] **Step 5 : Build + vérif navigateur**

Run: `cd frontend && npm run typecheck && npm run build`
Puis : le bandeau s'affiche au 1ᵉʳ chargement, se ferme et **reste fermé** après reload ; le bouton « Donner mon avis » ouvre la modale, l'envoi crée une ligne visible dans `/admin` (onglet Feedback) et un email arrive sur `ADMIN_NOTIFY_EMAIL`.

- [ ] **Step 6 : Commit**

```bash
git add frontend/lib/api.ts frontend/components/feedback/FeedbackButton.tsx frontend/components/common/BetaBanner.tsx frontend/components/layout/AppShell.tsx
git commit -m "feat(feedback): floating feedback button + dismissible beta banner"
```

---

## Task 4 : Passe messages FR / états vides / erreurs

**Files:**
- Modify: divers composants frontend (selon constats).

**Interfaces:** aucune nouvelle. Objectif : aucun texte anglais visible, aucun état vide sans message, aucune erreur brute affichée.

- [ ] **Step 1 : Recensement**

Run: `cd frontend && grep -rniE "error|failed|loading|no results|not found|something went wrong" app components --include=*.tsx | grep -v "// " | grep -vi "aria|className|isError|isLoading|onError|setError|hasError"`
Repérer les chaînes **affichées** (JSX text, `placeholder=`, `toast(...)`) qui sont en anglais. Les traduire.

- [ ] **Step 2 : États vides**

Vérifier qu'ont un message FR clair : recherche d'offres sans résultat ; liste de candidatures/Kanban vide ; `/admin` onglets vides ; upload de CV rejeté (422) ; source d'offres indisponible (`unavailable_sources`). Corriger les manquants (un `<p className="text-sm text-muted-foreground">` suffit).

- [ ] **Step 3 : Erreurs**

Vérifier que `request()` (Beta 3 Task 9) affiche `err.message` (jamais `[object Object]`), et que les pages catch → `toast.error` ou encart, jamais un `throw` non géré visible. Le `500` renvoie maintenant `detail` générique (Task 2) — s'assurer que les pages l'affichent tel quel.

- [ ] **Step 4 : Build + commit**

Run: `cd frontend && npm run typecheck && npm run build`

```bash
git add frontend/
git commit -m "polish: French copy pass on empty states, errors and placeholders"
```

---

## Task 5 : Amorçage des offres + section runbook

**Files:**
- Modify: `docs/RUNBOOK.md`

- [ ] **Step 1 : Ajouter au runbook**

```markdown
## Amorçage avant l'arrivée des testeurs

1. Lancer un crawl manuel :
   `docker compose -f docker-compose.prod.yml exec backend python -c "from app.database import SessionLocal; from app.job_search.crawl_runner import run_crawl; run_crawl(SessionLocal)"`
2. Vérifier : `docker compose ... exec db psql -U postgres -d ats_diagnostic -c "SELECT source, count(*) FROM crawled_listing WHERE is_active GROUP BY source;"` → Emploi Dakar présent.
3. Vérifier `ENABLED_CRAWLERS` (env) inclut `emploi_dakar` ; `RELIEFWEB_APPNAME` renseigné.
4. Depuis le navigateur, recherche « comptable » + « Dakar » → offres locales visibles et scorées.
```

- [ ] **Step 2 : Commit**

```bash
git add docs/RUNBOOK.md
git commit -m "docs(runbook): offer-seeding steps before onboarding testers"
```

---

## Task 6 : Vérification E2E + checklist de lancement (bloquant)

**Files:**
- Create: `docs/CHECKLIST-LANCEMENT.md`

**Interfaces:** aucune. Sortie : la checklist entièrement cochée, avec la date et l'opérateur.

- [ ] **Step 1 : Écrire `docs/CHECKLIST-LANCEMENT.md`**

```markdown
# Checklist de lancement — Beta yokkutelabs

À faire sur l'environnement de prod (`beta.yokkutelabs.com`), navigateur réel,
dont **au moins un passage complet depuis un téléphone**. Le beta ne s'ouvre
pas tant que tout n'est pas coché.

## Infra & accès
- [ ] `beta.` et `api.beta.` résolvent ; TLS valide (cadenas) sur les deux.
- [ ] `curl https://api.beta.yokkutelabs.com/health` → `{"status":"ok","db":"ok",...}`.
- [ ] `db` et `minio` ne sont pas joignables depuis l'extérieur.
- [ ] Requête `fetch` depuis une autre origine → bloquée par CORS.

## Auth
- [ ] Inscription **sans** code → refusée ; avec un code déjà utilisé → refusée.
- [ ] Inscription avec code + case de consentement cochée → OK ; `users.consent_version` renseigné.
- [ ] Cookie `search_app_token` : `Secure`, `HttpOnly`, `SameSite=Lax` (DevTools).
- [ ] « Mot de passe oublié » → email reçu → lien → nouveau mot de passe → login OK.
- [ ] 8 échecs de login → `429`.

## Parcours produit (téléphone)
- [ ] Inscription → onboarding → recherche → offres **sénégalaises** visibles.
- [ ] Diagnostic ATS → CV généré → lettre générée → prépa entretien.
- [ ] À la N+1ᵉ génération : encart « quota atteint » (pas une erreur rouge).
- [ ] `python -m scripts.llm_switch off` → une génération montre « en pause » (503 propre) ; `on` → rétabli.
- [ ] `/profil` montre les jauges d'utilisation.

## RGPD
- [ ] `/conditions` et `/confidentialite` accessibles sans être connecté, contenu validé (raison sociale, pays hébergeur, email de contact renseignés).
- [ ] « Exporter mes données » → JSON complet téléchargé.
- [ ] « Supprimer mon compte » (mot de passe) → login échoue ensuite ; lignes DB parties ; `mc ls local/personalization/users/<id>/` vide.

## Observabilité
- [ ] Erreur test backend → visible dans GlitchTip, **sans** contenu de CV.
- [ ] Erreur test frontend → visible dans GlitchTip.
- [ ] Uptime Kuma : `API health`, `Frontend`, `TLS` → tous verts ; une notification test reçue.

## Admin
- [ ] `/admin` accessible au compte admin ; `403` / redirection pour un compte normal ; pas d'entrée de nav « Admin » pour un non-admin.
- [ ] Générer 5 codes, en révoquer 1.
- [ ] Ajuster un quota d'un testeur → visible dans `/admin/users/{id}`.
- [ ] Onglet Feedback affiche un retour test.

## Sauvegardes
- [ ] `deploy/backup/pg_backup.sh` exécuté → fichier `.age` sur R2.
- [ ] `deploy/backup/minio_mirror.sh` exécuté → objets sur R2.
- [ ] **Restauration testée** sur base jetable → `SELECT count(*) FROM users` cohérent.
- [ ] Crons installés (`crontab -l`).

## Coûts
- [ ] Plafond de dépense mensuel posé dans la console Anthropic + alertes 50/80/100 %.

## Amorçage
- [ ] Crawl manuel lancé ; offres Emploi Dakar en base ; 1ʳᵉ recherche non vide.

## Feedback humain
- [ ] Groupe WhatsApp créé ; message d'accueil + pitch 3 lignes prêts.
- [ ] 5-10 codes attribués nominativement (tableau code ↔ personne).

---
Passée le : __________  par : __________
```

- [ ] **Step 2 : Exécuter la checklist**

Dérouler chaque case sur le serveur. Pour chaque échec : corriger (commit scopé sur `feature/beta-launch`), re-vérifier. Ne pas cocher une case non vérifiée.

- [ ] **Step 3 : Consigner**

Remplir la ligne « Passée le / par ». Commit.

```bash
git add docs/CHECKLIST-LANCEMENT.md
git commit -m "docs: launch checklist (run and signed off)"
```

- [ ] **Step 4 : Bilan**

Résumer à l'utilisateur : ce qui est vert, ce qui a dû être corrigé, et confirmer que le beta peut ouvrir. Le déroulé humain (recrutement, visio de lancement, suivi 3 semaines, doc de conclusions) est **hors code** — cf. spec §9.3.

---

## Self-Review

**Couverture du spec §8 + §9.2 :**

| Exigence | Task |
|---|---|
| §8.1 modèle `Feedback` | Beta 6 Task 2 (référencé) |
| §8.1 `POST /feedback` → table + notification Resend vers l'admin | Task 1 |
| §8.1 bouton flottant « Donner mon avis » + modale + `pathname` + toast | Task 3 |
| §8.1 groupe WhatsApp = canal async | checklist (Task 6) + spec §9.3 (hors code) |
| §8.2 `@app.exception_handler(Exception)` → 500 FR générique + id GlitchTip ; `HTTPException` inchangées | Task 2 |
| §8.3 bandeau beta dismissible (localStorage) au 1ᵉʳ login | Task 3 |
| §8.4 passe états vides / erreurs FR | Task 4 |
| §8.5 amorçage des crawlers avant les testeurs | Task 5 |
| §9.2 checklist pré-lancement (DNS/TLS, register+code, login/reset, CORS, cookie, parcours téléphone, quota, interrupteur, suppression, export, backup+restauration, Sentry, Kuma, plafond Anthropic, pages légales, feedback, `/admin`) | Task 6 |

**Placeholders :** aucun `TBD` de code. `docs/CHECKLIST-LANCEMENT.md` contient volontairement des cases à cocher (c'est son objet).

**Cohérence des noms :** `FeedbackIn`, `submit_feedback`, `send_feedback_notification`, `admin_notify_email` / `ADMIN_NOTIFY_EMAIL`, `register_exception_handlers` (`app/errors.py`), `sendFeedback` (frontend), `<FeedbackButton />`, `<BetaBanner />` (clé localStorage `beta_banner_dismissed`), route `POST /feedback`. Identiques entre tasks.

**Dépendances inter-plans :** Beta 6 (modèle `Feedback`, `/admin` onglet Feedback), Beta 5 (`sentry_sdk` pour `event_id` — `capture_exception` renvoie `None` sans init, géré). **À exécuter en dernier.**

**Ordre d'exécution :** 1 → 2 → 3 → 4 → 5 → 6. Task 6 est la porte de sortie du chantier beta.
