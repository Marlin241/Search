# Runbook — Beta yokkutelabs

Opérations du beta fermé (`search.yokkutelabs.com`). Les plans Beta 2 à 7
ajoutent leurs sections au fil de leur exécution.

## 1. Provisioning initial du VPS (une fois)

1. VPS Debian 12, **8 Go RAM**. DNS : enregistrements **A** (+ **AAAA** si
   IPv6) `search` et `api.search` de `yokkutelabs.com` → IP du VPS.
2. `apt update && apt install -y docker.io docker-compose-plugin age rclone git ufw fail2ban`
3. Pare-feu : `ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw enable`
4. SSH : dans `/etc/ssh/sshd_config` → `PasswordAuthentication no`,
   `PermitRootLogin no` ; `systemctl restart ssh`.
5. `git clone <repo> /opt/Search && cd /opt/Search && git checkout main`
6. **Deux fichiers d'environnement distincts :**
   - `/opt/Search/.env` (`chmod 600`) — lu par `docker compose` pour
     l'interpolation. Depuis `.env.prod.example` :
     `POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
     (obligatoires : le compose de prod échoue si l'un manque — pas de
     valeur par défaut faible). Générer chacun avec `openssl rand -hex 32`
     (ou `-base64 24` pour l'user MinIO).
   - `/opt/Search/backend/.env` (`chmod 600`) — injecté dans le conteneur
     backend. Depuis `backend/.env.example` :
     - `JWT_SECRET` : `openssl rand -hex 32`
     - `CORS_ORIGINS=["https://search.yokkutelabs.com"]`
     - `BACKEND_BASE_URL=https://api.search.yokkutelabs.com`
     - `FRONTEND_BASE_URL=https://search.yokkutelabs.com`
     - `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, et les
       clés de sources d'offres (France Travail, Adzuna…)
     - `ADMIN_EMAILS=guyroland879@gmail.com` (inscription sans code +
       promotion admin auto ; cf. §9)
     - `ADMIN_NOTIFY_EMAIL=guyroland879@gmail.com` (notifs demandes d'accès
       + retours in-app)
     - **Ne PAS** y remettre `DATABASE_URL` / `MINIO_*` : le compose de prod
       les construit et les surcharge à partir de `/opt/Search/.env`.
7. nginx :
   - `cp deploy/nginx/security-headers.conf /etc/nginx/snippets/beta-security-headers.conf`
   - `cp deploy/nginx/search.yokkutelabs.com.conf /etc/nginx/sites-available/`
   - `cp deploy/nginx/api.search.yokkutelabs.com.conf /etc/nginx/sites-available/`
   - `ln -s ../sites-available/search.yokkutelabs.com.conf /etc/nginx/sites-enabled/`
   - `ln -s ../sites-available/api.search.yokkutelabs.com.conf /etc/nginx/sites-enabled/`
   - `nginx -t && systemctl reload nginx`
8. TLS : `certbot --nginx -d search.yokkutelabs.com -d api.search.yokkutelabs.com`
9. Premier déploiement : `deploy/deploy.sh`
10. Sauvegardes :
    - `cp deploy/backup/rclone.conf.example deploy/backup/rclone.conf` (renseigner
      depuis Cloudflare > R2 > API Tokens)
    - `cp deploy/backup/backup.env.example deploy/backup/backup.env`
      (`RCLONE_CONFIG=/opt/Search/deploy/backup/rclone.conf`, `R2_BUCKET=…`,
      `MINIO_ROOT_USER`/`PASSWORD` = mêmes valeurs que `/opt/Search/.env`)
    - Générer la paire `age` **hors serveur** : `age-keygen -o key.txt` ;
      copier **uniquement** la clé publique `age1…` dans `AGE_RECIPIENT` ;
      garder `key.txt` (clé privée) en lieu sûr hors serveur.
    - Cron :
      ```
      0 2 * * * cd /opt/Search && deploy/backup/pg_backup.sh >> /var/log/pg_backup.log 2>&1
      30 2 * * * cd /opt/Search && deploy/backup/minio_mirror.sh >> /var/log/minio_mirror.log 2>&1
      ```

## 2. Déploiement courant

**Automatique** : chaque push sur `main` déclenche `.github/workflows/ci.yml` ;
si les jobs `backend` + `frontend` passent, le job `deploy` se connecte en SSH
au VPS et lance `deploy/deploy.sh origin/main`. Redéploiement manuel possible
via l'onglet **Actions ▸ CI ▸ Run workflow**.

**Manuel** (rollback, ou CI indisponible) : `cd /opt/Search && deploy/deploy.sh`
(ou `deploy/deploy.sh <tag-ou-commit>`).

Rappel : le backend n'a pas de volume mount — le rebuild est fait par le
script. Vérif : `curl -s https://api.search.yokkutelabs.com/health`.
Les migrations Alembic sont appliquées automatiquement au démarrage du
conteneur backend (`alembic upgrade head` dans son `CMD`) ; si elles échouent,
`/health` ne repasse pas OK, `deploy.sh` sort en erreur et le job GitHub échoue.

