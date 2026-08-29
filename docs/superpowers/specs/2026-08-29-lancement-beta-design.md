# Lancement en beta fermé — Design

## Contexte

Le produit (copilote de recherche d'emploi pour l'Afrique francophone,
Sénégal d'abord) a été développé et validé en local. Les phases 1-6 du spec
`2026-08-28-sources-afrique-ouest` (sources ReliefWeb / Jobicy / flux RSS
remote, crawler Emploi Dakar, `is_remote` de première classe,
`LocationAutocomplete`) sont **mergées sur `main`**. La phase 7 — validation
terrain — est le sujet de ce spec : ouvrir un **beta fermé** à 5-10
chercheurs d'emploi à Dakar, hébergé, pendant ~3 semaines, pour observer
usage réel, rétention et volonté de payer avant de décider d'une
monétisation.

### État technique constaté

- **Stack** : FastAPI + Next 16 (standalone) + Postgres 16 + MinIO, orchestré
  par `docker-compose.yml`. Tourne uniquement en local (`localhost`).
- **Auth** : JWT (`app/auth/`), `POST /auth/register` **ouvert**, `POST
  /auth/login`, `GET /auth/me`. **Pas de réinitialisation de mot de passe.**
  Token stocké côté client dans le cookie `search_app_token` posé en JS
  (`frontend/context/AuthContext.tsx`) — donc **ni `HttpOnly` ni `Secure`**.
- **`User`** (`app/models/user.py`) : `id`, `email`, `hashed_password`,
  `created_at`. **Pas de champ de consentement, pas de rôle admin.**
- **CORS** : `cors_origins` par défaut `["http://localhost:3000"]`.
- **LLM** : appels Anthropic dans `llm_analyzer` (diagnostic ATS, Haiku),
  `personalization` (CV + lettre, Sonnet), `compatibility` (détail de
  compatibilité par offre, Haiku), `interview_prep` (dossier de prépa),
  `ats_adapters/custom_fields` (préremplissage de formulaire ATS, Sonnet).
  Limites actuelles : `app/rate_limit/limiter.py` — **par heure** uniquement
  (10 diagnostics/h, 10 personnalisations/h), plus des tables de log
  dédiées (`PersonalizationRequestLog`, `CompatibilityRequestLog`,
  `InterviewPrepDossierRequestLog`).
- **Email** : client Resend déjà présent (`app/notifications/resend_client.py`,
  `_send_email(to, subject, html)`), settings `resend_api_key` /
  `resend_from_email` déjà déclarés.
- **Jobs de fond** : `APScheduler` dans le lifespan `main.py` (daily_search,
  application_reminders, crawl).
- **Migrations** : Alembic ; le Dockerfile backend fait `alembic upgrade
  head` au démarrage.
- **Déploiement** : **rien** — aucun compose de prod, aucun reverse-proxy
  applicatif, aucune sauvegarde, aucune observabilité.
- **VPS cible** : déjà provisionné, **nginx + certbot installés sur l'hôte**.
- **Domaine** : `beta.yokkutelabs.com` (le registrar/DNS de `yokkutelabs.com`
  est sous le contrôle de l'utilisateur).

## Objectif

Rendre l'application hébergeable et exploitable pour un beta fermé
responsable :

1. **Hébergement** : compose de prod derrière le nginx/certbot existant du
   VPS, réseau interne cloisonné, procédure de déploiement et de rollback.
2. **Sauvegardes** : dump Postgres + miroir MinIO chiffrés vers un stockage
   objet externe, restauration testée avant lancement.
3. **Accès** : inscription fermée par **codes d'invitation**, durcissement
   cookie/CORS/throttle, **réinitialisation de mot de passe** minimale.
4. **Coûts & quotas LLM** : **plafond mensuel dur par utilisateur et par
   fonctionnalité**, conçu comme préfiguration des futurs paliers
   d'abonnement ; interrupteur global ; journal d'usage.
5. **Observabilité auto-hébergée** : suivi d'erreurs (GlitchTip) + moniteur
   de disponibilité (Uptime Kuma) en conteneurs, rotation des logs Docker.
6. **RGPD minimum viable** : pages Conditions / Confidentialité, recueil du
   consentement à l'inscription, suppression et export de compte.
7. **Dashboard admin** : une zone `/admin` réservée à l'utilisateur (users,
   usage/quotas, feedback, codes d'invitation, interrupteur).
8. **Produit & feedback** : widget de retour in-app, handler d'erreurs
   global, bandeau beta, amorçage des offres.
9. **Runbook + checklist de lancement + déroulé du test terrain.**

### Hors scope (explicitement exclu)

- **Paiement / mobile money, paliers de prix, page de tarification,
  facturation.** Les quotas de cette itération sont un *instrument
  d'observation*, pas un système de facturation. La décision de monétiser
  dépend des conclusions du beta.
- **CI/CD auto-deploy, environnement de staging, IaC (Ansible/Terraform),
  gestionnaire de secrets, agrégation de logs, WAF** — disproportionné pour
  10 testeurs (approche 3 écartée).
- **Sentry auto-hébergé « complet »** (≈ 10 conteneurs, 8+ Go de RAM) —
  remplacé par **GlitchTip**, compatible SDK Sentry, léger. Voir §5 et la
  note RAM.
- **Refonte de l'auth** (OAuth social, 2FA, sessions serveur) — le JWT
  actuel + durcissement cookie suffit pour un beta.
- **App mobile, côté entreprise, côté école, expansion multi-pays active** —
  déjà hors scope du spec afrique-ouest, inchangé.
- **Multi-tenant / rôles fins** — un seul `is_admin` booléen.
- **Internationalisation des devises / slider de salaire multi-devise** —
  chantier séparé déjà noté.

---

## §1 — Hébergement & déploiement

### 1.1 Topologie

Un seul VPS. Le **nginx de l'hôte** (déjà installé) est le seul point
d'entrée public (80/443). Les conteneurs applicatifs n'exposent leurs ports
que sur `127.0.0.1`.

```
Internet
  │  :443
  ▼
nginx (hôte) ── beta.yokkutelabs.com      ─▶ 127.0.0.1:3000  (frontend)
             └─ api.beta.yokkutelabs.com  ─▶ 127.0.0.1:8000  (backend)
                                                │
        docker network "search_internal" (pas de ports publiés)
                                                │
                        ┌───────────────┬───────┴────────┬─────────────┐
                     backend          db (pg)        minio        glitchtip + kuma
```

### 1.2 `docker-compose.prod.yml` (nouveau)

Dérivé de `docker-compose.yml`, différences :

- **`db`** : plus de `ports:` publiés (retire `5432:5432`). Volume `db_data`
  conservé.
- **`minio`** : plus de `ports:` publiés (retire `9000/9001`). Volume
  `minio_data` conservé. Console MinIO accessible au besoin via tunnel SSH.
- **`backend`** : `ports: ["127.0.0.1:8000:8000"]` (loopback uniquement).
  `env_file: ./backend/.env` (fichier présent sur le serveur seulement,
  `chmod 600`, déjà gitignoré). `restart: unless-stopped`.
- **`frontend`** : `ports: ["127.0.0.1:3000:3000"]`. Build arg
  `NEXT_PUBLIC_API_URL=https://api.beta.yokkutelabs.com`.
  `restart: unless-stopped`.
- **`createbuckets`** : inchangé.
- **Logging** : sur `backend`, `frontend`, `db`, `minio` —
  `logging: { driver: json-file, options: { max-size: "10m", max-file: "3" } }`.
- Réseau explicite `search_internal` (bridge) partagé par tous les services.

Le `docker-compose.yml` d'origine **reste tel quel** pour le dev local.

### 1.3 nginx (hôte)

Deux `server` blocks dans `/etc/nginx/sites-available/` (fichiers d'exemple
versionnés dans `deploy/nginx/`) :

- `beta.yokkutelabs.com` → `proxy_pass http://127.0.0.1:3000;`
- `api.beta.yokkutelabs.com` → `proxy_pass http://127.0.0.1:8000;`
  (`client_max_body_size 12m;` pour l'upload de CV ;
  `proxy_read_timeout 120s;` pour les générations synchrones éventuelles ;
  en-têtes `X-Forwarded-For` / `X-Forwarded-Proto` transmis).
- En-têtes de sécurité communs (snippet inclus) : `Strict-Transport-Security`,
  `X-Content-Type-Options nosniff`, `X-Frame-Options DENY`,
  `Referrer-Policy strict-origin-when-cross-origin`.

TLS via `certbot --nginx -d beta.yokkutelabs.com -d api.beta.yokkutelabs.com`
(renouvellement auto déjà en place sur l'hôte).

### 1.4 DNS

Deux enregistrements **A** (+ **AAAA** si IPv6 dispo) : `beta` et `api.beta`
→ IP du VPS.

### 1.5 Durcissement serveur

- `ufw` : autoriser 22, 80, 443 uniquement ; `ufw enable`.
- SSH : `PasswordAuthentication no`, `PermitRootLogin no`, clé publique.
- `fail2ban` : jail `sshd` (souvent déjà présent).
- Docker : ne pas publier de ports en `0.0.0.0` (garantie par le compose de
  prod).

### 1.6 Secrets de prod (`backend/.env` sur le serveur)

Clés nouvelles ou à changer par rapport à `.env.example` :

| Clé | Valeur prod |
|---|---|
| `JWT_SECRET` | 32+ octets aléatoires (`openssl rand -hex 32`) |
| `CORS_ORIGINS` | `["https://beta.yokkutelabs.com"]` |
| `BACKEND_BASE_URL` | `https://api.beta.yokkutelabs.com` |
| `FRONTEND_BASE_URL` | `https://beta.yokkutelabs.com` |
| `RESEND_FROM_EMAIL` | `no-reply@yokkutelabs.com` (domaine vérifié Resend) |
| `COOKIE_DOMAIN` | `beta.yokkutelabs.com` |
| `ENVIRONMENT` | `production` |
| `GLITCHTIP_DSN` | DSN du projet GlitchTip auto-hébergé |
| `LLM_FEATURES_ENABLED` | `true` |
| quotas LLM | voir §4 |

`.env.example` est mis à jour avec toutes ces clés (valeurs vides /
placeholders).

### 1.7 Déploiement & rollback

Script `deploy/deploy.sh` (exécuté sur le serveur) :

```
git fetch && git checkout <tag|commit>
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs --tail=50 backend frontend
curl -fsS https://api.beta.yokkutelabs.com/health
```

- **Migrations** : appliquées automatiquement par le `CMD` du backend
  (`alembic upgrade head`) à chaque redémarrage du conteneur.
- **Rollback** : `git checkout <commit précédent>` puis re-`up -d --build`.
  Les migrations Alembic de ce projet n'ont pas de `downgrade` fiable →
  rollback = **code seulement** ; une migration destructrice doit être
  évitée pendant le beta (ajouts de colonnes nullable uniquement).
- Rappel (mémoire projet) : **le backend n'a pas de volume mount**, tout
  changement backend exige `up -d --build`.

---

## §2 — Sauvegardes & persistance

### 2.1 Postgres

Cron hôte quotidien (`deploy/backup/pg_backup.sh`) :

```
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U postgres ats_diagnostic \
  | gzip | age -r "$AGE_PUBKEY" > db-$(date +%F).sql.gz.age
rclone copy db-$(date +%F).sql.gz.age remote:yokkute-beta-backups/
```

- Chiffrement **`age`** (clé publique sur le serveur, clé privée gardée hors
  serveur par l'utilisateur).
- **Stockage externe** : bucket **Cloudflare R2**, via `rclone` (config S3).
- Rétention : 14 quotidiennes + 8 hebdomadaires, prune dans le script.

### 2.2 MinIO

`mc mirror --overwrite local/personalization remote-r2:yokkute-beta-media/`
quotidien. Le bucket contient les CV uploadés (non régénérables) et les
documents générés.

### 2.3 Restauration testée (bloquant avant lancement)

Procédure dans le runbook : sur une machine jetable, `age -d` → `gunzip` →
`psql` dans un Postgres neuf, vérifier `SELECT count(*)` sur `users`,
`diagnostics`, `personalized_document`. Documenté avec le résultat obtenu.

### 2.4 Garde-fous

- **Ne jamais** `docker compose down -v` (détruit `db_data` / `minio_data`).
- Volumes nommés listés dans le runbook avec cet avertissement.

---

## §3 — Durcissement auth & accès

### 3.1 Codes d'invitation

**Modèle `InviteCode`** (`app/models/invite_code.py`, table `invite_code`) :

| Champ | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `code` | str(16), unique, indexé | généré `secrets.token_urlsafe(9)` |
| `note` | str, nullable | « pour Awa, groupe FB » |
| `created_at` | datetime, not null | |
| `expires_at` | datetime, nullable | défaut : `created_at + 30 j` |
| `used_by_user_id` | int, FK users, nullable | |
| `used_at` | datetime, nullable | |

Migration Alembic (ajout de table).

**`register`** (`app/routers/auth.py`) :

- `UserCreate` gagne `invite_code: str` et `accept_terms: bool` (§3.2).
- Validation dans une **seule transaction** : code existe, `used_by_user_id
  IS NULL`, `expires_at` futur → créer l'utilisateur, stamper le code
  (`used_by_user_id`, `used_at`), `commit`. Sinon `400 « Code d'invitation
  invalide ou déjà utilisé. »`.
- Verrou : `SELECT ... FOR UPDATE` sur la ligne `invite_code` (dialecte non
  SQLite) pour empêcher deux inscriptions concurrentes avec le même code.

**Script admin** `backend/scripts/invites.py` (aussi exposé dans le
dashboard §7) :
`python -m scripts.invites generate --count 15 --note "..."` /
`list` / `revoke <code>`. Lancé via `docker compose exec backend`.

### 3.2 Consentement

- `User` gagne `consent_accepted_at: datetime | None`,
  `consent_version: str | None`. Migration (colonnes nullable).
- Constante `CURRENT_TERMS_VERSION = "2026-09"` (`app/config.py` ou module
  dédié).
- `register` : `accept_terms` doit être `true` sinon `422` ; on stocke
  `consent_accepted_at = utcnow()`, `consent_version = CURRENT_TERMS_VERSION`.
- Frontend : case à cocher obligatoire sur le formulaire d'inscription avec
  liens vers `/conditions` et `/confidentialite` (§6).

### 3.3 Cookie & CORS

- `AuthContext.tsx` : le cookie `search_app_token` est posé avec
  `secure; samesite=lax; domain=beta.yokkutelabs.com` **en production**
  (conditionné sur `process.env.NODE_ENV` / `NEXT_PUBLIC_*`). `path=/`
  conservé.
- **Amélioration retenue** : déplacer la pose/suppression du cookie dans un
  **route handler Next** (`app/api/session/route.ts`) pour le poser
  `HttpOnly` côté serveur ; `proxy.ts` continue de lire le même cookie. Le
  token reste par ailleurs renvoyé au client pour l'en-tête
  `Authorization` des appels API (inchangé).
- `CORS_ORIGINS` = `["https://beta.yokkutelabs.com"]` uniquement.
  `allow_credentials=True` conservé.

### 3.4 Throttle

Dans `app/rate_limit/` (nouveau module `login_throttle.py`, stockage table
`auth_attempt` : `key`, `attempted_at` — `key` = `email` normalisé + IP
forwardée) :

- `/auth/login` : `429` après **8 échecs / 15 min** pour une même `key`.
  Succès purge les tentatives de la `key`.
- `/auth/register` : `429` après **5 tentatives / h** par IP.
- `/auth/forgot-password` : `429` après **5 / h** par (email, IP).

### 3.5 Réinitialisation de mot de passe (minimale)

- **Modèle `PasswordResetToken`** (table `password_reset_token`) :
  `token_hash` (SHA-256 du token envoyé), `user_id` FK, `created_at`,
  `expires_at` (`created_at + 1 h`), `used_at` nullable. Migration.
- `POST /auth/forgot-password {email}` → **toujours `200`** (pas
  d'énumération) ; si l'email existe : invalider les tokens actifs de l'user,
  créer un token, envoyer via `resend_client._send_email` un lien
  `https://beta.yokkutelabs.com/reset-password?token=<token>`.
- `POST /auth/reset-password {token, password}` → hash du token, ligne non
  utilisée et non expirée → `hash_password`, `used_at = now`, invalider les
  autres tokens de l'user.
- Frontend : pages `/mot-de-passe-oublie` et `/reset-password` (petits
  formulaires), lien « Mot de passe oublié ? » sur `/login`.
- Email : gabarit HTML simple ajouté au `resend_client`.

### 3.6 JWT

Expiration 24 h conservée. `JWT_SECRET` fort en prod (§1.6). Pas d'autre
changement.

---

## §4 — Coûts & quotas LLM

### 4.1 Principe

Chaque appel LLM déclenché par un utilisateur est **compté** et **plafonné
par mois calendaire, par fonctionnalité**. Le plafond est un paramètre de
configuration, préfigurant un futur palier d'abonnement « beta / gratuit ».
Objectif : anticiper la structure de facturation **et** observer la réaction
des users quand ils atteignent une limite (frustration ? demande
d'augmentation ? abandon ?).

Les limites **horaires** existantes (`limiter.py`) sont **conservées** comme
protection anti-rafale ; les quotas mensuels sont le nouveau contrôle
principal de volume.

### 4.2 Journal unifié `LlmCallLog` (nouveau)

Table `llm_call_log` — **source de vérité unique** pour l'enforcement des
quotas, les stats d'usage et le dashboard admin.

| Champ | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `user_id` | int, FK users, indexé | |
| `feature` | str, indexé | enum `diagnostic \| cv \| lettre \| compatibility \| interview_prep \| ats_prefill` |
| `model` | str | `claude-haiku-4-5-...`, `claude-sonnet-5` |
| `input_tokens` | int, nullable | depuis `response.usage` si dispo |
| `output_tokens` | int, nullable | idem |
| `created_at` | datetime, not null, indexé | |

Migration Alembic.

- Un helper `record_llm_call(db, user_id, feature, response)` extrait
  `response.usage` (le SDK Anthropic le fournit) et insère la ligne. Appelé
  après chaque appel réussi dans `llm_analyzer`, `personalization`,
  `compatibility`, `interview_prep`, `ats_adapters/custom_fields`.
- Les tables de log spécifiques existantes (`PersonalizationRequestLog`…)
  restent en place (le rate-limit horaire s'appuie dessus) — pas de
  migration de données, additif.

### 4.3 Enforcement

Helper `enforce_monthly_quota(db, user, feature)` dans `app/rate_limit/` :

```
used = count(llm_call_log WHERE user_id=? AND feature=?
                            AND created_at >= <1er du mois courant, UTC>)
limit = user.quota_overrides.get(feature) if user.quota_overrides
        else settings.llm_monthly_quotas[feature]
if used >= limit: raise QuotaExceeded(feature, reset_date=<1er du mois prochain>)
```

- `QuotaExceeded` → HTTP `429` avec corps FR :
  « Tu as atteint ta limite beta de {limit} {libellé} ce mois-ci. Elle se
  réinitialise le {date}. » + un `code: "quota_exceeded"` pour que le
  frontend affiche un encart dédié (pas une erreur générique).
- Appelé **avant** l'appel LLM, à côté du `lock_user_for_rate_limit`
  existant, dans chaque endpoint concerné.
- `User.quota_overrides: JSON | None` (nouvelle colonne, migration) — permet
  d'augmenter le quota d'un testeur précis depuis le dashboard sans
  redéploiement.

### 4.4 Configuration (`config.py` / env)

| Clé | Défaut beta | Fonctionnalité |
|---|---|---|
| `LLM_MONTHLY_QUOTA_DIAGNOSTIC` | `7` | diagnostic ATS |
| `LLM_MONTHLY_QUOTA_CV` | `5` | génération de CV |
| `LLM_MONTHLY_QUOTA_LETTRE` | `5` | lettre de motivation |
| `LLM_MONTHLY_QUOTA_COMPATIBILITY` | `13` | détail de compatibilité par offre |
| `LLM_MONTHLY_QUOTA_INTERVIEW_PREP` | `3` | dossier de prépa entretien |
| `LLM_MONTHLY_QUOTA_ATS_PREFILL` | `10` | préremplissage de formulaire ATS |
| `LLM_FEATURES_ENABLED` | `true` | interrupteur global |

Chargées dans un dict `settings.llm_monthly_quotas`. Valeurs délibérément
basses pour le beta (choix utilisateur : ~1/3 d'une première proposition
jugée trop généreuse) — à réévaluer après le premier dogfooding et selon les
réactions des testeurs face aux limites.

### 4.5 Interrupteur global

- Setting `LLM_FEATURES_ENABLED` **+** flag persistant `app_setting` (table
  clé/valeur, une ligne `llm_features_enabled`) pour pouvoir couper **sans
  redémarrer** le conteneur (toggle depuis le dashboard §7).
- Dépendance FastAPI `require_llm_enabled` partagée par tous les endpoints
  LLM → `503 { code: "llm_paused" }` : « Cette fonctionnalité est en pause
  (capacité beta). Réessaie plus tard. »
- Précédence : si le flag DB existe, il gagne sur l'env.

### 4.6 Console Anthropic (manuel, runbook)

Plafond de dépense mensuel + alertes email à 50 / 80 / 100 %. Filet dur
indépendant du code (protège d'une boucle de retry sur bug).

### 4.7 Frontend

- Encart « quota atteint » réutilisable (déclenché par `code:
  "quota_exceeded"`), affichant le libellé, la limite et la date de reset.
- Sur le dashboard user existant (ou le profil) : une petite jauge
  « utilisation ce mois-ci » par fonctionnalité (lecture de
  `GET /me/usage`, nouvel endpoint qui agrège `llm_call_log`). Sert aussi de
  test de perception : est-ce que voir la jauge change le comportement ?

### 4.8 Modèles

Audit rapide : les appels à faible enjeu sont déjà en Haiku (`llm_analyzer`,
`compatibility`). CV/lettre et préremplissage ATS en Sonnet — **non
touchés** sans contrôle qualité. Pas de changement de modèle dans cette
itération, seulement le comptage.

---

## §5 — Observabilité auto-hébergée

### 5.1 Suivi d'erreurs — GlitchTip

- Service `glitchtip` (+ `glitchtip-db` Postgres + `redis`) dans un
  **`docker-compose.monitoring.yml`** séparé (démarrable/arrêtable
  indépendamment).
- Compatible SDK Sentry : backend `sentry-sdk[fastapi]`, frontend
  `@sentry/nextjs`, `dsn = GLITCHTIP_DSN`.
- **Scrubbing PII** (les CV ne doivent jamais partir) :
  `send_default_pii=False` ; `before_send` qui supprime `request.data` /
  `request.body` pour les routes `/diagnostics`, `/personalization*`,
  `/candidate-profile/cv`, `/job-search/compatibility-detail`,
  `/interview-prep*` ; scrub des variables locales contenant `cv_text`,
  `resume`, `letter`.
- `traces_sample_rate` bas (0.0–0.1).

> **Note RAM.** GlitchTip + son Postgres + Redis ajoutent ~700 Mo–1 Go au
> pied de l'app (backend + Postgres + MinIO). **Décision : VPS 8 Go pour la
> durée du beta**, monitoring lancé en permanence. Sentry « complet »
> auto-hébergé (~10 conteneurs, 8+ Go pour lui seul) est écarté.

### 5.2 Disponibilité — Uptime Kuma

- Service `uptime-kuma` (conteneur unique, volume `kuma_data`) dans
  `docker-compose.monitoring.yml`.
- **Accessible par tunnel SSH uniquement** (`ssh -L 3001:127.0.0.1:3001 …`) —
  aucun `server` block nginx, aucune surface publique supplémentaire.
- Monitors : `https://api.beta.yokkutelabs.com/health` (5 min),
  `https://beta.yokkutelabs.com` (5 min), certificat TLS (expiration).
  Notifications → email (Resend SMTP) ou Telegram.

### 5.3 Logs

- Rotation `json-file` (§1.2).
- `docker compose logs -f <service>` = outil de première ligne (documenté).
- Endpoint `/health` étendu : vérifie la connexion DB (`SELECT 1`) et
  renvoie `{ status, db, version }`.

### 5.4 Santé DB

Check hebdomadaire manuel dans le runbook (`pg_stat_activity`, taille de la
base, espace disque) — historique de deadlock connu sur ce projet
(`BackgroundTasks` + `lock_user_for_rate_limit`).

---

## §6 — RGPD minimum viable

### 6.1 Pages légales

Pages Next statiques `/conditions` et `/confidentialite` (+ lien footer
partout, + liens dans le formulaire d'inscription). Contenu (brouillon
rédigé par l'assistant, **fond juridique validé par l'utilisateur**) :

- Éditeur : yokkutelabs (forme, contact email).
- Hébergeur : nom + pays du VPS.
- Données collectées : email, mot de passe (haché), CV et documents
  uploadés, profil candidat, historique de recherche, candidatures suivies,
  documents générés, logs d'usage LLM.
- Finalités et **base légale : consentement**.
- **Sous-traitants** : Anthropic (traitement des CV/lettres/analyses,
  **transfert hors UE — États-Unis**), Resend (emails), hébergeur.
- Durée de conservation : pendant la vie du compte + 6 mois, puis
  suppression ; suppression immédiate sur demande.
- Droits : accès, rectification, effacement, portabilité, retrait du
  consentement.
- Réclamation : CNIL (France) / Commission de protection des données
  personnelles (Sénégal).
- Cookies : uniquement le cookie de session `search_app_token` (strictement
  nécessaire) — pas de bannière cookies requise.

### 6.2 Suppression de compte

- `DELETE /auth/me` (authentifié, re-confirmation par mot de passe dans le
  corps) :
  - Supprime en cascade toutes les lignes liées : `diagnostics`,
    `personalized_document` + logs, `applications` + `interviews`,
    `saved_job`, `interview_prep_dossier` + logs, `compatibility_request_log`,
    `personalization_request_log`, `llm_call_log`, `notified_listing`,
    `saved_search`, `candidate_profile`, lien `invite_code.used_by_user_id`
    (mis à `NULL`, le code reste consommé), `password_reset_token`,
    `auth_attempt`.
  - Supprime les objets MinIO préfixés par l'utilisateur
    (`storage` : lister + supprimer le préfixe `user/{id}/` ou équivalent —
    à vérifier selon le schéma de clés actuel).
  - **Audit des relations** : seul `User.diagnostics` a
    `cascade="all, delete-orphan"` aujourd'hui. Ajouter les `cascade` ORM +
    `ondelete="CASCADE"` sur les FK manquantes, avec migration. Là où une
    suppression applicative est plus sûre (objets MinIO), la faire
    explicitement dans le handler.
- Frontend : bouton « Supprimer mon compte » dans `/profil`, modale de
  confirmation (ressaisie du mot de passe), déconnexion + redirection.

### 6.3 Export

`GET /auth/me/export` → JSON (profil, diagnostics, documents générés
[métadonnées + contenu texte], candidatures, recherches sauvegardées,
usage). Satisfait la portabilité, coût faible. Téléchargé côté frontend
depuis `/profil`.

---

## §7 — Dashboard admin

### 7.1 Accès

- `User` gagne `is_admin: bool = False` (migration). Positionné à la main en
  base pour le compte de l'utilisateur
  (`UPDATE users SET is_admin = true WHERE email = ...`).
- Dépendance `get_current_admin` (comme `get_current_user` + check
  `is_admin`) → `403` sinon.
- Routeur `app/routers/admin.py`, préfixe `/admin`, **tous les endpoints
  derrière `get_current_admin`**.
- Frontend : segment `/admin` protégé par `proxy.ts` (préfixe protégé) **et**
  par un garde qui vérifie `is_admin` via `GET /auth/me` (le champ est
  ajouté à `UserOut`) ; sinon redirection `/dashboard`.

### 7.2 Endpoints & écrans (lecture d'abord, quelques actions)

| Écran | Endpoint(s) | Contenu / action |
|---|---|---|
| **Vue d'ensemble** | `GET /admin/overview` | nb users, users actifs 7 j, total appels LLM ce mois par feature, tokens cumulés (≈ coût), état interrupteur |
| **Utilisateurs** | `GET /admin/users` | email, date d'inscription, note du code d'invitation, consentement (version + date), dernière activité, usage LLM du mois par feature, quotas/overrides |
| » détail user | `GET /admin/users/{id}`, `PATCH /admin/users/{id}/quota` | ajuster `quota_overrides` ; désactiver le compte |
| **Feedback** | `GET /admin/feedback` | liste des retours in-app (§8), date, user, page, message ; marquer traité |
| **Codes d'invitation** | `GET /admin/invites`, `POST /admin/invites`, `DELETE /admin/invites/{code}` | générer (count + note), lister avec statut, révoquer |
| **Interrupteur LLM** | `POST /admin/llm-toggle {enabled}` | écrit le flag `app_setting` (§4.5) |

- Pas de graphiques : tableaux + quelques compteurs. `framer-motion` /
  `lucide-react` déjà présents suffisent au style.
- Le script `scripts/invites.py` reste disponible comme repli CLI.

---

## §8 — Produit & canal de feedback

### 8.1 Feedback in-app

- **Modèle `Feedback`** (table `feedback`) : `id`, `user_id` FK nullable,
  `page` str, `message` text, `created_at`, `handled_at` nullable. Migration.
- `POST /feedback {page, message}` (authentifié) → insert + notification
  Resend vers l'email admin (`ADMIN_NOTIFY_EMAIL` en config).
- Frontend : bouton flottant « Donner mon avis » (présent sur les écrans
  authentifiés) → modale (textarea + `pathname` courant auto). Confirmation
  toast (`sonner`, déjà présent).

### 8.2 Handler d'erreurs global

`app/main.py` : `@app.exception_handler(Exception)` → log + capture
GlitchTip + réponse `500 { detail: "Une erreur est survenue. L'équipe a été
notifiée.", error_id: <id GlitchTip> }`. Jamais de traceback à l'écran.
Les `HTTPException` explicites (avec messages FR déjà en place) passent
inchangées.

### 8.3 Bandeau beta

Bandeau dismissible (persistant en `localStorage`) au premier login :
« Version beta — certaines parties sont encore brutes. Un souci, une idée ?
Utilise le bouton “Donner mon avis” ou le groupe WhatsApp. »

### 8.4 Passe états vides / erreurs

Vérification rapide (pas exhaustive) : recherche sans résultat, quota
atteint, source indisponible, upload de CV rejeté — tous avec un message FR
clair. Pas de chaîne anglaise visible.

### 8.5 Amorçage des offres

Avant l'arrivée des testeurs : lancer `run_crawl` manuellement sur le
serveur (`docker compose exec backend python -m app.job_search.crawl_runner`
ou équivalent) et vérifier que `crawled_listing` + une recherche Sénégal
renvoient des offres. Confirmer que `ENABLED_CRAWLERS` inclut `emploi_dakar`
et que les sources live (ReliefWeb Sénégal, Jobicy) répondent depuis l'IP du
VPS.

---

## §9 — Runbook & déroulé du test

### 9.1 `docs/RUNBOOK.md`

Sections : provisioning initial ; déploiement ; rollback ; backup manuel &
restauration ; rotation des secrets (`JWT_SECRET`, clés API) ; génération /
révocation de codes ; lecture des stats d'usage ; bascule de l'interrupteur
LLM ; incidents courants —
- requête qui « pend » → `pg_stat_activity`, `docker compose restart
  backend` ;
- disque plein → purge des logs Docker, des vieux dumps ;
- pic de dépense Anthropic → interrupteur + investigation `llm_call_log` ;
- GlitchTip/Kuma qui saturent la RAM → arrêter
  `docker-compose.monitoring.yml`.

### 9.2 Checklist pré-lancement (bloquante)

- [ ] `beta.` et `api.beta.` résolvent, TLS valide sur les deux.
- [ ] Inscription **exige** un code valide ; code déjà utilisé refusé.
- [ ] Login OK ; mot de passe oublié → email reçu → reset OK.
- [ ] CORS : requête depuis une autre origine rejetée.
- [ ] Cookie `search_app_token` : `Secure`, `SameSite=Lax` (et `HttpOnly`
      si route handler en place).
- [ ] Flux complet depuis un **téléphone** : inscription → onboarding →
      recherche (offres sénégalaises visibles) → diagnostic → CV → lettre.
- [ ] Quota : à la N+1ᵉ génération, encart « quota atteint » (pas d'erreur
      générique).
- [ ] Interrupteur LLM : `off` → `503` propre ; `on` → rétabli.
- [ ] Suppression de compte : données + objets MinIO effacés (vérif SQL +
      `mc ls`).
- [ ] Export de compte : JSON téléchargeable et complet.
- [ ] Sauvegarde exécutée + **restauration testée** sur machine jetable.
- [ ] GlitchTip reçoit une erreur test ; Uptime Kuma tous les monitors
      verts.
- [ ] Plafond de dépense Anthropic posé + alertes configurées.
- [ ] Pages `/conditions` et `/confidentialite` en ligne et liées ;
      consentement enregistré à l'inscription.
- [ ] Bouton feedback → email admin reçu.
- [ ] `/admin` accessible au compte admin, `403` pour un compte normal.
- [ ] Crawlers lancés au moins une fois, offres présentes.

### 9.3 Déroulé du test terrain

- **Recrutement** : 5-10 chercheurs d'emploi à Dakar (réseau direct +
  groupes Facebook emploi). Profils variés (jeune diplômé, expérimenté,
  reconversion).
- **Envoi** : à chacun — 1 code d'invitation nominatif + pitch 3 lignes
  (ce que c'est, ce qu'on aimerait qu'il essaie : onboarding → 1 recherche →
  1 candidature complète) + lien du **groupe WhatsApp** dédié.
- **Lancement** : visio de groupe ou individuelle, 1ʳᵉ recherche guidée,
  observation des blocages.
- **Pendant ~3 semaines** : usage libre, point hebdo (WhatsApp + 1 appel
  court), relevé des retours in-app.
- **Grille d'observation** (reprise du spec afrique-ouest §7b) : blocages
  d'onboarding, pertinence ressentie des offres, rétention (revient-il sans
  qu'on le relance ?), réaction aux quotas, volonté de payer et moyen
  (mobile money ?).
- **Sortie** : court document de conclusions décidant la suite (paliers
  d'abonnement, plus de sources, ajustement des quotas, test de prix…).

---

## Flux de données

### Inscription

```
formulaire (email, mot de passe, code, accept_terms)
  │
  ▼  POST /auth/register
throttle IP (5/h) ──dépassé──▶ 429
  │ ok
  ▼
transaction:
  SELECT invite_code FOR UPDATE
    code inexistant / utilisé / expiré ──▶ 400 (rollback)
  INSERT user (consent_accepted_at, consent_version)
  UPDATE invite_code (used_by_user_id, used_at)
  COMMIT
  ▼
201
```

### Appel LLM (ex. génération de CV)

```
POST /personalization/... (authentifié)
  │
  ├─ require_llm_enabled ──flag off──▶ 503 {code: llm_paused}
  ├─ lock_user_for_rate_limit(user)
  ├─ check_personalization_rate_limit (horaire) ──dépassé──▶ 429
  ├─ enforce_monthly_quota(user, "cv")
  │     used = count(llm_call_log WHERE user, feature=cv, mois courant)
  │     used >= limit ──▶ 429 {code: quota_exceeded, reset_date}
  │ ok
  ▼
appel Anthropic (Sonnet)
  ▼
record_llm_call(user, "cv", response.usage)  → INSERT llm_call_log
  ▼
réponse (job de génération)
```

### Sauvegarde quotidienne (cron hôte)

```
pg_dump ──gzip──age──▶ db-DATE.sql.gz.age ──rclone──▶ R2/B2
mc mirror local/personalization ──────────────────────▶ R2/B2 (media)
prune local + distant (14 quotidiennes + 8 hebdo)
```

---

## Gestion d'erreurs

- **Inscription concurrente, même code** : `SELECT ... FOR UPDATE` sur
  `invite_code` sérialise ; le second obtient `400`.
- **Email de reset** : échec Resend loggé, `POST /auth/forgot-password`
  renvoie quand même `200` (pas de fuite d'information ni d'échec bloquant
  côté user ; l'incident remonte dans GlitchTip).
- **Quota / interrupteur** : `429` / `503` avec `code` machine → encart
  dédié frontend, jamais l'erreur générique.
- **Suppression de compte** : opération transactionnelle DB ; la purge MinIO
  qui échoue est loggée et re-tentable (script de nettoyage des orphelins
  dans le runbook), mais ne bloque pas la suppression du compte.
- **GlitchTip indisponible** : le SDK bufferise/drop silencieusement, aucun
  impact sur les requêtes.
- **Monitoring qui pèse sur la RAM** : `docker-compose.monitoring.yml`
  arrêtable sans toucher à l'app.
- **Handler global** : toute exception non gérée → `500` générique FR + id
  GlitchTip, jamais de traceback.

---

## Tests

Ciblés sur le risque (contrainte d'économie de tokens du projet). SQLite en
unitaire, navigateur réel + Postgres/Docker pour les flux à risque.

| Cible | Type | Notes |
|---|---|---|
| Validation code d'invitation | Unitaire (SQLite) | inexistant / expiré / déjà utilisé / OK ; le code est bien stampé ; `accept_terms=false` → 422 |
| Concurrence sur un code | Unitaire | 2 inscriptions même code → une seule réussit (best-effort en SQLite ; vrai test en Postgres si rapide) |
| Throttle login/register | Unitaire | 429 après seuil, purge au succès |
| Cycle token de reset | Unitaire | création, usage unique, expiration, invalidation des autres |
| `enforce_monthly_quota` | Unitaire | seed `llm_call_log`, dépassement → 429 avec `reset_date` correct ; `quota_overrides` prioritaire ; bascule au 1er du mois |
| `record_llm_call` | Unitaire | extraction `usage` (mock réponse Anthropic), insertion |
| Interrupteur LLM | Unitaire | flag env / flag DB / précédence ; 503 sur tous les endpoints LLM |
| Suppression de compte | Unitaire (SQLite) | toutes les tables liées vidées ; `invite_code.used_by_user_id` → NULL ; user parti |
| Export de compte | Unitaire | structure JSON complète pour un user seedé |
| Garde admin | Unitaire | `403` sans `is_admin`, `200` avec |
| Feedback | Unitaire | insert + appel Resend mické |
| Flux complet | **Navigateur réel + Postgres/Docker** | inscription avec code → onboarding → recherche (offres SN) → diagnostic → CV → lettre → quota atteint → feedback → suppression de compte ; console propre, `docker logs` propres. Rappel : `up -d --build backend` après modif backend. |
| Déploiement | Manuel | `deploy.sh` sur le serveur, `/health` vert, TLS OK, CORS bloque les autres origines |
| Restauration backup | Manuel (bloquant) | dump → machine jetable → `psql` → comptages cohérents |

---

## Découpage en phases (branche `feature/beta-launch`, commits scopés)

1. **Infra** : `docker-compose.prod.yml`, `deploy/nginx/*.conf`,
   `deploy/deploy.sh`, `deploy/backup/*`, `.env.example` complété,
   `/health` étendu (check DB), `docs/RUNBOOK.md` (provisioning + deploy +
   backup). Pas de code applicatif.
2. **Auth & accès** : modèle `InviteCode` + migration + `register` +
   `scripts/invites.py` ; colonnes consentement + `CURRENT_TERMS_VERSION` ;
   cookie `Secure`/`HttpOnly` + route handler Next ; `CORS_ORIGINS` prod ;
   throttle login/register/forgot ; `PasswordResetToken` + endpoints +
   pages frontend + gabarit email. Tests unitaires.
3. **Quotas & coûts LLM** : `LlmCallLog` + migration + `record_llm_call`
   câblé aux 6 sites d'appel ; `enforce_monthly_quota` + config des quotas ;
   `app_setting` + interrupteur + `require_llm_enabled` ; `GET /me/usage` +
   jauge frontend + encart « quota atteint ». Tests unitaires.
4. **RGPD** : pages `/conditions` et `/confidentialite` (brouillon) ;
   `DELETE /auth/me` + audit/ajout des cascades + purge MinIO + bouton
   frontend ; `GET /auth/me/export` + bouton. Tests unitaires.
5. **Observabilité** : `docker-compose.monitoring.yml` (GlitchTip + deps,
   Uptime Kuma, ports en `127.0.0.1` — accès tunnel SSH) ; `sentry-sdk`
   backend + `@sentry/nextjs` frontend + scrubbing PII ; section runbook
   monitoring (dont la commande de tunnel).
6. **Dashboard admin** : `is_admin` + migration + `get_current_admin` ;
   `app/routers/admin.py` (overview / users / quota / feedback / invites /
   toggle) ; segment frontend `/admin`. `is_admin` dans `UserOut`. Tests
   garde + endpoints clés.
7. **Feedback & polish** : modèle `Feedback` + `POST /feedback` + widget ;
   handler d'exception global ; bandeau beta ; passe états vides/erreurs FR.
8. **Vérif navigateur réelle de bout en bout** sur le serveur + passage
   complet de la checklist §9.2 + amorçage des crawlers + restauration
   testée.
9. **Lancement du test terrain** (hors code) : recrutement, envoi des codes,
   visio de lancement, suivi 3 semaines, doc de conclusions.

---

## Décisions et alternatives écartées

- **nginx/certbot de l'hôte plutôt que Caddy en conteneur** : déjà installés
  et opérationnels sur le VPS ; ajouter Caddy dupliquerait la terminaison
  TLS. Les conteneurs n'exposent que `127.0.0.1`.
- **GlitchTip plutôt que Sentry auto-hébergé** : compatibilité SDK Sentry
  totale, ~3 conteneurs contre ~10, tient sur le VPS. Sentry complet exige
  8+ Go pour lui seul.
- **Uptime Kuma plutôt qu'UptimeRobot SaaS** : auto-hébergé (souhait
  explicite), conteneur unique, notifications intégrées.
- **Quotas mensuels par fonctionnalité plutôt que simple rate-limit** :
  double objectif — préfigurer les paliers d'abonnement et **observer la
  réaction des users** face à une limite, donnée clé pour la décision de
  monétisation.
- **`llm_call_log` unifié plutôt que réutiliser les tables de log
  existantes** : une seule source pour quotas + stats + dashboard + future
  facturation ; les tables existantes restent pour le rate-limit horaire
  (additif, aucune migration de données).
- **Interrupteur DB en plus de l'env** : couper la dépense sans redémarrer
  le conteneur (le backend n'a pas de hot-reload en prod).
- **Reset de mot de passe minimal plutôt que rien** : un testeur qui oublie
  son mot de passe abandonnerait ; plutôt que rien ou une réinitialisation
  manuelle par l'admin, un flux token/email court et standard.
- **Un seul `is_admin` booléen plutôt qu'un système de rôles** : un seul
  admin (l'utilisateur), YAGNI.
- **Codes d'invitation à usage unique nominatifs** : on sait exactement qui
  est derrière chaque compte, essentiel pour un panel de 10 personnes.
- **Pas de CI/CD** : `git pull` + `up -d --build` manuel suffit à cette
  échelle ; un déploiement auto ajoute de la surface pour zéro gain sur 10
  testeurs.

## Décisions tranchées (2026-08-29)

1. **Stockage des sauvegardes** : **Cloudflare R2** (pas de frais d'egress,
   API S3). L'utilisateur fournira endpoint + clé + secret d'un bucket R2.
2. **RAM du VPS** : **8 Go** pour la durée du beta (monitoring permanent,
   alertes actives 24/7). Redimensionnement à la baisse possible après.
3. **Uptime Kuma** : **accès par tunnel SSH uniquement** pendant le beta,
   pas de `server` block nginx `status.` — pas de surface publique
   supplémentaire. Les alertes importantes partent par email/Telegram.
4. **Valeurs de quotas** (§4.4) : fixées basses (voir table), à réévaluer
   après le dogfooding.
