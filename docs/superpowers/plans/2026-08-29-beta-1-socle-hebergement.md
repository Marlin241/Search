# Beta — Plan 1 : Socle d'hébergement & déploiement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre l'application déployable sur le VPS derrière son nginx/certbot existant, avec réseau interne cloisonné, endpoint `/health` fiable, scripts de déploiement et de sauvegarde chiffrée hors-site, et un runbook.

**Architecture:** Un `docker-compose.prod.yml` dérivé du compose de dev : `db` et `minio` ne publient plus aucun port, `backend` et `frontend` ne publient que sur `127.0.0.1`, le nginx de l'hôte (déjà installé) est le seul point d'entrée public et termine le TLS via certbot. Les sauvegardes sont des scripts shell lancés par cron sur l'hôte : `pg_dump` chiffré `age` + miroir MinIO, poussés vers Cloudflare R2 par `rclone`. Aucun changement de logique applicative sauf l'extension de `/health`.

**Tech Stack:** Docker Compose v2, nginx (hôte), certbot, `age` (chiffrement), `rclone` (Cloudflare R2), Bash, FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-lancement-beta-design.md` — §1 (Hébergement & déploiement), §2 (Sauvegardes), §5.3 (`/health` étendu), §9.1 (Runbook). Les §3-§8 sont couverts par les plans Beta 2 à 7.

## Global Constraints

- **Branche** : tout le travail sur `feature/beta-launch`, jamais `main`. Commits scopés : `git add <chemins explicites>`, jamais `git add -A`.
- **Le `docker-compose.yml` de dev reste inchangé** — le compose de prod est un fichier séparé.
- **`requirements.txt` non épinglé** par convention du projet — n'ajouter aucune dépendance ici (aucune nécessaire).
- **Après toute modif backend testée en réel** : `docker compose up -d --build backend` puis `docker logs search-backend-1` + `curl http://localhost:8000/health` (rappel : le backend n'a pas de volume mount).
- **Domaine** : `beta.yokkutelabs.com` (frontend), `api.beta.yokkutelabs.com` (backend). VPS **8 Go RAM**.
- **Aucun secret dans le repo** : `backend/.env` n'existe que sur le serveur ; `.env.example` ne contient que des placeholders ; les clés `age`/`rclone` ne sont jamais commitées.
- **Nom de projet Compose figé à `search`** (clé `name:` dans le compose de prod) pour que les noms de conteneurs restent `search-backend-1`, `search-db-1`, etc.
- **Rollback = code uniquement** : ne jamais écrire de migration Alembic destructive pendant le beta (colonnes nullable uniquement) — contrainte portée par les plans suivants, rappelée ici.

---

## File Structure

**Créés :**
- `docker-compose.prod.yml` (racine) — services de prod : ports internes only, `restart: unless-stopped`, logging borné, réseau `search_internal`, `name: search`.
- `deploy/nginx/beta.yokkutelabs.com.conf` — server block frontend (`:3000`).
- `deploy/nginx/api.beta.yokkutelabs.com.conf` — server block backend (`:8000`), `client_max_body_size`, timeouts.
- `deploy/nginx/security-headers.conf` — snippet d'en-têtes de sécurité inclus par les deux server blocks.
- `deploy/deploy.sh` — script de déploiement (sur le serveur) : checkout, build, up, vérif `/health`.
- `deploy/backup/pg_backup.sh` — dump Postgres → gzip → age → rclone vers R2 + prune.
- `deploy/backup/minio_mirror.sh` — `rclone sync` du bucket `personalization` vers R2.
- `deploy/backup/rclone.conf.example` — gabarit de config rclone R2 (placeholders).
- `docs/RUNBOOK.md` — provisioning, déploiement, rollback, sauvegarde/restauration, incidents courants.
- `backend/tests/test_health.py` — tests de l'endpoint `/health`.

**Modifiés :**
- `backend/app/main.py:106-108` — `/health` interroge la DB et renvoie `{status, db, version}`.
- `backend/.env.example` — ajout des clés de prod (placeholders) + bloc de commentaires.
- `.gitignore` — ignorer `deploy/backup/rclone.conf`, `*.age`, `/backups/`, `*.key`.

**Non modifiés (volontairement) :** `docker-compose.yml` (dev), `backend/Dockerfile` (le `CMD` fait déjà `alembic upgrade head`), toute logique métier.

