# Site vitrine public — Design

## Contexte

Aujourd'hui `frontend/app/page.tsx` fait un redirect client : un visiteur
non connecté qui arrive sur `/` tombe directement sur `/login`, un
formulaire de connexion, sans aucune présentation de la solution. Pour une
structure comme Yokkute Labs qui ouvre une beta « dans les règles de
l'art », c'est un manque de sérieux : la première impression d'un
prospect, d'un partenaire ou d'un journaliste est un champ mot de passe.

Ce spec ajoute une **landing publique unique sur `/`** qui présente la
proposition de valeur et les fonctionnalités clés, avec des CTA adaptés au
fait que la beta est **sur invitation** : « Se connecter » pour ceux qui
ont un code, et un formulaire « Demander un accès » pour les autres. Un
visiteur déjà connecté est toujours renvoyé sur `/dashboard`.

### État technique constaté

- **Frontend** : Next 16.3.2 + Turbopack, App Router, `frontend/`. Root
  layout (`app/layout.tsx`) enveloppe tout dans `<Providers>` +
  `<AuthProvider>` ; polices Outfit (`--font-display`) + Inter
  (`--font-sans`). Design system : `components/ui/*` (Button, Input, Card,
  Badge, ScoreRing…), tokens et utilitaires dans `app/globals.css`
  (primaire indigo `hsl(239 84% 67%)`, accent teal `hsl(172 66% 50%)`,
  `.gradient-mesh`, `.text-gradient`, `.gradient-primary`). framer-motion
  déjà utilisé (`app/(auth)/login/page.tsx`).
- **`app/page.tsx`** : `"use client"`, lit `useAuth()`, `router.replace(user
  ? "/dashboard" : "/login")`, affiche un spinner en attendant.
- **`proxy.ts`** (ex-`middleware.ts`, renommé par Next 16) : garde
  serveur qui vérifie seulement la présence du cookie `search_app_token`.
  `PROTECTED_PREFIXES` = dashboard/offres/candidatures/diagnostic/profil/
  onboarding/admin. `AUTH_PATHS` = login/mot-de-passe-oublie/reset-password
  → si cookie présent, redirige vers `/dashboard`. `/` n'est pas dans le
  `matcher`.
- **Pages légales** : `app/conditions/` et `app/confidentialite/` existent
  déjà (ajoutées en Beta 4, brouillon FR avec placeholders `[À CONFIRMER]`).
  `components/common/LegalFooter.tsx` existe.
- **Marque** : « Search » en dur dans `app/(auth)/login/page.tsx:88`,
  `app/layout.tsx` (metadata `title`/`description`), badge « v3 » en dur
  dans `components/layout/Sidebar.tsx:24-28`. `lib/navConfig.ts` importe
  `Search` (l'icône lucide, pour l'entrée « Offres ») — sans rapport, à ne
  pas toucher.
- **Admin** : `app/(app)/admin/` (`layout.tsx` garde client +
  `page.tsx` 4 onglets), `components/admin/{Overview,Users,Invites,
  Feedback}Tab.tsx`. Backend `app/routers/admin.py`, routeur avec
  `dependencies=[Depends(get_current_admin)]`, schémas dans
  `app/schemas/admin.py`. `lib/api.ts` `export const admin = {…}`.
- **Backend** : FastAPI. `app/models/` un fichier par modèle. Migrations
  Alembic (le Dockerfile fait `alembic upgrade head` au démarrage).
  `app/rate_limit/auth_throttle.py` : table `auth_attempt` (`action`,
  `identifier`, `created_at`), dict `_LIMITS` par action, fonctions
  `record_auth_attempt` / `check_auth_throttle` / `clear_auth_attempts`,
  exception `AuthThrottleExceeded`.
- **Email** : `app/notifications/resend_client.py` — `_send_email(to,
  subject, html)`, `send_feedback_notification(admin_email, user_email,
  page, message)` (no-op si `admin_email` vide, HTML échappé),
  `EmailSendError`. `config.admin_notify_email` (défaut `""`).
- **Feedback** (précédent similaire) : modèle `Feedback` (`user_id` SET
  NULL, `page`, `message`, `created_at`, `handled_at`) ; routeur
  `app/routers/feedback.py` `POST /feedback` (authed → `db.add` + commit →
  notif Resend en `try/except EmailSendError` non bloquant → 204).
- **`lib/api.ts`** : `API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api"`,
  helper `request<T>()` (ligne 69, ajoute le header `Authorization`),
  `requestBlob()`. `ApiError` porte `.code`.
