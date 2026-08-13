# Recherche proactive et notifications par email — Design

## Contexte

Aujourd'hui, la recherche d'offres (`POST /job-search/search`) est entièrement
à la demande : l'utilisateur soumet des critères, obtient une réponse, et rien
n'est conservé. Pour retrouver de nouvelles offres correspondant à ses
critères, il doit relancer la recherche manuellement.

Ce chantier fait suite au chantier CI/fiabilité
(`docs/superpowers/specs/2026-08-13-ci-fiabilite-design.md`), qui sécurisait
l'outillage avant d'attaquer de nouvelles fonctionnalités.

**Contexte produit** : le projet vise à terme un usage commercial (si les
tests avec l'utilisateur actuel sont concluants), pas uniquement un usage
personnel solo. Deux décisions de ce design (fuseau horaire par utilisateur,
lien de désabonnement) en découlent directement — voir « Hors scope » pour la
frontière exacte retenue.

## Objectif

Permettre à un utilisateur de sauvegarder une recherche et de recevoir un
email quotidien listant les nouvelles offres correspondantes, sans avoir à
relancer une recherche manuelle.

**Hors scope pour cette itération** (explicitement exclu) :
- Notification dans l'application (liste/badge) — email uniquement.
- Plusieurs recherches sauvegardées par utilisateur — une seule, activable/désactivable.
- Nettoyage/expiration des offres déjà notifiées (`NotifiedListing`) — la
  table grossit sans purge ; trivial à ajouter plus tard si le volume le
  justifie, ne bloque aucun choix d'architecture pris ici.
- Retry automatique en cas d'échec d'envoi d'email — une offre non marquée
  comme notifiée réapparaît naturellement dans l'email du lendemain, ce qui
  couvre le cas sans mécanisme dédié.
- Header `List-Unsubscribe` (RFC 8058, bouton de désabonnement natif
  Gmail/Yahoo sans ouverture de page) — optimisation de délivrabilité qui ne
  devient critique qu'à un volume d'envoi significatif. Le lien de
  désabonnement cliquable dans le corps de l'email (voir composant 5) reste
  inclus : c'est le besoin fonctionnel/légal de base, distinct de cette
  optimisation.
- Choix de l'heure d'envoi par l'utilisateur — fixée à 8h, heure locale du
  fuseau choisi, pour tout le monde. Seul le fuseau varie par utilisateur,
  pas l'heure elle-même.
- Airflow ou tout autre orchestrateur externe — un seul job quotidien ne
  justifie pas l'infrastructure additionnelle (scheduler, webserver, base
  dédiée) qu'Airflow impose ; voir composant 3.

## Composants

### 1. Modèle `SavedSearch` (nouveau)

Un par utilisateur (relation un-à-un, même pattern que `CandidateProfile`).

| Champ | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `user_id` | int, FK → `users.id`, unique, `ondelete=CASCADE` | un-à-un avec `User` |
| `keywords` | str | même sémantique que `SearchCriteria.keywords` |
| `location` | str, nullable | |
| `contract_type` | str, nullable | |
| `remote` | bool, nullable | |
| `exclude_keywords` | JSON (`list[str]`) | défaut `[]` |
| `timezone` | str | nom IANA (ex: `"Europe/Paris"`), défaut `"Europe/Paris"` |
| `enabled` | bool | défaut `True` à la création (l'utilisateur vient de sauvegarder = intention active) |
| `created_at` | datetime | |
| `updated_at` | datetime | |

### 2. Modèle `NotifiedListing` (nouveau)

| Champ | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `user_id` | int, FK → `users.id`, `ondelete=CASCADE` | |
| `offer_url` | str | |
| `notified_at` | datetime | |

Contrainte unique `(user_id, offer_url)` — même pattern que
`Application.offer_url` (contrainte unique `user_id` + `offer_url`). Sert
uniquement à ne jamais renvoyer deux fois la même offre au même utilisateur.

### 3. Endpoints (`app/routers/job_search.py`, modifié)

- `GET /job-search/saved-search` : renvoie la recherche sauvegardée de
  l'utilisateur courant, ou `404` si aucune n'existe encore.
- `PUT /job-search/saved-search` : upsert (crée si absent, sinon met à jour)
  — body : `keywords`, `location`, `contract_type`, `remote`,
  `exclude_keywords`, `timezone`, `enabled`. Valide `timezone` contre
  `zoneinfo.available_timezones()` (stdlib Python) ; `422` si invalide.

### 4. Job planifié (`app/job_search/daily_search.py`, nouveau)

- **Nouvelle dépendance** : `apscheduler` ajouté à `backend/requirements.txt`
  (dépendance d'exécution, pas seulement de développement — le scheduler
  tourne en production).
- **Scheduler** : `APScheduler` (`BackgroundScheduler`, cohérent avec le
  reste du code backend qui est synchrone/SQLAlchemy classique — pas
  `AsyncIOScheduler`), démarré dans le `lifespan` de `app/main.py` (start au
  démarrage de l'app, `shutdown()` à l'arrêt). Aucune nouvelle brique
  d'infrastructure (pas de conteneur supplémentaire, pas de Redis/Celery/
  Airflow) — cohérent avec les choix déjà faits pour
  `job_search/background_discovery.py` (état en mémoire, pas de file de
  tâches partagée).