---

## Task 1 : `/health` interroge la base

**Files:**
- Modify: `backend/app/main.py:106-108`
- Modify: `backend/tests/test_health.py` (le fichier existe déjà — `test_health_returns_ok` y assère `response.json() == {"status": "ok"}` à l'exact, ce que ce changement casse : le remplacer)

**Interfaces:**
- Consumes: `app.database.SessionLocal` (déjà utilisé par `main.py`).
- Produces: `GET /health` → `200 {"status": "ok", "db": "ok", "version": "<str>"}` quand la DB répond ; `503 {"status": "degraded", "db": "error", "version": "<str>"}` quand `SELECT 1` lève.

- [ ] **Step 1 : Réécrire `backend/tests/test_health.py`**

Remplacer tout le corps du fichier (garder les 2 lignes `os.environ.setdefault` du haut) par :

```python
import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok_reports_db_ok():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert "version" in body


def test_health_degraded_when_db_unavailable(monkeypatch):
    from app import main

    def _boom():
        raise RuntimeError("db down")

    # Force the DB probe to fail without touching the real session.
    monkeypatch.setattr(main, "_probe_db", _boom)
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["db"] == "error"
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: FAIL (`_probe_db` n'existe pas ; le body n'a ni `db` ni `version`).

- [ ] **Step 3 : Implémenter**

Dans `backend/app/main.py`, remplacer les lignes de `health()` par :

```python
from sqlalchemy import text
from fastapi import Response

APP_VERSION = "beta"


def _probe_db() -> None:
    db = database.SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    try:
        _probe_db()
        return {"status": "ok", "db": "ok", "version": APP_VERSION}
    except Exception:
        response.status_code = 503
        return {"status": "degraded", "db": "error", "version": APP_VERSION}
```

(`database` est déjà importé dans `main.py`.)

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5 : Non-régression + lint**

Run: `cd backend && ruff check app/main.py && ruff format --check app/main.py && pytest -q`
Expected: ruff OK, suite complète verte.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/main.py backend/tests/test_health.py
git commit -m "feat(health): /health probes the database and returns 503 when it is down"
```

> Note : `test_end_to_end.py` peut aussi toucher `/health` — si `pytest -q` à
> l'étape 5 signale un autre test qui assère l'ancien corps exact, l'aligner
> sur `body["status"] == "ok"` (sous-ensemble, pas égalité stricte).

---

## Task 2 : `docker-compose.prod.yml` + `.env.example` + `.gitignore`

**Files:**
- Create: `docker-compose.prod.yml`
- Modify: `backend/.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: un fichier compose validé par `docker compose -f docker-compose.prod.yml config`, exposant `127.0.0.1:8000` (backend) et `127.0.0.1:3000` (frontend), aucun port pour `db`/`minio`, projet nommé `search`.

- [ ] **Step 1 : Écrire `docker-compose.prod.yml`**

```yaml
name: search

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ats_diagnostic
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped
    networks: [search_internal]
    logging: &logging
      driver: json-file
      options: { max-size: "10m", max-file: "3" }

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped
    networks: [search_internal]
    logging: *logging

  createbuckets:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin} &&
      mc mb --ignore-existing local/personalization
      "
    networks: [search_internal]

  backend:
    build: ./backend
    env_file:
      - ./backend/.env
    environment:
      DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@db:5432/ats_diagnostic
      MINIO_ENDPOINT: http://minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-minioadmin}
      MINIO_BUCKET: personalization
    depends_on:
      db:
        condition: service_healthy
      createbuckets:
        condition: service_completed_successfully
    ports:
      - "127.0.0.1:8000:8000"
    restart: unless-stopped
    networks: [search_internal]
    logging: *logging

  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_URL: https://api.beta.yokkutelabs.com
    depends_on:
      - backend
    ports:
      - "127.0.0.1:3000:3000"
    restart: unless-stopped
    networks: [search_internal]
    logging: *logging

volumes:
  db_data:
  minio_data:

networks:
  search_internal:
    driver: bridge
```

- [ ] **Step 2 : Valider la syntaxe compose**

Run: `docker compose -f docker-compose.prod.yml config >/dev/null && echo OK`
Expected: `OK` (aucune erreur ; si `docker` absent en local, exécuter cette étape sur le serveur et cocher après).

- [ ] **Step 3 : Compléter `backend/.env.example`**

Ajouter à la fin de `backend/.env.example` :

```dotenv