- **Cible** : chercheurs d'emploi à Dakar, **majoritairement sur
  téléphone**. FR uniquement.
- **yokkutelabs.com** : site d'agence (vert, logo carte d'Afrique, nav
  Home/About/Services/Contact, FR/EN). Le produit n'y figure pas. Footer :
  `solution@yokkutelabs.com`, Dakar.

## Objectif

Remplacer le redirect de `/` par une vraie page de présentation publique,
en une seule page, FR, cohérente avec le design system du produit, avec :

1. une proposition de valeur claire et les 4 fonctionnalités clés ;
2. des CTA adaptés à une beta sur invitation (« Se connecter » +
   « Demander un accès ») ;
3. un formulaire de demande d'accès maîtrisé (données chez nous,
   anti-spam, visible dans `/admin`) ;
4. le renvoi systématique d'un visiteur connecté vers `/dashboard`.

### Hors périmètre

- Le **choix du nom définitif** du produit : décision différée. Le site
  affiche « Search » (sans le badge « v3 »), via un token unique pour que
  le renommage soit trivial.
- Pages « À propos » et « Contact » dédiées (une seule landing ; le
  rattachement corpo et le contact tiennent dans le footer).
- i18n / version anglaise (structure laissée prête, non câblée).
- Indexation moteurs : la landing est livrée en `noindex` (produit encore
  nommé « Search », beta fermée) ; passage en indexable au lancement
  public avec le vrai nom.
- Toute modification de l'hébergement : la landing est servie par l'app
  Next existante, même conteneur, route `/`.
- Système de liste d'attente avec relances automatiques : une demande
  d'accès = une ligne + un email à l'admin ; la suite est manuelle.

## Architecture

### Routing et rendu

- `app/page.tsx` devient un **server component** qui rend la landing.
  Plus de `"use client"`, plus de redirect JS, plus de spinner.
- **Visiteur connecté → `/dashboard`** : dans `proxy.ts`, ajouter une
  règle « si `pathname === "/"` et cookie `search_app_token` présent →
  `NextResponse.redirect("/dashboard")` », et ajouter `"/"` au `matcher`.
  Redirection côté serveur, aucun flash. Le visiteur anonyme voit la
  landing.
- **Consulter les guides** `frontend/node_modules/next/dist/docs/01-app/`
  avant d'écrire : conventions `metadata` / `generateMetadata`, server vs
  client components, `matcher` de middleware/proxy en v16.
- La landing garde le root layout (donc `<AuthProvider>` monte et appelle
  `fetchMe` côté client → 401 silencieux pour un anonyme, sans effet
  visible). Acceptable ; pas d'optimisation ici.

### Découpage frontend

Nouveau dossier `frontend/components/marketing/` :

- `MarketingHeader.tsx` — logo + lien « Se connecter » (`/login`) +
  bouton « Demander un accès » (ancre `#acces`). Sticky léger. Distinct du
  `Sidebar` de l'app.
- `Hero.tsx` — titre + sous-titre + 2 CTA + maquette UI stylisée.
- `ProblemSection.tsx` — 2-3 phrases sur la douleur.
- `FeatureGrid.tsx` — 4 `FeatureCard` (titre, phrase, mini-visuel/icône).
- `HowItWorks.tsx` — 3 étapes numérotées.
- `AccessSection.tsx` — encart « beta fermée » + `<AccessRequestForm>`.
- `AccessRequestForm.tsx` — client component : champs email + note +
  honeypot caché ; appelle `requestAccess()` ; états succès/erreur ; toast.
- `MarketingFooter.tsx` — « un produit Yokkute Labs » (lien
  `https://yokkutelabs.com`), Conditions / Confidentialité / Contact
  (`mailto:solution@yokkutelabs.com`), mention beta.

Composant partagé `frontend/components/common/Logo.tsx` (icône `Sparkles`
dans une pastille dégradée + wordmark `PRODUCT_NAME`), réutilisé par
`MarketingHeader`, `Sidebar` et la page `login`.

`frontend/lib/brand.ts` :

```ts
export const PRODUCT_NAME = "Search";
export const TAGLINE = "Le copilote IA pour décrocher ton job — pensé pour Dakar et l'Afrique de l'Ouest.";
export const PARENT_NAME = "Yokkute Labs";
export const PARENT_URL = "https://yokkutelabs.com";
export const CONTACT_EMAIL = "solution@yokkutelabs.com";
```

### Contenu de la landing (FR, page unique au scroll)

