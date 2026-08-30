# Runbook — Beta yokkutelabs

Opérations du beta fermé (`beta.yokkutelabs.com`). Les plans Beta 2 à 7
ajoutent leurs sections au fil de leur exécution.

## 1. Provisioning initial du VPS (une fois)

1. VPS Debian 12, **8 Go RAM**. DNS : enregistrements **A** (+ **AAAA** si
   IPv6) `beta` et `api.beta` de `yokkutelabs.com` → IP du VPS.
2. `apt update && apt install -y docker.io docker-compose-plugin age rclone git ufw fail2ban`
3. Pare-feu : `ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw enable`
4. SSH : dans `/etc/ssh/sshd_config` → `PasswordAuthentication no`,
   `PermitRootLogin no` ; `systemctl restart ssh`.
5. `git clone <repo> /opt/search && cd /opt/search && git checkout feature/beta-launch`
6. **Deux fichiers d'environnement distincts :**
   - `/opt/search/.env` (`chmod 600`) — lu par `docker compose` pour
     l'interpolation. Depuis `.env.prod.example` :
     `POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
     (obligatoires : le compose de prod échoue si l'un manque — pas de
     valeur par défaut faible). Générer chacun avec `openssl rand -hex 32`
     (ou `-base64 24` pour l'user MinIO).
   - `/opt/search/backend/.env` (`chmod 600`) — injecté dans le conteneur
     backend. Depuis `backend/.env.example` :
     - `JWT_SECRET` : `openssl rand -hex 32`
     - `CORS_ORIGINS=["https://beta.yokkutelabs.com"]`
     - `BACKEND_BASE_URL=https://api.beta.yokkutelabs.com`
     - `FRONTEND_BASE_URL=https://beta.yokkutelabs.com`
     - `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, et les
       clés de sources d'offres (France Travail, Adzuna…)
     - **Ne PAS** y remettre `DATABASE_URL` / `MINIO_*` : le compose de prod
       les construit et les surcharge à partir de `/opt/search/.env`.
7. nginx :
   - `cp deploy/nginx/security-headers.conf /etc/nginx/snippets/beta-security-headers.conf`
   - `cp deploy/nginx/beta.yokkutelabs.com.conf /etc/nginx/sites-available/`
   - `cp deploy/nginx/api.beta.yokkutelabs.com.conf /etc/nginx/sites-available/`
   - `ln -s ../sites-available/beta.yokkutelabs.com.conf /etc/nginx/sites-enabled/`
   - `ln -s ../sites-available/api.beta.yokkutelabs.com.conf /etc/nginx/sites-enabled/`
   - `nginx -t && systemctl reload nginx`
8. TLS : `certbot --nginx -d beta.yokkutelabs.com -d api.beta.yokkutelabs.com`
9. Premier déploiement : `deploy/deploy.sh`
10. Sauvegardes :
    - `cp deploy/backup/rclone.conf.example deploy/backup/rclone.conf` (renseigner
      depuis Cloudflare > R2 > API Tokens)
    - `cp deploy/backup/backup.env.example deploy/backup/backup.env`
      (`RCLONE_CONFIG=/opt/search/deploy/backup/rclone.conf`, `R2_BUCKET=…`,
      `MINIO_ROOT_USER`/`PASSWORD` = mêmes valeurs que `/opt/search/.env`)
    - Générer la paire `age` **hors serveur** : `age-keygen -o key.txt` ;
      copier **uniquement** la clé publique `age1…` dans `AGE_RECIPIENT` ;
      garder `key.txt` (clé privée) en lieu sûr hors serveur.
    - Cron :
      ```
      0 2 * * * cd /opt/search && deploy/backup/pg_backup.sh >> /var/log/pg_backup.log 2>&1
      30 2 * * * cd /opt/search && deploy/backup/minio_mirror.sh >> /var/log/minio_mirror.log 2>&1
      ```

## 2. Déploiement courant

`cd /opt/search && deploy/deploy.sh` (ou `deploy/deploy.sh <tag-ou-commit>`).
Rappel : le backend n'a pas de volume mount — le rebuild est fait par le
script. Vérif : `curl -s https://api.beta.yokkutelabs.com/health`.
Les migrations Alembic sont appliquées automatiquement au démarrage du
conteneur backend (`alembic upgrade head` dans son `CMD`).

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