# --- Production (beta) — renseigner uniquement dans backend/.env sur le serveur ---
# Généré par: openssl rand -hex 32
JWT_SECRET=change-me
# Origine autorisée du navigateur (le frontend)
CORS_ORIGINS=["https://beta.yokkutelabs.com"]
BACKEND_BASE_URL=https://api.beta.yokkutelabs.com
FRONTEND_BASE_URL=https://beta.yokkutelabs.com
# Mot de passe Postgres de prod (repris par docker-compose.prod.yml)
POSTGRES_PASSWORD=change-me
# Identifiants MinIO de prod
MINIO_ROOT_USER=change-me
MINIO_ROOT_PASSWORD=change-me
# Email d'expéditeur (domaine vérifié dans Resend)
RESEND_API_KEY=
RESEND_FROM_EMAIL=no-reply@yokkutelabs.com
```

- [ ] **Step 4 : Mettre à jour `.gitignore`**

Ajouter :

```gitignore
deploy/backup/rclone.conf
*.age
*.key
/backups/
```

- [ ] **Step 5 : Vérifier qu'aucun secret n'est suivi**

Run: `git status && git check-ignore -v deploy/backup/rclone.conf backups/ 2>/dev/null; echo done`
Expected: `docker-compose.prod.yml`, `backend/.env.example`, `.gitignore` en modifiés/nouveaux ; pas de `backend/.env`, pas de `rclone.conf`.

- [ ] **Step 6 : Commit**

```bash
git add docker-compose.prod.yml backend/.env.example .gitignore
git commit -m "feat(deploy): production docker-compose (internal-only db/minio, loopback app ports)"
```

---

## Task 3 : Server blocks nginx de l'hôte

**Files:**
- Create: `deploy/nginx/security-headers.conf`
- Create: `deploy/nginx/beta.yokkutelabs.com.conf`
- Create: `deploy/nginx/api.beta.yokkutelabs.com.conf`

**Interfaces:**
- Produces: 3 fichiers destinés à `/etc/nginx/` sur le serveur. `certbot --nginx` complètera les blocs TLS (443 + redirection 80→443) au premier passage. Contenu ci-dessous = configuration HTTP de base uniquement.

- [ ] **Step 1 : `deploy/nginx/security-headers.conf`**

```nginx
# Inclus dans chaque server block. En-têtes de sécurité communs.
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

- [ ] **Step 2 : `deploy/nginx/beta.yokkutelabs.com.conf`**

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name beta.yokkutelabs.com;

    include /etc/nginx/snippets/beta-security-headers.conf;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade           $http_upgrade;
        proxy_set_header Connection        "upgrade";
    }
}
```

- [ ] **Step 3 : `deploy/nginx/api.beta.yokkutelabs.com.conf`**

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name api.beta.yokkutelabs.com;

    include /etc/nginx/snippets/beta-security-headers.conf;

    # Upload de CV (multipart) — cohérent avec la validation applicative.
    client_max_body_size 12m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # Générations synchrones éventuelles (diagnostic).
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }
}
```

- [ ] **Step 4 : Vérifier la cohérence des chemins d'include**

Le runbook (Task 6) doit indiquer : copier `security-headers.conf` vers `/etc/nginx/snippets/beta-security-headers.conf`, les deux autres vers `/etc/nginx/sites-available/` + symlink dans `sites-enabled/`, puis `sudo nginx -t`.

Run: `grep -rn "beta-security-headers.conf" deploy/nginx/`
Expected: référencé dans les deux server blocks, avec le même chemin.

- [ ] **Step 5 : Commit**

```bash
git add deploy/nginx/
git commit -m "feat(deploy): host nginx server blocks for beta + api subdomains"
```

---

## Task 4 : Script de déploiement

**Files:**
- Create: `deploy/deploy.sh`

**Interfaces:**
- Produces: `deploy/deploy.sh [<ref>]` — exécuté **sur le serveur**, à la racine du repo cloné. `<ref>` par défaut `origin/feature/beta-launch` (à ajuster après merge vers `main`). Sort en erreur si `/health` ne répond pas `200` après le déploiement.

