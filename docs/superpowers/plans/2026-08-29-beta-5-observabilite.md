# Beta — Plan 5 : Observabilité auto-hébergée — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Savoir quand l'application plante (suivi d'erreurs GlitchTip, compatible SDK Sentry) et quand elle est indisponible (Uptime Kuma), les deux auto-hébergés en Docker, sans exposer de surface publique et sans faire fuiter de CV vers l'outil de suivi.

**Architecture:** Un `docker-compose.monitoring.yml` séparé (démarrable/arrêtable sans toucher à l'app) lance GlitchTip (web + worker + migrate + son Postgres + Redis) et Uptime Kuma, tous liés au port `127.0.0.1` uniquement — accès par tunnel SSH. Le backend initialise `sentry-sdk[fastapi]` si `GLITCHTIP_DSN` est défini, avec un `before_send` qui supprime les corps de requête des routes traitant des CV et scrub les variables locales sensibles. Le frontend initialise `@sentry/nextjs` a minima (client + serveur, **sans** upload de source maps ni wrapper `withSentryConfig`, pour ne pas fragiliser le build Next 16 + Turbopack).

**Tech Stack:** Docker Compose, GlitchTip, Uptime Kuma, `sentry-sdk[fastapi]` (pip), `@sentry/nextjs` (npm), FastAPI, Next 16.

**Spec:** `docs/superpowers/specs/2026-08-29-lancement-beta-design.md` — §5 (5.1 GlitchTip + scrubbing PII, 5.2 Uptime Kuma tunnel SSH, 5.3 logs + `/health` — `/health` déjà fait en Beta 1, 5.4 santé DB — déjà au runbook).

## Global Constraints

- **Branche** `feature/beta-launch`, jamais `main`. Commits scopés.
- **VPS 8 Go** (décision spec) : le monitoring tourne en permanence.
- **Rien d'exposé publiquement** : GlitchTip et Uptime Kuma bindent `127.0.0.1:<port>` ; accès via `ssh -L`.
- **Aucun CV / texte de CV ne doit atteindre GlitchTip.** `send_default_pii=False` + `before_send` obligatoire côté backend ; côté frontend, ne pas capturer les corps de requête.
- **`sentry-sdk` non épinglé** dans `requirements.txt` (convention du projet). `@sentry/nextjs` épinglé au caret comme les autres deps front.
- **Build Next 16 + Turbopack fragile** (cf. [[dev-workflow-feedback]] : `middleware.ts`→`proxy.ts`) : intégration Sentry frontend **minimale**, vérifiée par `npm run build` **et** navigateur réel. Fallback documenté en Task 3 si le build casse.
- **Init conditionnelle** : sans `GLITCHTIP_DSN` (dev, tests), le SDK ne s'initialise pas — aucun impact sur la suite de tests.

---

## File Structure

**Créés :**
- `docker-compose.monitoring.yml` (racine) — GlitchTip (web/worker/migrate/pg/redis) + Uptime Kuma.
- `deploy/monitoring/monitoring.env.example` — variables GlitchTip (SECRET_KEY, EMAIL_URL, etc.), placeholders.
- `backend/app/observability.py` — `init_sentry()` + `_before_send` (scrubbing).
- `backend/tests/test_observability.py` — teste `_before_send` (scrubbing), pas l'init réseau.

**Modifiés :**
- `backend/requirements.txt` — `+ sentry-sdk[fastapi]`.
- `backend/app/config.py` — `glitchtip_dsn: str = ""` (`environment` existe déjà, ajouté en Beta 2/3).
- `backend/app/main.py` — `init_sentry()` au chargement du module, avant `app = FastAPI(...)`.
- `frontend/package.json` — `+ @sentry/nextjs`.
- `frontend/instrumentation.ts` (créer) + `frontend/instrumentation-client.ts` (créer) — init Sentry serveur + client.
- `frontend/Dockerfile` — passer `NEXT_PUBLIC_GLITCHTIP_DSN` en build arg (comme `NEXT_PUBLIC_API_URL`).
- `docker-compose.prod.yml` — build arg `NEXT_PUBLIC_GLITCHTIP_DSN` sur le service `frontend`.
- `.gitignore` — `deploy/monitoring/monitoring.env`, `uptime-kuma` volume local si applicable.
- `backend/.env.example` — `+ GLITCHTIP_DSN=`.
- `docs/RUNBOOK.md` — section « Observabilité ».

---

## Task 1 : `docker-compose.monitoring.yml` (GlitchTip + Uptime Kuma)

**Files:**
- Create: `docker-compose.monitoring.yml`, `deploy/monitoring/monitoring.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: une stack de monitoring, projet Compose `search-monitoring` (clé `name:`), tous ports en `127.0.0.1` : GlitchTip web sur `127.0.0.1:3001`, Uptime Kuma sur `127.0.0.1:3002`. Volumes nommés `gt_pg`, `gt_uploads`, `kuma`.

- [ ] **Step 1 : Écrire `docker-compose.monitoring.yml`**

```yaml
name: search-monitoring

x-gt-env: &gt-env
  DATABASE_URL: postgres://postgres:${GT_PG_PASSWORD}@gt-postgres:5432/glitchtip
  SECRET_KEY: ${GT_SECRET_KEY}
  REDIS_URL: redis://gt-redis:6379/0
  DEFAULT_FROM_EMAIL: ${GT_FROM_EMAIL}
  EMAIL_URL: ${GT_EMAIL_URL}
  GLITCHTIP_DOMAIN: ${GT_DOMAIN:-http://localhost:3001}
  ENABLE_OPEN_USER_REGISTRATION: "False"

services:
  gt-postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${GT_PG_PASSWORD}
      POSTGRES_DB: glitchtip
    volumes: [gt_pg:/var/lib/postgresql/data]
    restart: unless-stopped
    networks: [monitoring]

  gt-redis:
    image: redis:7-alpine
    restart: unless-stopped
    networks: [monitoring]

  gt-web:
    image: glitchtip/glitchtip:latest
    depends_on: [gt-postgres, gt-redis]
    environment: *gt-env
    volumes: [gt_uploads:/code/uploads]
    ports: ["127.0.0.1:3001:8080"]
    restart: unless-stopped
    networks: [monitoring, default]

  gt-worker:
    image: glitchtip/glitchtip:latest
    command: ./bin/run-celery-with-beat.sh
    depends_on: [gt-postgres, gt-redis]
    environment: *gt-env
    volumes: [gt_uploads:/code/uploads]
    restart: unless-stopped
    networks: [monitoring, default]

  gt-migrate:
    image: glitchtip/glitchtip:latest
    command: ./manage.py migrate
    depends_on: [gt-postgres]
    environment: *gt-env
    networks: [monitoring]
    restart: on-failure

  uptime-kuma:
    image: louislam/uptime-kuma:1
    volumes: [kuma:/app/data]
    ports: ["127.0.0.1:3002:3001"]
    restart: unless-stopped
    networks: [default]

volumes:
  gt_pg:
  gt_uploads:
  kuma:

networks:
  monitoring:
  default:
```

> `gt-web`/`gt-worker` sont sur `default` en plus de `monitoring` pour joindre l'API du backend si besoin (ex. Kuma → `http://…` en localhost via le réseau hôte). Uptime Kuma surveille des URL **publiques** (`https://api.beta…/health`) — pas besoin du réseau interne de l'app.

- [ ] **Step 2 : `deploy/monitoring/monitoring.env.example`**

```dotenv
# Copier vers deploy/monitoring/monitoring.env (gitignoré).
GT_PG_PASSWORD=REMPLIR
GT_SECRET_KEY=REMPLIR   # python -c "import secrets;print(secrets.token_urlsafe(50))"
GT_FROM_EMAIL=monitoring@yokkutelabs.com
# Resend en SMTP : smtp://resend:<RESEND_API_KEY>@smtp.resend.com:587
GT_EMAIL_URL=REMPLIR
GT_DOMAIN=http://localhost:3001
```

- [ ] **Step 3 : `.gitignore`** — ajouter `deploy/monitoring/monitoring.env`.

- [ ] **Step 4 : Valider la syntaxe**

Run: `docker compose -f docker-compose.monitoring.yml --env-file deploy/monitoring/monitoring.env.example config >/dev/null && echo OK`
Expected: `OK` (exécuter sur le serveur si Docker absent en local).

- [ ] **Step 5 : Commit**

```bash
git add docker-compose.monitoring.yml deploy/monitoring/monitoring.env.example .gitignore
git commit -m "feat(observability): self-hosted GlitchTip + Uptime Kuma compose (loopback only)"
```

---

## Task 2 : Suivi d'erreurs backend (GlitchTip via sentry-sdk)

**Files:**
- Create: `backend/app/observability.py`, `backend/tests/test_observability.py`
- Modify: `backend/requirements.txt`, `backend/app/config.py`, `backend/app/main.py`, `backend/.env.example`

**Interfaces:**
- Produces:
  - `app.observability.init_sentry() -> None` — no-op si `settings.glitchtip_dsn` est vide ; sinon `sentry_sdk.init(dsn=..., environment=settings.environment, send_default_pii=False, traces_sample_rate=0.0, before_send=_before_send)`.
  - `app.observability._before_send(event: dict, hint: dict) -> dict | None` — supprime `event["request"]["data"]` et `["request"]["cookies"]` ; si le chemin de la requête commence par un préfixe sensible (`/diagnostics`, `/personalization`, `/candidate-profile/cv`, `/job-search/compatibility-detail`, `/interview-prep`, `/saved-jobs`) → supprime aussi `event["request"]` en entier sauf `url`+`method` ; scrub des valeurs de variables locales dont le nom contient `cv`, `resume`, `cv_text`, `offer_text`, `letter`, `dossier`, `password`, `token` dans `event["exception"]…["stacktrace"]["frames"][*]["vars"]`.

- [ ] **Step 1 : Dépendance + config**

`requirements.txt` : ajouter `sentry-sdk[fastapi]`.
`config.py` : `glitchtip_dsn: str = ""`.
`.env.example` : `GLITCHTIP_DSN=`.

Run: `cd backend && pip install "sentry-sdk[fastapi]"` (dans le venv de dev).

- [ ] **Step 2 : Tests qui échouent (scrubbing only)**

`backend/tests/test_observability.py` :

```python
from app.observability import _before_send


def test_before_send_drops_request_body():
    event = {"request": {"url": "https://x/y", "method": "POST", "data": {"cv": "secret"}, "cookies": "a=b"}}
    out = _before_send(event, {})
    assert "data" not in out["request"] and "cookies" not in out["request"]


def test_before_send_strips_request_on_sensitive_path():
    event = {"request": {"url": "https://x/diagnostics", "method": "POST", "data": {"cv": "secret"}, "headers": {"a": "b"}}}
    out = _before_send(event, {})
    assert set(out["request"]) <= {"url", "method"}


def test_before_send_scrubs_local_vars():
    event = {"exception": {"values": [{"stacktrace": {"frames": [
        {"vars": {"cv_text": "SENSITIVE", "count": "3"}}
    ]}}]}}
    out = _before_send(event, {})
    frame = out["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame["vars"]["cv_text"] == "[scrubbed]"
    assert frame["vars"]["count"] == "3"


def test_before_send_is_safe_on_minimal_event():
    assert _before_send({}, {}) == {}
```

- [ ] **Step 3 : Vérifier l'échec** — module absent.

- [ ] **Step 4 : Implémenter `observability.py`**

```python
import sentry_sdk

from app.config import get_settings

_SENSITIVE_PREFIXES = (
    "/diagnostics", "/personalization", "/candidate-profile/cv",
    "/job-search/compatibility-detail", "/interview-prep", "/saved-jobs",
)
_SENSITIVE_VAR_HINTS = (
    "cv", "resume", "cv_text", "offer_text", "letter", "dossier", "password", "token",
)


def _scrub_frames(event: dict) -> None:
    for value in event.get("exception", {}).get("values", []):
        for frame in value.get("stacktrace", {}).get("frames", []):
            varz = frame.get("vars")
            if not isinstance(varz, dict):
                continue
            for name in list(varz):
                if any(h in name.lower() for h in _SENSITIVE_VAR_HINTS):
                    varz[name] = "[scrubbed]"


def _before_send(event: dict, hint: dict) -> dict | None:
    request = event.get("request")
    if isinstance(request, dict):
        url = request.get("url", "")
        path = url.split("://", 1)[-1].split("/", 1)
        path = "/" + path[1] if len(path) > 1 else "/"
        if any(path.startswith(p) for p in _SENSITIVE_PREFIXES):
            event["request"] = {k: request[k] for k in ("url", "method") if k in request}
        else:
            request.pop("data", None)
            request.pop("cookies", None)
    _scrub_frames(event)
    return event


def init_sentry() -> None:
    dsn = get_settings().glitchtip_dsn
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=get_settings().environment,
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=_before_send,
    )
```

- [ ] **Step 5 : Câbler dans `main.py`**

En haut de `backend/app/main.py`, après les imports, avant `settings = get_settings()` (ou juste après) :

```python
from app.observability import init_sentry

init_sentry()
```

- [ ] **Step 6 : Vérifier**

Run: `cd backend && pytest tests/test_observability.py -q && pytest -q && ruff check app/ && mypy app`
Expected: PASS (l'init est no-op sans DSN → aucun autre test impacté).

- [ ] **Step 7 : Commit**

```bash
git add backend/requirements.txt backend/app/observability.py backend/app/config.py backend/app/main.py backend/.env.example backend/tests/test_observability.py
git commit -m "feat(observability): GlitchTip error reporting with PII-scrubbing before_send"
```

---

## Task 3 : Suivi d'erreurs frontend (@sentry/nextjs, minimal)

**Files:**
- Modify: `frontend/package.json`, `frontend/Dockerfile`, `docker-compose.prod.yml`
- Create: `frontend/instrumentation.ts`, `frontend/instrumentation-client.ts`

**Interfaces:**
- Produces: capture des erreurs client + serveur du frontend vers GlitchTip via `NEXT_PUBLIC_GLITCHTIP_DSN`. **Pas** de source maps, **pas** de `withSentryConfig`, **pas** de tunnel — init manuelle uniquement.

- [ ] **Step 1 : Dépendance**

Run: `cd frontend && npm install --save @sentry/nextjs`
(épinglé au caret comme les autres.)

- [ ] **Step 2 : `instrumentation-client.ts`** (racine `frontend/`)

```ts
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_GLITCHTIP_DSN;
if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV,
    tracesSampleRate: 0,
    sendDefaultPii: false,
    // Ne pas capturer les corps de requête / réponses.
    beforeBreadcrumb(crumb) {
      if (crumb.category === "fetch" || crumb.category === "xhr") {
        delete (crumb.data as Record<string, unknown> | undefined)?.["request_body"];
      }
      return crumb;
    },
  });
}

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
```

- [ ] **Step 3 : `instrumentation.ts`** (racine `frontend/`)

```ts
import * as Sentry from "@sentry/nextjs";

export async function register() {
  const dsn = process.env.NEXT_PUBLIC_GLITCHTIP_DSN;
  if (!dsn) return;
  if (process.env.NEXT_RUNTIME === "nodejs" || process.env.NEXT_RUNTIME === "edge") {
    Sentry.init({ dsn, environment: process.env.NODE_ENV, tracesSampleRate: 0, sendDefaultPii: false });
  }
}

export const onRequestError = Sentry.captureRequestError;
```

- [ ] **Step 4 : Build args**

`frontend/Dockerfile` — dans l'étape `builder`, ajouter :

```dockerfile
ARG NEXT_PUBLIC_GLITCHTIP_DSN
ENV NEXT_PUBLIC_GLITCHTIP_DSN=$NEXT_PUBLIC_GLITCHTIP_DSN
```

`docker-compose.prod.yml` — service `frontend`, sous `build.args` :

```yaml
        NEXT_PUBLIC_GLITCHTIP_DSN: ${NEXT_PUBLIC_GLITCHTIP_DSN:-}
```

- [ ] **Step 5 : Build (le point de risque)**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: build vert.

> **Si le build casse** (incompat `@sentry/nextjs` × Next 16 / Turbopack) : fallback —
> `npm remove @sentry/nextjs && npm install --save @sentry/react`, supprimer
> `instrumentation*.ts`, et ajouter un `<SentryErrorBoundary>` dans
> `app/providers.tsx` initialisé via `@sentry/react` `Sentry.init` dans un
> petit `components/observability/SentryInit.tsx` (`"use client"`, `useEffect`).
> Couvre les erreurs de rendu client, ce qui est l'essentiel pour un beta.
> Consigner le choix retenu dans le commit.

- [ ] **Step 6 : Vérif navigateur**

Avec un DSN GlitchTip de test dans l'env : provoquer une erreur client (ex. bouton de dev qui `throw`), vérifier qu'elle apparaît dans GlitchTip **sans** contenu de CV.

- [ ] **Step 7 : Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/instrumentation.ts frontend/instrumentation-client.ts frontend/Dockerfile docker-compose.prod.yml
git commit -m "feat(observability): minimal @sentry/nextjs client+server error reporting"
```

---

## Task 4 : Runbook observabilité + configuration des sondes

**Files:**
- Modify: `docs/RUNBOOK.md`

- [ ] **Step 1 : Ajouter la section « Observabilité »**

```markdown
## Observabilité

### Démarrage
`cp deploy/monitoring/monitoring.env.example deploy/monitoring/monitoring.env` (renseigner),
puis `docker compose -f docker-compose.monitoring.yml --env-file deploy/monitoring/monitoring.env up -d`.
Arrêt (libère ~1 Go RAM) : `... down` (sans `-v` — garde les données).

### Accès (tunnel SSH, rien de public)
Depuis le poste local :
`ssh -L 3001:127.0.0.1:3001 -L 3002:127.0.0.1:3002 <user>@<vps>`
puis http://localhost:3001 (GlitchTip) et http://localhost:3002 (Uptime Kuma).

### GlitchTip — mise en route (une fois)
1. Créer le compte admin sur la 1ʳᵉ visite.
2. Créer une organisation + un projet « backend » (plateforme Python) →
   copier le DSN → `backend/.env` `GLITCHTIP_DSN=` → `deploy/deploy.sh`.
3. Créer un projet « frontend » (plateforme JavaScript) → DSN →
   `docker-compose.prod.yml` build arg `NEXT_PUBLIC_GLITCHTIP_DSN` (via
   `.env` racine ou export) → redeploy.
4. Régler la rétention des events à 30 j (Settings du projet) pour borner
   le disque.
5. Alertes : Settings > Alerts → email (SMTP Resend déjà configuré via
   `GT_EMAIL_URL`) sur « nouveau problème ».

### Uptime Kuma — sondes à créer
- `API health` : HTTP(s), `https://api.beta.yokkutelabs.com/health`,
  intervalle 300 s, mot-clé attendu `"status": "ok"`.
- `Frontend` : HTTP(s), `https://beta.yokkutelabs.com`, 300 s.
- `TLS api` : le même moniteur API, activer « Certificate Expiry » (alerte
  à 14 j).
- Notification : email (SMTP Resend) ou Telegram.

### Logs applicatifs
`docker compose -f docker-compose.prod.yml logs -f <service>`.
Rotation : `json-file` `max-size=10m max-file=3` (déjà dans le compose).
```

- [ ] **Step 2 : Commit**

```bash
git add docs/RUNBOOK.md
git commit -m "docs(runbook): observability — start/stop, SSH tunnel, GlitchTip + Kuma setup"
```

---

## Self-Review

**Couverture du spec §5 :**

| Exigence | Task |
|---|---|
| §5.1 GlitchTip (web + deps) en `docker-compose.monitoring.yml` séparé | Task 1 |
| §5.1 SDK Sentry back + front, `dsn = GLITCHTIP_DSN` | Tasks 2, 3 |
| §5.1 `send_default_pii=False` + `before_send` supprimant les corps des routes CV + scrub des locals | Task 2 (`_before_send`, testé) |
| §5.1 `traces_sample_rate` bas (0.0) | Tasks 2, 3 |
| §5.1 note RAM / VPS 8 Go | Global Constraints + runbook (Task 4) |
| §5.2 Uptime Kuma conteneur unique, volume `kuma` | Task 1 |
| §5.2 accès tunnel SSH, pas de `server` block nginx | Task 1 (`127.0.0.1`) + runbook (Task 4) |
| §5.2 monitors `/health`, `/`, expiration TLS ; notif email/Telegram | Task 4 |
| §5.3 rotation logs `json-file` | déjà dans `docker-compose.prod.yml` (Beta 1) ; rappel runbook |
| §5.3 `/health` étendu (check DB) | fait en Beta 1 |
| §5.4 santé DB hebdo | déjà au runbook (Beta 1 §6) |

**Placeholders :** aucun `TBD` de code. Les `REMPLIR` de `monitoring.env.example` sont des placeholders de secrets, attendus (fichier d'exemple).

**Cohérence des noms :** `init_sentry` / `_before_send` (`app/observability.py`), `glitchtip_dsn` (backend), `GLITCHTIP_DSN` (env backend), `NEXT_PUBLIC_GLITCHTIP_DSN` (build arg frontend), projet Compose `search-monitoring`, ports `127.0.0.1:3001` (GlitchTip) / `127.0.0.1:3002` (Kuma), volumes `gt_pg` `gt_uploads` `kuma`. Identiques entre tasks et runbook.

**Risque identifié + mitigation :** `@sentry/nextjs` × Next 16 + Turbopack (Task 3) — fallback `@sentry/react` + ErrorBoundary documenté dans la task. Le backend (la source d'erreurs qui compte le plus, avec les CV) ne dépend pas de ce risque.

**Ordre d'exécution :** 1 → 2 → 3 → 4. Task 2 et 3 indépendantes après 1.