### Secrets GitHub à créer (Settings ▸ Secrets and variables ▸ Actions)

Tant qu'ils sont absents, le job `deploy` se contente d'un message et passe.

| Secret | Contenu |
| --- | --- |
| `DEPLOY_SSH_HOST` | IP ou hostname du VPS |
| `DEPLOY_SSH_USER` | utilisateur de déploiement (accès à `/opt/Search` + `docker`) |
| `DEPLOY_SSH_KEY` | clé privée SSH **dédiée au déploiement** (`ssh-keygen -t ed25519 -f deploy_key -N ""` ; `deploy_key.pub` → `~/.ssh/authorized_keys` de l'utilisateur sur le VPS) |
| `DEPLOY_SSH_PORT` | port SSH si non-standard (facultatif ; 22 par défaut) |
| `DEPLOY_KNOWN_HOSTS` | sortie de `ssh-keyscan -p <port> <host>` (épingle la clé du serveur — anti-MITM). Sur port non-standard les lignes sont au format `[host]:port …` |

Restreindre la clé côté serveur (`authorized_keys`) :
`from="<ip-github-actions>",no-port-forwarding,no-agent-forwarding,no-X11-forwarding …`
n'est pas possible (les runners GitHub n'ont pas d'IP fixe) — utiliser un
utilisateur dédié aux droits minimaux, ou un runner self-hosted sur le VPS si
on veut fermer l'accès SSH entrant.

## 3. Rollback

`deploy/deploy.sh <commit-précédent>`. **Code uniquement** — pas de
`downgrade` Alembic fiable sur ce projet. Une migration du beta ne doit
jamais supprimer ni renommer de colonne (ajouts nullable uniquement).

## 4. Sauvegarde & restauration

- Sauvegarde manuelle : `deploy/backup/pg_backup.sh` (et
  `deploy/backup/minio_mirror.sh`).
- **Restauration (à tester une fois avant le lancement)** :
  1. `rclone --config deploy/backup/rclone.conf copy r2:<bucket>/db/db-<date>.sql.gz.age .`
  2. `age -d -i key.txt db-<date>.sql.gz.age | gunzip > dump.sql`
  3. Sur une machine jetable : `createdb restore_test && psql restore_test < dump.sql`
  4. `psql restore_test -c "SELECT count(*) FROM users;"` — cohérent ?
- **Ne jamais** `docker compose -f docker-compose.prod.yml down -v` (détruit
  `db_data` et `minio_data`).

## 5. Incidents courants

- **Requête qui « pend »** :
  `docker compose -f docker-compose.prod.yml exec db psql -U postgres -d ats_diagnostic -c "SELECT pid,state,wait_event,left(query,60) FROM pg_stat_activity WHERE datname='ats_diagnostic' AND pid<>pg_backend_pid();"`
  — si `idle in transaction` bloquant :
  `docker compose -f docker-compose.prod.yml restart backend`.
- **Disque plein** : `docker system prune -f` ; purger `/var/log/*backup.log` ;
  `find backups/ -mtime +21 -delete`.
- **Frontend/back KO après deploy** :
  `docker compose -f docker-compose.prod.yml logs --tail=100 <service>` ; rollback (§3).
- **Certificat TLS** : renouvellement auto par certbot ; forcer avec
  `certbot renew --force-renewal` puis `systemctl reload nginx`.

## 6. Santé hebdomadaire

- `docker compose -f docker-compose.prod.yml ps` — tous `healthy`.
- `df -h` et `free -m`.
- Taille de la base :
  `docker compose -f docker-compose.prod.yml exec db psql -U postgres -d ats_diagnostic -c "\l+"`.
- Dernière sauvegarde présente sur R2 :
  `rclone --config deploy/backup/rclone.conf lsl r2:<bucket>/db/ | tail`.

## 7. RGPD / données

- **Suppression de compte** : self-service (profil > Zone de danger). Purge
  en base (toutes les tables liées) + objets MinIO `users/<id>/`. Les codes
  d'invitation consommés sont déliés (conservés, marqués utilisés).
- **Demande manuelle par email** :
  `docker compose -f docker-compose.prod.yml exec backend python -c "from app.database import SessionLocal; from app.models.user import User; from app.auth.account_deletion import delete_account; from app.storage.dependencies import get_object_storage; db=SessionLocal(); u=db.query(User).filter_by(email='X@Y').one(); delete_account(db, u, get_object_storage())"`
- **Export** : self-service (profil > Zone de danger > Exporter mes données),
  ou `GET /auth/me/export` avec le token de l'utilisateur.
- **Purge d'inactivité (6 mois)** : manuelle pendant la beta —
  `SELECT email FROM users WHERE id NOT IN (SELECT DISTINCT user_id FROM llm_call_logs) AND created_at < now() - interval '6 months';`
  puis `delete_account` pour chacun.
- **Pages légales** : `/conditions`, `/confidentialite`. Version en vigueur :
  `CURRENT_TERMS_VERSION` (`backend/app/auth/consent.py`). Les mentions
  `[À CONFIRMER : …]` (forme juridique, pays de l'hébergeur, email) doivent
  être renseignées avant l'ouverture du beta.
- **Demandes d'accès (table `access_requests`)** : déposées depuis la landing
  publique, non rattachées à un compte. Le demandeur reçoit un accusé de
  réception ; l'admin est notifié si `ADMIN_NOTIFY_EMAIL` est renseigné.
  Traitement dans `/admin ▸ Demandes d'accès` : **Approuver** génère un code
  d'invitation à usage unique (30 j) et l'envoie par email au demandeur ;
  **Écarter** clôt sans email. `status` ∈ `pending` / `approved` / `dismissed`.
  Purge des demandes en attente (> 90 j) :
  `docker exec search-db-1 psql -U postgres -d ats_diagnostic -c "DELETE FROM access_requests WHERE status = 'pending' AND created_at < now() - interval '90 days';"`
  Sur demande d'effacement d'une personne qui avait demandé un accès :
  `docker exec search-db-1 psql -U postgres -d ats_diagnostic -c "DELETE FROM access_requests WHERE email = 'la-personne@example.com';"`

## 8. Observabilité

### Démarrage
`cp deploy/monitoring/monitoring.env.example deploy/monitoring/monitoring.env`
(renseigner `GT_PG_PASSWORD`, `GT_SECRET_KEY`), puis :
`docker compose -f docker-compose.monitoring.yml --env-file deploy/monitoring/monitoring.env up -d`
Arrêt (libère ~1 Go RAM) : même commande + `down` (jamais `-v`).

### Accès (tunnel SSH — rien de public)
Depuis le poste local :
`ssh -L 3001:127.0.0.1:3001 -L 3002:127.0.0.1:3002 <user>@<vps>`
puis http://localhost:3001 (GlitchTip) et http://localhost:3002 (Uptime Kuma).

### GlitchTip — mise en route (une fois)
1. Créer le compte admin à la 1ʳᵉ visite ; créer une organisation.
2. Projet « backend » (plateforme Python) → copier le DSN →
   `backend/.env` `GLITCHTIP_DSN=` + `ENVIRONMENT=production` →
   `deploy/deploy.sh`.
3. Projet « frontend » (plateforme JavaScript) → DSN → `/opt/Search/.env`
   `NEXT_PUBLIC_GLITCHTIP_DSN=` → redeploy (rebuild frontend).
4. Rétention des events : 30 j (Settings du projet).
5. Alertes : Settings > Alerts → email sur « nouveau problème »
   (SMTP via `GT_EMAIL_URL`).

### Uptime Kuma — sondes à créer
- `API health` : HTTP(s) `https://api.search.yokkutelabs.com/health`, 300 s,
  mot-clé attendu `"status":"ok"`.
- `Frontend` : HTTP(s) `https://search.yokkutelabs.com`, 300 s.
- Sur le moniteur API : activer « Certificate Expiry » (alerte à 14 j).
- Notification : email (SMTP Resend) ou Telegram.

### Logs applicatifs
`docker compose -f docker-compose.prod.yml logs -f <service>`.
Rotation `json-file` (max-size 10m, max-file 3) déjà dans le compose.

## 9. Admin

- **Se donner les droits admin** : mettre son email dans `ADMIN_EMAILS`
  (`backend/.env`, séparés par des virgules), puis
  `docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_admin`
  (demande un mot de passe, crée le compte déjà admin ; ré-exécutable). Ensuite
  connexion normale sur `/login`. Les comptes listés dans `ADMIN_EMAILS`
  s'inscrivent sans code d'invitation et sont promus au démarrage.
  - **Promotion seule** : retirer un email d'`ADMIN_EMAILS` ne retire **pas**
    `is_admin`. Pour révoquer :
    `docker compose -f docker-compose.prod.yml exec db psql -U postgres -d ats_diagnostic -c "UPDATE users SET is_admin = false WHERE email = '...';"`
- **Dashboard** : https://search.yokkutelabs.com/admin (visible seulement pour un
  compte `is_admin` ; un compte normal est redirigé vers `/dashboard` et ne voit
  pas l'entrée de nav « Admin »).
- **Codes d'invitation** : onglet Invitations (ou CLI
  `docker compose -f docker-compose.prod.yml exec backend python -m scripts.invites generate --count 15 --note "vague 1"`).
- **Interrupteur LLM** : onglet Vue d'ensemble (ou CLI
  `docker compose -f docker-compose.prod.yml exec backend python -m scripts.llm_switch off`).
- **Ajuster le quota d'un testeur** : onglet Utilisateurs > clic sur la ligne >
  override par fonctionnalité (champ vide = quota par défaut).
- **Désactiver un compte** : onglet Utilisateurs > Désactiver (le compte ne peut
  plus se connecter ; données conservées). Impossible sur son propre compte.
- **Feedback in-app** : onglet Feedback (« Marquer traité » grise la ligne).

## 10. Amorçage avant l'arrivée des testeurs

1. Lancer un crawl manuel :
   `docker compose -f docker-compose.prod.yml exec backend python -c "from app.database import SessionLocal; from app.job_search.crawl_runner import run_crawl; run_crawl(SessionLocal)"`
2. Vérifier :
   `docker compose -f docker-compose.prod.yml exec db psql -U postgres -d ats_diagnostic -c "SELECT source, count(*) FROM crawled_listing WHERE is_active GROUP BY source;"`
   → Emploi Dakar présent.
3. Vérifier que `ENABLED_CRAWLERS` (env) inclut `emploi_dakar` et que
   `RELIEFWEB_APPNAME` est renseigné.
4. Depuis le navigateur, recherche « comptable » + « Dakar » → offres locales
   visibles et scorées.
