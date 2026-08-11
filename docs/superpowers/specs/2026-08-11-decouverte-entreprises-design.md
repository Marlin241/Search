# Découverte automatique des entreprises Greenhouse/Lever — Design

## Contexte

Ce document couvre une extension du sous-projet 2 (automatisation de
candidature, `docs/superpowers/specs/2026-08-06-automatisation-candidature-design.md`),
déjà en production. Ce sous-projet excluait explicitement de son périmètre V1
la « recherche de mots-clés à travers toutes les entreprises utilisant
Greenhouse/Lever dans le monde (uniquement parmi les entreprises que
l'utilisateur choisit de suivre) ». En usage réel, cette limite s'est révélée
gênante : l'utilisateur doit connaître et taper à la main le nom de chaque
entreprise à suivre avant de lancer une recherche, ce qui rend la
fonctionnalité Greenhouse/Lever quasiment inutilisée en pratique.

## Objectif

Remplacer la saisie manuelle du champ « Entreprises à suivre sur
Greenhouse/Lever » par une détection automatique : quand une recherche
France Travail/Adzuna remonte des offres, le backend identifie les
entreprises citées et tente de trouver lui-même leur board Greenhouse ou
Lever, sans intervention de l'utilisateur.

**Hors scope pour cette itération** (explicitement exclu) :
- Découverte d'offres sur des sites carrière n'utilisant ni Greenhouse ni
  Lever (Workday, sites custom d'entreprise...) — ces offres restent
  visibles uniquement via le lien France Travail/Adzuna d'origine, sans
  tentative de scraper le site de l'entreprise. Décision assumée : chaque
  site a une structure différente, ce serait trop fragile à généraliser, et
  l'offre est déjà accessible via le lien fourni par la source d'origine.
- Toute forme de recherche web tierce (Google/Bing) pour trouver le vrai
  slug d'une entreprise — introduirait une dépendance externe payante/à
  quota et irait à l'encontre de la posture déjà adoptée par le projet
  (« pas de scraping de recherche »).
- Déduplication entre une offre France Travail/Adzuna et la même offre
  retrouvée sur le board Greenhouse/Lever de l'entreprise (URLs
  différentes, pas de correspondance automatique possible) — cohérent avec
  l'existant, où le dédoublonnage n'intervient qu'à la création d'une
  `Application` (contrainte unique `offer_url`), jamais à l'affichage des
  résultats de recherche.
- Ré-vérification périodique des entreprises déjà testées (pas
  d'expiration de cache) — un changement de plateforme ATS par une
  entreprise déjà répertoriée est un cas jugé trop rare pour justifier un
  mécanisme de rafraîchissement.

## Algorithme de détection

Pour chaque entreprise nouvellement rencontrée dans des résultats France
Travail/Adzuna :
1. **Normalisation** du nom : minuscules, accents et apostrophes retirés
   (ex: « L'Oréal » → `loreal`).
2. **Génération de variantes de slug** à partir du nom normalisé : une
   variante sans séparateur (`laposte`) et une variante avec tirets entre
   les mots (`la-poste`).
3. **Vérification directe** : chaque variante est testée contre les APIs
   Greenhouse (`boards-api.greenhouse.io/v1/boards/{slug}/jobs`) et Lever
   (`api.lever.co/v0/postings/{slug}`) déjà utilisées par
   `app/job_search/greenhouse.py` et `lever.py` — une réponse HTTP valide
   avec au moins un contenu exploitable retient la variante comme slug de
   l'entreprise.
4. **Résultat mémorisé** : trouvé (source + slug) ou non trouvé de façon
   confirmée (réponse HTTP claire, ex: 404) — dans les deux cas,
   l'entreprise ne sera plus jamais re-testée. Une erreur réseau/timeout
   n'est pas une confirmation et ne compte pas comme un résultat : voir
   « Gestion des erreurs et cas limites ».

**Limite assumée** : une entreprise avec un slug atypique (ex:
`doctolib-fr` au lieu de `doctolib`) ne sera pas détectée. Aucune solution
générique n'existe sans recherche web tierce, écartée ci-dessus — ce
compromis (couverture partielle plutôt que dépendance externe) est
délibéré.

## Modèle de données

### `CompanyAtsMapping` (nouveau)

| Champ | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `company_name` | str, unique | nom normalisé (minuscules, sans accents), clé de cache |
| `source` | str, nullable | `greenhouse` / `lever` / `null` si aucune plateforme trouvée |
| `slug` | str, nullable | slug retenu, renseigné seulement si `source` non nul |
| `checked_at` | datetime | horodatage de la vérification, à titre d'audit — pas utilisé pour une quelconque expiration |

Table globale, partagée entre tous les utilisateurs (pas de `user_id`) :
une entreprise vérifiée une fois par n'importe quel utilisateur bénéficie
immédiatement à toutes les recherches suivantes, y compris celles d'autres
utilisateurs.

### `SearchCriteria` (modifié)

Le champ `followed_companies` est retiré — la liste d'entreprises à
interroger sur Greenhouse/Lever n'est plus fournie par l'utilisateur, elle
est dérivée automatiquement des résultats France Travail/Adzuna de la même
recherche.

## Composants

### 1. Extraction et résolution des entreprises (`app/job_search/aggregator.py`, modifié)

Après l'appel synchrone à France Travail et Adzuna, l'agrégateur extrait la
liste des noms d'entreprises uniques (normalisés) présents dans les
`JobListing` obtenus. Il les répartit en deux groupes :
- **Connues** (déjà présentes dans `CompanyAtsMapping`) : celles avec une
  `source` non nulle sont interrogées immédiatement via les clients
  `GreenhouseJobBoardClient`/`LeverJobBoardClient` existants (appelés avec
  le slug déjà connu), et leurs offres sont incluses dans la réponse
  synchrone. Celles avec `source` nulle sont ignorées silencieusement (déjà
  testées, non trouvées).
- **Inconnues** : transmises à la découverte en arrière-plan (section
  suivante). Un plafond (`MAX_COMPANIES_PER_DISCOVERY = 15`) limite le
  nombre d'entreprises inconnues traitées par recherche, pour borner le
  volume d'appels réseau déclenchés par une recherche à mots-clés très
  larges — les entreprises au-delà de ce plafond sont ignorées pour cette
  recherche ; elles resteront « inconnues » et seront retentées si une
  recherche future les cite à nouveau, sans garantie sur le délai.

### 2. Découverte en arrière-plan (`app/job_search/discovery.py`, nouveau)

- Déclenchée via `BackgroundTasks` de FastAPI, après renvoi de la réponse
  HTTP initiale de `POST /job-search/search`.
- Pour chaque entreprise inconnue transmise : exécute l'algorithme de
  détection (section précédente), écrit le résultat dans
  `CompanyAtsMapping` (trouvé ou non), et si trouvé, récupère les offres
  correspondantes via le client Greenhouse/Lever existant.
- Les nouvelles offres trouvées sont accumulées dans un état en mémoire
  (dictionnaire process-local, `search_id` → liste d'offres + indicateur
  `done`), cohérent avec l'échelle actuelle du projet (un seul processus
  backend, pas de file de tâches ni de cache partagé de type Redis).
  Nettoyé après consultation par le frontend ou après un délai fixe (5
  minutes), pour éviter une fuite mémoire si le frontend ne consulte
  jamais le résultat.

### 3. Nouvelle route de polling (`app/routers/job_search.py`, modifié)

- `POST /job-search/search` : inchangée dans son usage, mais la réponse
  inclut désormais `search_id: str` et `discovery_pending: bool` (vrai s'il
  reste des entreprises inconnues à traiter). Les offres des entreprises
  déjà connues sont incluses directement dans `listings`, comme les offres
  France Travail/Adzuna.
- `GET /job-search/search/{search_id}/discovery` (nouvelle) : renvoie
  `{done: bool, new_listings: list[JobListing]}`. Accessible uniquement à
  l'utilisateur ayant initié la recherche (le `search_id` est associé au
  `user_id` au moment de sa création). `search_id` inconnu ou expiré →
  `done: true, new_listings: []` (comportement idempotent, pas d'erreur).

### 4. Frontend

- `components/SearchCriteriaForm.tsx` : suppression du champ « Entreprises
  à suivre sur Greenhouse/Lever » et du champ correspondant dans
  `SearchCriteriaFormValue`/`toSearchCriteria`.
- `app/candidatures/page.tsx` : après une recherche, si
  `discovery_pending` est vrai, démarre un polling (`setInterval`, ~3s) sur
  `GET /job-search/search/{search_id}/discovery` ; chaque réponse fusionne
  `new_listings` dans l'état `searchResult.listings` affiché, jusqu'à
  `done: true` qui arrête le polling. Un indicateur textuel léger («
  Recherche en cours sur les sites des entreprises... ») s'affiche pendant
  que le polling est actif.
- `lib/types.ts` : `JobSearchResult` gagne `search_id` et
  `discovery_pending` ; nouveau type de réponse pour l'endpoint de
  polling.
- `lib/api.ts` : nouvelle fonction `pollJobSearchDiscovery(token,
  searchId)`.

## Gestion des erreurs et cas limites

- **Échec réseau lors d'une vérification Greenhouse/Lever en arrière-plan**
  (timeout, 5xx) : traité comme « non trouvé » pour cette tentative, mais
  **non mémorisé** dans `CompanyAtsMapping` (contrairement à une réponse
  404/vide qui, elle, signifie explicitement que l'entreprise n'a pas de
  board à ce slug) — l'entreprise sera retentée lors d'une prochaine
  recherche la citant, pour ne pas figer un résultat « non trouvé » à cause
  d'une simple indisponibilité momentanée du service.
- **`search_id` jamais consulté par le frontend** (recherche abandonnée,
  page fermée) : nettoyage automatique après 5 minutes en mémoire, aucune
  fuite.
- **Redémarrage du backend pendant une découverte en cours** : l'état en
  mémoire est perdu, le polling suivant reçoit `done: true` avec
  `new_listings: []` (comportement idempotent défini ci-dessus) — aucune
  offre supplémentaire pour cette recherche précise, mais aucune erreur
  visible ; l'entreprise reste « inconnue » et sera retentée à la prochaine
  recherche.

## Tests

- **`discovery.py`** : génération des variantes de slug (cas simples,
  accents, apostrophes), résolution cache hit/non trouvé/nouveau via
  réponses HTTP mockées, respect du plafond `MAX_COMPANIES_PER_DISCOVERY`.
- **`aggregator.py`** : extraction correcte des noms d'entreprises uniques
  depuis un mélange de résultats France Travail/Adzuna ; répartition
  connues/inconnues.
- **Route `GET /job-search/search/{search_id}/discovery`** : cas en cours,
  terminé, `search_id` inconnu — tests d'intégration avec le
  `BackgroundTasks` de FastAPI.
- **Frontend** : test du polling (mock de l'API — plusieurs réponses
  successives avec `done: false` puis `done: true` — vérifie la fusion
  progressive dans la liste affichée) ; suppression des tests existants
  liés à l'ancien champ manuel `followedCompanies`.

## Prochaines étapes (hors scope de cette spec)

- Découverte élargie à d'autres ATS (SmartRecruiters, Workday...) si leur
  API publique le permet sans scraping.
- File de tâches partagée (Redis/Celery ou équivalent) si le volume
  d'utilisateurs simultanés rend l'état en mémoire process-local
  insuffisant.
- Recherche web tierce pour améliorer le taux de détection des slugs
  atypiques, si le taux de couverture actuel s'avère insuffisant en usage
  réel.