- **Fréquence de déclenchement** : toutes les heures, à l'heure pile (cron
  APScheduler `hour="*"`, `minute=0`). `max_instances=1` (défaut
  APScheduler) empêche deux exécutions simultanées si un run dépasse une
  heure.
- **Sélection des utilisateurs à traiter à chaque exécution** : pour chaque
  `SavedSearch` avec `enabled=True`, calcule l'heure locale actuelle via
  `datetime.now(ZoneInfo(saved_search.timezone))` et ne traite que ceux dont
  `.hour == 8`. Ce design (scan horaire + filtre par fuseau, plutôt qu'un
  déclenchement dynamique par utilisateur) reste stateless et survit
  trivialement à un redémarrage du backend, contrairement à des jobs
  planifiés dynamiquement par utilisateur qu'il faudrait re-enregistrer.
  **Limite assumée** : autour d'une transition d'heure d'été/hiver, un
  utilisateur peut exceptionnellement recevoir l'email en double (heure
  répétée) ou pas du tout ce jour-là (heure sautée) — non traité
  spécifiquement, impact mineur pour un email quotidien non critique.
- **Recherche** : pour chaque utilisateur sélectionné, reconstruit un
  `SearchCriteria` depuis son `SavedSearch` et appelle la même logique que
  la recherche manuelle (`search_jobs` de `aggregator.py` pour
  France Travail/Adzuna/La Bonne Alternance, `get_cached_mapping` +
  clients Greenhouse/Lever pour les entreprises déjà connues). **Différence
  avec le flux manuel** : les entreprises pas encore résolues
  (Greenhouse/Lever) sont résolues **de façon synchrone** dans ce job,
  plutôt que via le mécanisme de polling différé de
  `background_discovery.py` — ce mécanisme existe uniquement pour ne pas
  bloquer une requête HTTP utilisateur ; un job en arrière-plan n'a pas
  cette contrainte, donc autant obtenir un résultat complet en un seul
  passage.
- **Déduplication** : les offres dont `offer_url` est déjà dans
  `NotifiedListing` pour cet utilisateur sont retirées de la liste avant
  l'envoi.