- [ ] **Step 1 : Écrire `deploy/deploy.sh`**

```bash
#!/usr/bin/env bash
# Déploiement de la beta. À lancer sur le VPS, à la racine du repo.
# Usage: deploy/deploy.sh [git-ref]
set -euo pipefail

REF="${1:-origin/feature/beta-launch}"
COMPOSE="docker compose -f docker-compose.prod.yml"

echo "==> Fetch + checkout $REF"
git fetch --all --tags
git checkout --detach "$REF"
git log -1 --oneline

echo "==> Build + up"
$COMPOSE up -d --build

echo "==> Attente de /health (max 90s)"
for i in $(seq 1 18); do
  if curl -fsS http://127.0.0.1:8000/health | grep -q '"status": "ok"'; then
    echo "OK après $((i*5))s"
    $COMPOSE ps
    exit 0
  fi
  sleep 5
done

echo "!! /health n'est jamais passé OK — logs :"
$COMPOSE logs --tail=80 backend
exit 1
```

- [ ] **Step 2 : Vérifier la syntaxe**

Run: `bash -n deploy/deploy.sh && chmod +x deploy/deploy.sh && echo OK`
Expected: `OK`. Si `shellcheck` est disponible : `shellcheck deploy/deploy.sh` (avertissements mineurs tolérés).

- [ ] **Step 3 : Commit**

```bash
git add deploy/deploy.sh
git commit -m "feat(deploy): deploy.sh — checkout, build, up, health-gate"
```

---

## Task 5 : Scripts de sauvegarde chiffrée vers Cloudflare R2

**Files:**
- Create: `deploy/backup/pg_backup.sh`
- Create: `deploy/backup/minio_mirror.sh`
- Create: `deploy/backup/rclone.conf.example`