1. **Header** — logo, « Se connecter », « Demander un accès ».
2. **Hero** — H1 proposition de valeur ; sous-titre ; CTA primaire
   « Demander un accès » (→ `#acces`), CTA secondaire « J'ai un code —
   me connecter » (→ `/login`). À droite : maquette stylisée reprenant le
   vocabulaire visuel de `/login` (score ring « 92 % », carte d'offre
   « Lead Developer · Dakar », barre de progression), en HTML/CSS, pas de
   capture.
3. **Le problème** — « Chercher un emploi à Dakar, c'est des offres
   éparpillées sur dix sites, un CV jamais adapté au poste, et des
   entretiens préparés à l'aveugle. »
4. **Fonctionnalités clés** — 4 blocs :
   - **Diagnostic ATS instantané** — score de lisibilité + mots-clés
     manquants, en quelques secondes.
   - **Offres locales, scorées pour toi** — Emploi Dakar, France Travail,
     offres remote… agrégées, avec un score de compatibilité par offre.
   - **CV & lettre générés par IA** — personnalisés pour l'offre,
     éditables, transparents sur ce qui a été modifié.
   - **Préparation d'entretien IA** — questions probables, recherche sur
     l'entreprise, checklist de coaching.
5. **Comment ça marche** — 3 étapes : ① dépose ton CV → ② reçois ton
   diagnostic et tes offres compatibles → ③ génère tes candidatures et
   prépare l'entretien.
6. **Beta fermée** (`id="acces"`) — encart transparent : « On ouvre
   l'accès progressivement à un petit groupe de chercheurs d'emploi à
   Dakar. Laisse-nous ton email, on te recontacte. » + `<AccessRequestForm>`.
7. **Footer** — « un produit Yokkute Labs » + liens légaux + contact +
   « Version beta ».

### Identité visuelle

- Réutilise le design system **produit** (indigo/teal, Outfit + Inter,
  `components/ui/*`, utilitaires `globals.css`). **Pas** d'alignement sur
  le vert Yokkute : la cohérence avec l'app dans laquelle le visiteur
  entre prime ; le lien « un produit Yokkute Labs » assure le
  rattachement.