- **Pas de rate-limit** : le job n'est pas déclenché par l'utilisateur (donc
  aucun des mécanismes de `app/rate_limit/limiter.py` ne s'applique) — une
  exécution par utilisateur par jour est intrinsèquement bornée.
- **Isolation des erreurs** : chaque utilisateur est traité dans son propre
  `try/except` — un échec (recherche ou envoi d'email) pour un utilisateur
  est logué (`logger.error`, même convention que le reste du projet) et
  n'interrompt pas le traitement des autres utilisateurs de ce passage.

### 5. Envoi d'email (`app/notifications/resend_client.py`, nouveau)

- Appel HTTP direct à l'API REST Resend via `httpx` (déjà une dépendance du
  projet) — pas de SDK ajouté, cohérent avec le style des autres
  intégrations externes (`france_travail.py`, `adzuna.py`,
  `la_bonne_alternance.py`, `greenhouse.py`, `lever.py`, qui appellent
  toutes leur API en HTTP direct plutôt que via un SDK vendor).
- Nouvelles variables de config (`app/config.py`) : `resend_api_key: str`,
  `resend_from_email: str`.
- **Un seul email par jour par utilisateur** (jamais un email par offre), et
  uniquement s'il y a au moins une nouvelle offre après déduplication —
  aucun envoi si la liste est vide.
- **Contenu** : sujet `"N nouvelle(s) offre(s) correspondant à votre
  recherche"`, corps listant pour chaque offre son titre, l'entreprise, le
  lieu (si connu) et le lien ; un lien de désabonnement en pied d'email
  (composant 6).
- **Après envoi réussi** : chaque offre envoyée est insérée dans
  `NotifiedListing`. Si l'envoi échoue, aucune insertion — ces offres
  réapparaîtront donc dans le calcul du lendemain (rattrapage naturel, voir
  « Hors scope »).

### 6. Désabonnement (`app/routers/job_search.py`, modifié)

- `create_unsubscribe_token(user_id: int) -> str` (nouveau, dans
  `app/auth/security.py` ou module dédié) : JWT signé avec le même
  `jwt_secret` que l'authentification, mais avec une claim distincte
  (`{"sub": str(user_id), "purpose": "unsubscribe"}`) et une expiration
  longue (365 jours) plutôt que celle, courte, des tokens de connexion —
  un email peut être lu des semaines après réception. Un token frais est
  généré à chaque envoi d'email (pas de token réutilisé/stocké), donc
  l'expiration n'est jamais perceptible en pratique tant que les emails
  continuent d'arriver.
- `verify_unsubscribe_token(token: str) -> int` : décode et vérifie la
  claim `purpose == "unsubscribe"` (rejette un token de connexion normal
  utilisé ici par erreur/malveillance, et vice-versa).
- `GET /job-search/saved-search/unsubscribe?token=...` : endpoint **public**
  (aucune authentification requise — appelé depuis un client email, pas
  depuis l'app). Décode le token, met `SavedSearch.enabled = False` pour
  l'utilisateur correspondant, renvoie une page HTML minimale de
  confirmation (`HTMLResponse`, pas de JSON — ce lien est cliqué depuis un
  navigateur). Idempotent : un utilisateur déjà désabonné qui reclique voit
  la même confirmation, sans erreur.

### 7. Frontend

- `app/candidatures/page.tsx` (ou nouveau composant dédié) : nouvelle
  section « Recherche automatique » sous le formulaire de recherche
  manuelle existant — un bouton « Sauvegarder cette recherche » (envoie les
  critères actuels du formulaire + le fuseau horaire sélectionné vers
  `PUT /job-search/saved-search` avec `enabled: true`), un sélecteur de
  fuseau horaire (liste fixe de fuseaux courants, pas une recherche libre
  parmi les ~600 noms IANA), et un toggle activer/désactiver visible une
  fois une recherche sauvegardée (`PUT` avec `enabled` modifié, reste des
  champs inchangés).
- `lib/api.ts` : nouvelles fonctions `getSavedSearch(token)` et
  `saveSavedSearch(token, payload)`.
- `lib/types.ts` : nouveau type `SavedSearch`.

## Gestion des erreurs et cas limites

- **`GET /job-search/saved-search/unsubscribe` avec un token invalide/
  expiré/malformé** : renvoie une page HTML d'erreur simple (pas de fuite
  d'information sur pourquoi — token invalide vs utilisateur inexistant
  traités identiquement).
- **Utilisateur avec `SavedSearch.enabled=True` mais dont le compte a été
  supprimé entretemps** : couvert nativement par
  `ondelete=CASCADE` sur `SavedSearch.user_id` et `NotifiedListing.user_id`
  — la ligne disparaît avec l'utilisateur, rien à gérer explicitement dans
  le job.
- **Backend redémarré/déployé pile pendant l'heure de traitement d'un
  utilisateur** : ce passage horaire est perdu pour les utilisateurs dont
  c'est l'heure locale de 8h ce jour-là ; ils recevront leur email normalement
  le lendemain. Pas de mécanisme de rattrapage dédié (cohérent avec
  « pas de retry automatique » ci-dessus).
- **Fuseau horaire invalide soumis via `PUT`** : rejeté à la validation
  (`422`), avant tout enregistrement.

## Tests

- **`daily_search.py`** : sélection des utilisateurs à traiter (fixe un
  instant "now", vérifie le sous-ensemble de `SavedSearch` sélectionné selon
  leur fuseau) ; déduplication (offres déjà dans `NotifiedListing` exclues
  du résultat) ; isolation des erreurs (un utilisateur en échec n'empêche
  pas le traitement des suivants, testé avec mock).
- **`resend_client.py`** : requête HTTP correcte (URL, headers, payload)
  via `respx` (déjà une dépendance de test du projet) ; gestion d'un échec
  HTTP (l'appelant reçoit une erreur, ne marque rien comme notifié).
- **Endpoint `GET`/`PUT /job-search/saved-search`** : création, mise à
  jour, validation du fuseau horaire invalide.
- **Endpoint `GET /job-search/saved-search/unsubscribe`** : token valide
  désactive la recherche ; token invalide rejeté proprement ; deuxième
  clic sur un lien déjà utilisé reste sans erreur (idempotence).
- **`create_unsubscribe_token`/`verify_unsubscribe_token`** : aller-retour
  correct ; un token de connexion normal (claim `purpose` absente) est
  rejeté par `verify_unsubscribe_token`.

## Prochaines étapes (hors scope de cette spec)

- Notification dans l'application, en complément de l'email.
- Plusieurs recherches sauvegardées par utilisateur.
- Header `List-Unsubscribe` (RFC 8058) une fois un volume d'envoi réel
  atteint.
- Nettoyage/expiration de `NotifiedListing` si le volume le justifie.
- Chantier suivant déjà identifié : suivi de candidatures enrichi (relances,
  statistiques, pipeline visuel).