**Interfaces:**
- Produces:
  - `deploy/backup/pg_backup.sh` — `pg_dump` (via `docker compose exec -T db`) → `gzip` → `age -r $AGE_RECIPIENT` → fichier `db-<date>.sql.gz.age` local, puis `rclone copy` vers `r2:$R2_BUCKET/db/`, puis prune (> 14 quotidiennes, garde 1/semaine au-delà jusqu'à 8 semaines) local **et** distant.
  - `deploy/backup/minio_mirror.sh` — `rclone sync` du contenu du bucket MinIO `personalization` vers `r2:$R2_BUCKET/media/`.
  - Les deux lisent leur config depuis `deploy/backup/backup.env` (non commité) : `AGE_RECIPIENT`, `R2_BUCKET`, `RCLONE_CONFIG`.

- [ ] **Step 1 : `deploy/backup/rclone.conf.example`**

```ini
# Copier vers deploy/backup/rclone.conf (gitignoré) et renseigner.
# Valeurs depuis Cloudflare dashboard > R2 > Manage R2 API Tokens.
[r2]
type = s3
provider = Cloudflare
access_key_id = REMPLIR
secret_access_key = REMPLIR
endpoint = https://<ACCOUNT_ID>.r2.cloudflarestorage.com
acl = private
```

- [ ] **Step 2 : `deploy/backup/pg_backup.sh`**

```bash
#!/usr/bin/env bash
# Sauvegarde chiffrée de Postgres vers Cloudflare R2. Cron quotidien sur le VPS.
set -euo pipefail

cd "$(dirname "$0")/../.."                       # racine du repo
source deploy/backup/backup.env                  # AGE_RECIPIENT, R2_BUCKET, RCLONE_CONFIG

STAMP="$(date -u +%F)"
OUT_DIR="backups/db"
mkdir -p "$OUT_DIR"
FILE="$OUT_DIR/db-$STAMP.sql.gz.age"

echo "==> Dump + chiffrement -> $FILE"
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U postgres --no-owner ats_diagnostic \
  | gzip \
  | age -r "$AGE_RECIPIENT" > "$FILE"

test -s "$FILE" || { echo "!! dump vide"; exit 1; }

echo "==> Upload R2"
rclone --config "$RCLONE_CONFIG" copy "$FILE" "r2:$R2_BUCKET/db/"

echo "==> Prune local (> 21 jours)"
find "$OUT_DIR" -name 'db-*.sql.gz.age' -mtime +21 -delete

echo "==> Prune R2 (> 60 jours)"
rclone --config "$RCLONE_CONFIG" delete --min-age 60d "r2:$R2_BUCKET/db/"

echo "OK $STAMP"
```

- [ ] **Step 3 : `deploy/backup/minio_mirror.sh`**

```bash
#!/usr/bin/env bash
# Miroir du bucket MinIO 'personalization' vers R2. Cron quotidien sur le VPS.
set -euo pipefail

cd "$(dirname "$0")/../.."
source deploy/backup/backup.env

# Exporte les objets MinIO via un conteneur mc jetable sur le réseau interne,
# vers un dossier local, puis rclone sync ce dossier vers R2.
STAGE="backups/media"
mkdir -p "$STAGE"

docker compose -f docker-compose.prod.yml run --rm -T \
  -v "$(pwd)/$STAGE:/export" \
  --entrypoint /bin/sh minio-client-oneoff 2>/dev/null || true

docker run --rm --network search_internal \
  -v "$(pwd)/$STAGE:/export" minio/mc:latest sh -c "
    mc alias set src http://minio:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD >/dev/null 2>&1 || \
    mc alias set src http://minio:9000 minioadmin minioadmin >/dev/null;
    mc mirror --overwrite --remove src/personalization /export
  "

rclone --config "$RCLONE_CONFIG" sync "$STAGE" "r2:$R2_BUCKET/media/"
echo "OK $(date -u +%F)"
```

> Note pour l'implémenteur : la ligne `minio-client-oneoff` est un garde inerte
> (`|| true`) ; l'export réel est fait par le `docker run … minio/mc` qui suit,
> attaché au réseau `search_internal`. Passer `MINIO_ROOT_USER/PASSWORD` via
> `--env-file deploy/backup/backup.env` si les identifiants MinIO y sont
> ajoutés ; sinon le fallback `minioadmin` s'applique.

- [ ] **Step 4 : Vérifier la syntaxe des deux scripts**

Run: `bash -n deploy/backup/pg_backup.sh && bash -n deploy/backup/minio_mirror.sh && chmod +x deploy/backup/*.sh && echo OK`
Expected: `OK`.

- [ ] **Step 5 : Commit**

```bash
git add deploy/backup/
git commit -m "feat(backup): encrypted pg_dump + MinIO mirror to Cloudflare R2"
```

---

## Task 6 : `docs/RUNBOOK.md`

**Files:**
- Create: `docs/RUNBOOK.md`

**Interfaces:**
- Produces: le mode d'emploi opérationnel du beta. Les plans suivants (2-7) y ajouteront leurs sections (génération de codes, interrupteur LLM, monitoring…).

- [ ] **Step 1 : Écrire `docs/RUNBOOK.md`**

Contenu (rédiger chaque section en entier, commandes exactes) :

```markdown
# Runbook — Beta yokkutelabs

## 1. Provisioning initial du VPS (une fois)

1. VPS Debian 12, 8 Go RAM. DNS : enregistrements A (+ AAAA) `beta` et
   `api.beta` de `yokkutelabs.com` → IP du VPS.
2. `apt update && apt install -y docker.io docker-compose-plugin age rclone git ufw fail2ban`
3. Pare-feu : `ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw enable`
4. SSH : dans `/etc/ssh/sshd_config` → `PasswordAuthentication no`,
   `PermitRootLogin no` ; `systemctl restart ssh`.
5. `git clone <repo> /opt/search && cd /opt/search`
6. Créer `backend/.env` (chmod 600) à partir de `backend/.env.example` :
   `openssl rand -hex 32` pour `JWT_SECRET` et `POSTGRES_PASSWORD`.
7. nginx :
   - `cp deploy/nginx/security-headers.conf /etc/nginx/snippets/beta-security-headers.conf`
   - `cp deploy/nginx/beta.yokkutelabs.com.conf /etc/nginx/sites-available/`
   - `cp deploy/nginx/api.beta.yokkutelabs.com.conf /etc/nginx/sites-available/`
   - `ln -s ../sites-available/beta.yokkutelabs.com.conf /etc/nginx/sites-enabled/`
   - `ln -s ../sites-available/api.beta.yokkutelabs.com.conf /etc/nginx/sites-enabled/`
   - `nginx -t && systemctl reload nginx`
8. TLS : `certbot --nginx -d beta.yokkutelabs.com -d api.beta.yokkutelabs.com`
9. Premier déploiement : `deploy/deploy.sh`
10. Sauvegardes : `cp deploy/backup/rclone.conf.example deploy/backup/rclone.conf`
    (renseigner), créer `deploy/backup/backup.env`
    (`AGE_RECIPIENT=`, `R2_BUCKET=`, `RCLONE_CONFIG=/opt/search/deploy/backup/rclone.conf`),
    générer la paire age hors serveur (`age-keygen`), ne mettre que la
    **clé publique** dans `backup.env`. Cron :
    `0 2 * * * cd /opt/search && deploy/backup/pg_backup.sh >> /var/log/pg_backup.log 2>&1`
    `30 2 * * * cd /opt/search && deploy/backup/minio_mirror.sh >> /var/log/minio_mirror.log 2>&1`

## 2. Déploiement courant

`cd /opt/search && deploy/deploy.sh` (ou `deploy/deploy.sh <tag>`).
Rappel : le backend n'a pas de volume mount — le rebuild est fait par le
script. Vérif : `curl -s https://api.beta.yokkutelabs.com/health`.

## 3. Rollback

`deploy/deploy.sh <commit-précédent>`. **Code uniquement** — pas de
`downgrade` Alembic fiable sur ce projet. Une migration du beta ne doit
jamais supprimer/renommer de colonne.

## 4. Sauvegarde & restauration

- Sauvegarde manuelle : `deploy/backup/pg_backup.sh`.
- **Restauration (à tester une fois avant le lancement)** :
  1. Récupérer le `.age` : `rclone --config deploy/backup/rclone.conf copy r2:<bucket>/db/db-<date>.sql.gz.age .`
  2. `age -d -i <clé-privée> db-<date>.sql.gz.age | gunzip > dump.sql`
  3. Sur une machine jetable : `createdb restore_test && psql restore_test < dump.sql`
  4. `psql restore_test -c "SELECT count(*) FROM users;"` — cohérent ?
- **Ne jamais** `docker compose -f docker-compose.prod.yml down -v` (détruit
  `db_data` et `minio_data`).

## 5. Incidents courants

- **Requête qui « pend »** : `docker compose -f docker-compose.prod.yml exec db psql -U postgres -d ats_diagnostic -c "SELECT pid,state,wait_event,left(query,60) FROM pg_stat_activity WHERE datname='ats_diagnostic' AND pid<>pg_backend_pid();"` — si `idle in transaction` bloquant : `docker compose -f docker-compose.prod.yml restart backend`.
- **Disque plein** : `docker system prune -f` ; purger `/var/log/*backup.log` ;
  `find backups/ -mtime +21 -delete`.
- **Frontend/back KO après deploy** : `docker compose -f docker-compose.prod.yml logs --tail=100 <service>` ; rollback (§3).
- **Certificat TLS** : renouvellement auto par certbot ; forcer avec
  `certbot renew --force-renewal` puis `systemctl reload nginx`.

## 6. Santé hebdomadaire

- `docker compose -f docker-compose.prod.yml ps` — tous `healthy`.
- `df -h` et `free -m`.
- Taille base : `docker compose -f docker-compose.prod.yml exec db psql -U postgres -d ats_diagnostic -c "\l+"`.
- Dernière sauvegarde présente sur R2 : `rclone --config deploy/backup/rclone.conf lsl r2:<bucket>/db/ | tail`.
```

- [ ] **Step 2 : Vérifier les liens croisés**

Run: `grep -n "deploy/backup/backup.env\|beta-security-headers.conf\|docker-compose.prod.yml" docs/RUNBOOK.md`
Expected: les noms de fichiers correspondent exactement à ceux créés aux Tasks 2-5.

- [ ] **Step 3 : Commit**

```bash
git add docs/RUNBOOK.md
git commit -m "docs: operational runbook for the beta (provisioning, deploy, backup, incidents)"
```

---

## Task 7 : Répétition de déploiement (dry run) + relevé

**Files:** aucun (vérification).

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: une section « Dry run » ajoutée en bas de `docs/RUNBOOK.md` avec le résultat observé (date, ce qui a marché, ce qui a coincé).

- [ ] **Step 1 : Valider le compose de prod en conditions réelles**

Sur le VPS (ou une machine avec Docker), à la racine du repo, avec un
`backend/.env` de test :

Run: `docker compose -f docker-compose.prod.yml up -d --build`
Then: `docker compose -f docker-compose.prod.yml ps`
Expected: `db` et `minio` `healthy`, `backend` et `frontend` `running`, aucun port `0.0.0.0:*` sur `db`/`minio` (`docker compose -f docker-compose.prod.yml ps` ne montre que `127.0.0.1:8000` et `127.0.0.1:3000`).

- [ ] **Step 2 : Vérifier `/health` et l'isolement réseau**

Run: `curl -s http://127.0.0.1:8000/health`
Expected: `{"status": "ok", "db": "ok", "version": "beta"}`.

Run: `curl -s http://127.0.0.1:5432 ; echo "(exit $?)"`
Expected: échec de connexion (Postgres non exposé).

- [ ] **Step 3 : Vérifier `alembic upgrade head` a tourné**

Run: `docker compose -f docker-compose.prod.yml logs backend | grep -i "alembic\|Running upgrade\|uvicorn running"`
Expected: montée de version Alembic puis `Uvicorn running`.

- [ ] **Step 4 : Tester une sauvegarde + une restauration**

Suivre `docs/RUNBOOK.md` §4 (sauvegarde manuelle puis restauration sur base
jetable). Noter le `SELECT count(*)` obtenu.

- [ ] **Step 5 : Consigner le dry run**

Ajouter à `docs/RUNBOOK.md` :

```markdown
## Dry run — <date>

- `docker-compose.prod.yml` : <OK / écarts>
- `/health` : <réponse>
- Isolement db/minio : <OK / écarts>
- Sauvegarde + restauration : <count users obtenu>, <durée>
- À corriger avant lancement : <liste ou « rien »>
```

- [ ] **Step 6 : Commit**

```bash
git add docs/RUNBOOK.md
git commit -m "docs: record beta deployment dry run results"
```

---

## Self-Review

**Couverture du spec (§1, §2, §5.3, §9.1) :**

| Exigence spec | Task |
|---|---|
| §1.2 `docker-compose.prod.yml`, ports internes, logging borné, réseau | Task 2 |
| §1.3 server blocks nginx + en-têtes sécurité + `client_max_body_size` | Task 3 |
| §1.4 DNS | Runbook §1 (Task 6) |
| §1.5 durcissement serveur (ufw, SSH, fail2ban) | Runbook §1 (Task 6) |
| §1.6 secrets prod dans `.env` / `.env.example` complété | Task 2 |
| §1.7 `deploy.sh`, health-gate, rollback code-only | Task 4 + Runbook §3 |
| §1.7 migrations via `CMD` backend | inchangé (vérifié Task 7 Step 3) |
| §2.1 `pg_dump` + `age` + `rclone` R2 + rétention | Task 5 |
| §2.2 miroir MinIO | Task 5 |
| §2.3 restauration testée | Task 7 Step 4 + Runbook §4 |
| §2.4 garde-fou `down -v` | Runbook §4 |
| §5.3 `/health` étendu (check DB) | Task 1 |
| §9.1 runbook (provisioning, deploy, rollback, backup, incidents, santé hebdo) | Task 6 |

**Hors de ce plan (plans suivants) :** `environment`/`COOKIE_DOMAIN`/`GLITCHTIP_DSN`/quotas LLM dans `.env.example` — ajoutés par les plans qui les consomment (Beta 2, 3, 5), pour ne pas documenter des clés inertes. Le `docker-compose.monitoring.yml` est au plan Beta 5.

**Placeholders :** aucun `TBD`/`TODO` ; toutes les commandes et tous les fichiers sont donnés en entier.

**Cohérence des noms :** `search_internal` (réseau), `search` (projet Compose → conteneurs `search-backend-1`/`search-db-1`), `beta-security-headers.conf` (snippet nginx), `deploy/backup/backup.env` (config non commitée), `r2:$R2_BUCKET` (remote rclone) — identiques entre Tasks 2-7 et le runbook.

**Note d'exécution :** les Tasks 1-6 se font sur poste de dev (les steps « valider avec `docker compose config` » peuvent être cochées après exécution sur le serveur si Docker n'est pas local). La Task 7 exige un accès Docker réel (VPS de préférence) et **doit** être faite avant d'enchaîner les plans Beta 2+.