- Livraison en thème clair (comme le reste de l'app).
- framer-motion pour des fade-in/slide-in légers au scroll, cohérents avec
  `/login`. Respect de `prefers-reduced-motion`.
- Responsive **mobile-first** : le hero passe en une colonne, la maquette
  stylisée sous le texte ; grille de fonctionnalités en une colonne ;
  cibles tactiles ≥ 44 px.
- `metadata` dans `page.tsx` : `title` = `` `${PRODUCT_NAME} — recherche
  d'emploi assistée par IA` ``, `description` = `TAGLINE`, OpenGraph
  (`type: website`, `locale: fr_FR`, `images: ["/og.png"]`),
  `robots: { index: false, follow: false }`. Image `frontend/public/og.png`
  statique (1200×630).

### Backend — « Demander un accès »

**Modèle** `app/models/access_request.py` → `AccessRequest` :

| colonne | type | notes |
|---|---|---|
| `id` | int PK | |
| `email` | `String(320)` non null | index simple (pas unique — on garde chaque demande) |
| `note` | `Text` non null, `default=""` | « qui es-tu, où en es-tu » |
| `source_ip` | `String(64)` nullable | anti-abus ; scrubbé par `_before_send` Sentry si jamais loggé |
| `created_at` | `DateTime` non null, `default=utcnow`, index | |
| `handled_at` | `DateTime` nullable | rempli quand l'admin traite la demande |

Migration Alembic (`server_default` inutile, table neuve).

**Schémas** `app/schemas/access_request.py` :
- `AccessRequestIn` : `email: EmailStr`, `note: str = ""`
  (`max_length=1000`), `company: str = ""` (honeypot — doit rester vide).
- `AdminAccessRequestOut` : `id`, `email`, `note`, `created_at`,
  `handled_at`.

**Endpoint public** `app/routers/access_requests.py` —
`POST /access-requests`, **sans authentification** :

1. `client_ip` via `app/auth/http.py::client_ip` (déjà durci XFF —
   dernier hop).
2. Si `payload.company` non vide (honeypot rempli) → **204 immédiat**,
   rien d'écrit (silencieux).
3. `check_auth_throttle(db, action="access_request", identifier=client_ip)`
   — nouvelle entrée dans `_LIMITS` d'`auth_throttle.py` :
   `"access_request": (5, timedelta(minutes=60))`. Si `AuthThrottleExceeded`
   → **429** `{code: "rate_limited", message: "Trop de demandes. Réessaie
   plus tard."}`.
4. `record_auth_attempt(db, action="access_request", identifier=client_ip)`.
5. `db.add(AccessRequest(email=payload.email.lower().strip(),
   note=payload.note.strip()[:1000], source_ip=client_ip))` + `db.commit()`.
6. Notif admin en `try/except EmailSendError` non bloquant :
   `send_access_request_notification(get_settings().admin_notify_email,
   payload.email, payload.note)` — nouvelle fonction dans `resend_client.py`
   calquée sur `send_feedback_notification` (no-op si email admin vide,
   HTML échappé via `_safe_href`/escaping existant).
7. **Toujours 204** (même si le même email a déjà demandé — pas
   d'énumération, pas de feedback exploitable).

Enregistrer le routeur dans `main.py`.

**Endpoints admin** dans `app/routers/admin.py` (donc déjà derrière
`get_current_admin`) :
- `GET /admin/access-requests` → `list[AdminAccessRequestOut]`, triées
  `created_at` desc, paramètre `?pending=true` optionnel (filtre
  `handled_at IS NULL`).
- `POST /admin/access-requests/{id}/handled` → 204, pose
  `handled_at = utcnow()` (idempotent : ne réécrit pas si déjà posé).

Schémas dans `app/schemas/admin.py` (ou import depuis
`access_request.py`).

**RGPD** : `AccessRequest` n'est pas rattaché à un `user_id`. Les demandes
non converties sont purgées manuellement (ajout d'une ligne dans le
RUNBOOK §7 : `DELETE FROM access_requests WHERE handled_at IS NULL AND
created_at < now() - interval '90 days';`). Une demande dont l'email
correspond à un compte créé ensuite n'est pas liée automatiquement — le
`delete_account` n'a donc rien à purger ici, mais le RUNBOOK note qu'une
suppression de compte peut s'accompagner d'un `DELETE FROM access_requests
WHERE email = :email`.

### Frontend — demande d'accès

- `lib/api.ts` : `requestAccess(email: string, note: string): Promise<void>`
  — POST `/access-requests` **sans** `Authorization`. Comme `request()`
  ajoute le header token, prévoir un petit `fetch` dédié (ou un paramètre
  `anonymous` à `request()`), qui : envoie `{ email, note, company: "" }`,
  traite 204 comme succès, 429 comme erreur « rate_limited », lève
  `ApiError` sinon.
- `AccessRequestForm.tsx` : champs « Email » + « Où en es-tu dans ta
  recherche ? » (textarea, optionnel) + champ honeypot `company` masqué
  (`aria-hidden`, `tabIndex={-1}`, hors flux visuel, jamais `display:none`
  seul — un wrapper positionné hors écran). Bouton `Button` du design
  system. Succès → remplace le formulaire par un message « Merci, on te
  recontacte bientôt. » + `toast.success`. Erreur → `toast.error` avec le
  message renvoyé.

### Frontend — nettoyage marque

- `components/layout/Sidebar.tsx` : retirer le `<span>` « v3 », utiliser
  `<Logo>` ou `PRODUCT_NAME`.
- `app/(auth)/login/page.tsx:88` : `Search` → `PRODUCT_NAME` (idéalement
  `<Logo>`).
- `app/layout.tsx` : `metadata.title` / `description` depuis `brand.ts`.
- `components/admin/*`, `lib/navConfig.ts` : ne pas toucher `Search`
  l'icône lucide.

## Flux de données

```
Visiteur anonyme ─GET /─▶ proxy.ts (pas de cookie) ─▶ app/page.tsx (landing SSR)
Visiteur connecté ─GET /─▶ proxy.ts (cookie présent) ─▶ 307 /dashboard

Formulaire "Demander un accès"
  AccessRequestForm ─POST /api/access-requests {email,note,company:""}─▶
    access_requests router
      honeypot? ─oui─▶ 204 (no-op)
      throttle IP (5/h) ─dépassé─▶ 429
      INSERT access_requests ; COMMIT
      send_access_request_notification(admin) [try/except, non bloquant]
      ─▶ 204
  ─▶ toast succès + message de remerciement

Admin
  /admin ▸ onglet "Demandes d'accès"
    GET /admin/access-requests?pending=true ─▶ liste
    [Traiter] ─POST /admin/access-requests/{id}/handled─▶ 204
    [Générer un code] ─▶ onglet "Invitations" avec l'email pré-rempli
```

## Gestion des erreurs

- `POST /access-requests` : `422` (email invalide, note > 1000) géré par
  FastAPI/Pydantic ; `429` `{code: "rate_limited"}` sur throttle ; `500`
  attrapé par le handler global d'exceptions (Beta 7, message FR
  générique + `error_id`). Le honeypot ne renvoie **jamais** d'erreur
  (204 silencieux) pour ne pas informer un bot.
- L'échec de l'email de notif ne fait **pas** échouer la requête (log +
  `try/except EmailSendError`, comme `feedback`).
- Frontend : si `requestAccess` lève, le formulaire reste rempli et
  affiche `toast.error` ; pas de perte de saisie.
- `proxy.ts` : la nouvelle règle `/` ne doit pas boucler — elle ne
  s'applique qu'à `pathname === "/"` exact, `/dashboard` n'est pas
  concerné.

## Tests

### Backend (pytest, pattern `tests/_helpers`)

- `POST /access-requests` : 204 sur payload valide + **1 ligne** en base
  avec email normalisé (minuscule/trim) ; honeypot rempli → 204 et
  **0 ligne** ; 6ᵉ appel de la même IP en 1 h → 429 `code=rate_limited` ;
  email invalide → 422 ; note > 1000 caractères → 422 ; `admin_notify_email`
  vide → pas d'appel Resend, 204 quand même ; `EmailSendError` → 204 quand
  même.
- `GET /admin/access-requests` : 401/403 sans admin ; renvoie les demandes
  triées desc ; `?pending=true` filtre les traitées.
- `POST /admin/access-requests/{id}/handled` : pose `handled_at` ;
  idempotent ; 404 si id inconnu ; 403 sans admin.
- `auth_throttle` : `"access_request"` bien présent dans `_LIMITS`.

### Frontend

- `tsc --noEmit` + `next build` verts.
- **Vérification navigateur réelle** (règle projet — `claude-in-chrome`,
  contre la stack dockerisée) :
  - `/` en anonyme → la landing s'affiche (pas de redirect login), console
    sans erreur.
  - `/` avec session active → redirigé vers `/dashboard` sans flash.
  - Soumission du formulaire « Demander un accès » → toast succès +
    message de remerciement ; la ligne apparaît dans `/admin` ▸ Demandes
    d'accès ; « Traiter » la fait passer en traitée.
  - Honeypot : un POST direct avec `company` non vide → 204, rien en base
    (vérif SQL).
  - **Responsive mobile** (viewport ~390 px) : hero lisible, CTA
    atteignables, grille de fonctionnalités en une colonne, pas de
    débordement horizontal.
  - Liens footer : Conditions, Confidentialité, `mailto:` OK ; lien
    « Yokkute Labs » ouvre yokkutelabs.com.
  - GIF de la soumission du formulaire (`access_request_flow.gif`).
- Docker : `docker compose up -d --build backend` après le travail backend
  (pas de volume mount) ; `docker logs search-backend-1` + `/docs`.

## Séquencement / commits (branche `feature/site-vitrine`)

Branche déjà créée depuis `feature/beta-launch`.
`feature/talya-inspired-rebuild` déjà supprimée.

1. **brand token + retrait « v3 »** — `lib/brand.ts`, `components/common/
   Logo.tsx`, `Sidebar.tsx`, `login/page.tsx`, `layout.tsx`.
2. **backend `AccessRequest`** — modèle, migration, schémas, entrée
   `_LIMITS`, `send_access_request_notification`, routeur public,
   enregistrement `main.py`, tests.
3. **admin — demandes d'accès** — endpoints `admin.py`, schémas,
   `lib/api.ts` `admin.getAccessRequests` / `markAccessRequestHandled`,
   `components/admin/AccessRequestsTab.tsx`, onglet dans `admin/page.tsx`.
4. **landing frontend** — `components/marketing/*`, `app/page.tsx` (SSR +
   metadata + OG), `public/og.png`, `requestAccess` dans `lib/api.ts`.
5. **proxy + intégration** — règle `/` connecté→`/dashboard` dans
   `proxy.ts` + `matcher` ; ligne « landing publique vérifiée » dans
   `docs/CHECKLIST-LANCEMENT.md` ; RUNBOOK §7 (purge `access_requests`).

Le merge de `feature/site-vitrine` (et de `feature/beta-launch`) dans
`main` reste la décision de l'utilisateur, au moment du déploiement prod.

## Décisions ouvertes (implémentation)

- Bouton « Générer un code » depuis une demande d'accès : **pré-remplir
  l'email dans l'onglet Invitations existant** (pas de nouveau flux
  serveur). Retenu sauf objection en revue.
- Champ « note » du formulaire : optionnel (ne pas bloquer la conversion).
