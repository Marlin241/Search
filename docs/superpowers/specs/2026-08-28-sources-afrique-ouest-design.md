# Sources d'offres Afrique de l'Ouest/Centrale + remote premier plan — Design

## Contexte

Le projet a démarré comme un exercice personnel. Les retours de l'entourage de
l'utilisateur ont montré que le produit pourrait réellement aider des
chercheurs d'emploi, notamment au Sénégal où l'utilisateur cherche lui-même.
L'objectif devient : prendre le produit au sérieux, valider qu'il aide
vraiment, et — si ça marche — envisager une monétisation plus tard.

Une discussion stratégique a écarté le positionnement « clone global de
Talya/Hirly » (marché déjà occupé, incumbents avec de l'avance, techno bâtie
autour des ATS occidentaux Greenhouse/Lever/Workday quasi inexistants en
Afrique) au profit d'un positionnement **copilote de recherche d'emploi pour
l'Afrique francophone**, en commençant par le **Sénégal**, puis l'Afrique de
l'Ouest et Centrale.

**État actuel du pipeline d'offres** (`backend/app/job_search/`) : 5 sources,
toutes orientées Europe/France — Adzuna, France Travail, La Bonne Alternance
(services publics français), Greenhouse, Lever. Architecture propre : une
interface `SearchClient` (`Protocol`), chaque source est un module isolé
branché dans `aggregator.py`, cache mémoire 15 min (`search_cache.py`),
scoring de compatibilité par-dessus, plus un job quotidien `daily_search.py`
pour les alertes email. Aucune persistance des offres (seuls `NotifiedListing`
— URLs déjà emailées — et `SavedJob` — offre explicitement sauvegardée par
l'user — existent en base).

Ce chantier est **purement additif** : aucune des 5 sources actuelles n'est
retirée, aucune fonctionnalité de `frontend-v3` n'est modifiée (score de
compat, génération CV/lettre, prépa entretien, Kanban, chemin « coller une URL
d'offre » qui existe déjà via `offerMode: "text" | "url"` dans
`diagnostic/page.tsx`).

## Objectif

Rendre `frontend-v3` + backend réellement utilisables par un chercheur
d'emploi au Sénégal :

1. Ajouter des sources d'offres africaines (API/RSS fiables + crawl de job
   boards locaux).
2. Traiter le remote comme une catégorie de premier plan.
3. Ajouter une autocomplétion de localisation couvrant l'Afrique de
   l'Ouest/Centrale + la France.

Puis valider : dogfooding par l'utilisateur, puis test avec 5-10 chercheurs
d'emploi à Dakar.

### Hors scope pour cette itération (explicitement exclu)

- **Paiement / mobile money** (Wave, Orange Money, MTN MoMo), paliers de prix,
  liste d'attente, landing marketing — dépend des conclusions de la
  validation.
- **Côté entreprise** (publication d'offres, matching, shortlist) et **côté
  école** — multiplie le travail et le cold-start ; reste candidat-only.
- **Expansion multi-pays active** (marketing/recrutement d'utilisateurs hors
  Sénégal) — les sources couvriront plusieurs pays techniquement, mais la
  validation se fait à Dakar d'abord.
- **App mobile.**
- **Scraping automatique de LinkedIn** — interdit par les CGU, bloqué
  agressivement, techniquement fragile ; l'affaire *hiQ v. LinkedIn* s'est
  retournée en faveur de LinkedIn. Le chemin « coller une URL d'offre »
  existant (action ponctuelle déclenchée par l'user sur une seule offre)
  couvre déjà le besoin et n'est pas concerné.
- **Détection du périmètre géographique d'un remote** (`remote_scope:
  worldwide | region_locked | unknown`) — peu fiable depuis le texte ;
  repoussé, à décider selon les retours.
- **Purge/expiration des lignes `crawled_listing`** — la désactivation
  (`is_active = False`) suffit pour la v1 ; purge triviale à ajouter plus
  tard, ne bloque aucun choix d'architecture ici.
- **Orchestrateur externe** (Airflow, Celery beat…) — l'`APScheduler`
  `BackgroundScheduler` déjà présent dans le lifespan FastAPI (`main.py`)
  suffit pour un job de crawl périodique de plus.
- **Slider de salaire multi-devise** — le `SalarySlider` de l'onboarding est
  aujourd'hui codé en dur `18000–100000` (logique EUR). Hors scope ici,
  mentionné pour mémoire ; à traiter dans un chantier « i18n/devises »
  séparé.

## Architecture : deux familles de sources

### Famille 1 — Sources « live » (pas de stockage)

Sources avec une API ou un flux interrogeable. Interrogées au moment de la
recherche avec les critères de l'utilisateur, exactement comme les 3 sources
« primaires » actuelles. Le cache mémoire 15 min (`search_cache.py`) absorbe
les revisites. **Aucun changement au modèle live.**

Sources ajoutées dans cette famille :

| Source | Accès | Couverture | Notes |
|---|---|---|---|
| **ReliefWeb** | API REST publique (`api.reliefweb.int/v1/jobs`) | Humanitaire / ONG, forte présence Afrique de l'Ouest | Paramètres de query (texte, pays) côté serveur ; pas de clé requise, `appname` recommandé |
| **Jobicy** | API REST publique (`jobicy.com/api/v2/remote-jobs`) | Remote uniquement, mondial | Filtres `count`, `geo`, `industry`, `tag` ; toutes les offres sont remote → `is_remote = True` d'office |
| **NGO Jobs in Africa** | Flux RSS par pays (`ngojobsinafrica.com`) | ONG, Afrique, flux par pays | Flux complet par pays → fetch + filtrage mots-clés en mémoire ; mis en cache |
| **We Work Remotely** / **RemoteOK** | Flux RSS publics | Remote uniquement, mondial (tech surtout) | `is_remote = True` d'office ; utile pour le mode remote d'un candidat sénégalais |

Chaque source = un nouveau module dans `job_search/` implémentant le
`Protocol` `SearchClient` (méthode `search(criteria) -> list[JobListing]`,
lève `JobSearchSourceError` en cas d'indisponibilité). Enregistrées dans
`get_job_search_clients()` (`job_search/dependencies.py`).

**Décision — flux RSS complets** : NGO Jobs / WWR / RemoteOK renvoient un flux
entier (pas de recherche serveur). On le récupère, on le met en cache
mémoire (même TTL que `search_cache`, ou un cache dédié court), et on filtre
les critères en mémoire (`keywords` sur titre+snippet, `location`,
`contract_type`). Volume attendu par flux : dizaines à quelques centaines
d'entrées — filtrage mémoire acceptable.

### Famille 2 — Sources « crawlées » (stockées en base)

Job boards locaux **sans API de recherche**. Impossible de les interroger en
direct par requête utilisateur : pas d'endpoint de recherche, scraping lent
(pagination), fragile, vite rate-limité.

| Source | URL | Couverture |
|---|---|---|
| **Emploi Dakar** | emploidakar.com | Sénégal, tous secteurs/niveaux — le plus consulté |
| **Senjob** | senjob.com | Sénégal, plateforme historique |
| **Réseau AfricWork** | emploisenegal.com + sites frères (emploi.ci, emploi.cm, emploi.ga, emploi.bj, emploi.tg…) | Multi-pays Afrique de l'Ouest/Centrale, **même plateforme** → un seul crawler paramétré par domaine couvre plusieurs pays |

Modèle : **crawl périodique → upsert dans `crawled_listing` → requête de la
table à la recherche**, mergée avec les résultats live.

## Composants

### 1. Modèle `CrawledListing` (nouveau)

Table `crawled_listing`. Une ligne par offre découverte sur une source
crawlée.

| Champ | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `url` | str, **unique**, indexé | clé naturelle de dédup |
| `source` | str, indexé | `emploi_dakar`, `senjob`, `africwork:sn`, `africwork:ci`… |
| `title` | str | |
| `company` | str, nullable | |
| `location` | str, nullable | |
| `snippet` | text | extrait / description courte |
| `salary` | str, nullable | brut, tel qu'affiché |
| `contract_type` | str, nullable | normalisé si détectable (CDI/CDD/Stage/…), sinon `NULL` |
| `is_remote` | bool, default `False` | posé par le crawler (heuristique texte sur titre+snippet) |
| `posted_at` | datetime, nullable | date de publication si le site l'expose |
| `first_seen_at` | datetime, not null | premier crawl où l'offre apparaît |
| `last_seen_at` | datetime, not null, indexé | dernier crawl où l'offre a été vue |
| `is_active` | bool, default `True`, indexé | passe à `False` après absence répétée |
| `missed_crawls` | int, default `0` | compteur d'absences consécutives ; remis à 0 dès que revue |

Migration Alembic. Postgres (prod) / SQLite (tests) comme le reste.

**Recherche full-text v1** : `ILIKE` sur `title` et `snippet` pour les
mots-clés. Pas de `tsvector` pour la v1 (volume faible, quelques milliers de
lignes actives). Note d'évolution : passer à un index `tsvector` GIN si le
volume ou la latence le justifient.

### 2. Crawlers (`job_search/crawlers/`)

Un module par site : `emploi_dakar.py`, `senjob.py`, `africwork.py`.

Chaque crawler expose :

```python
def crawl(config: CrawlerConfig, http_client: httpx.Client) -> list[CrawledListingData]: ...
```

- Récupère les pages de listing paginées, **nombre de pages plafonné**
  (`MAX_PAGES_PER_CRAWL`, ex. 10) et **délai poli** entre requêtes
  (`CRAWL_REQUEST_DELAY_SECONDS`, ex. 1s).
- Fetch **réutilisant la protection SSRF** de `offer_ingestion/scraper.py`
  (`_validate_url`, cap taille de réponse, cap redirections) — extraire cette
  logique dans un helper partagé `job_search/crawlers/http.py` plutôt que la
  dupliquer.
- Parse les cartes d'offres (BeautifulSoup, comme `scraper.py`), renvoie des
  `CrawledListingData` normalisés (dataclass, pas encore l'objet ORM).
- **User-Agent identifiable** : `ATSDiagnosticBot/1.0 (+<URL de contact>)`.
- `africwork.py` est paramétré par domaine (`CrawlerConfig.base_url`,
  `CrawlerConfig.country_code`) — une entrée de config par pays du réseau.

**Légal / robots.txt** : `robots.txt` et CGU de chaque site vérifiés **avant
activation** de son crawler (liste d'activation en config —
`ENABLED_CRAWLERS`). Un site dont les CGU interdisent le crawl reste
désactivé ; ce n'est pas un blocage du chantier (les sources live + les sites
tolérants suffisent à la v1).

### 3. Orchestrateur de crawl (`job_search/crawl_runner.py`)

`run_crawl(db_session_factory)` :

1. Pour chaque crawler activé (`ENABLED_CRAWLERS`) :
   - `try/except` **isolant par site** (comme `daily_search._process_saved_search`)
     — un site cassé n'interrompt pas les autres.
   - Appelle `crawl(...)`, récupère les `CrawledListingData`.
   - **Upsert par `url`** :
     - URL absente → `INSERT`, `first_seen_at = last_seen_at = now`,
       `missed_crawls = 0`.
     - URL présente → `UPDATE` des champs de contenu, `last_seen_at = now`,
       `missed_crawls = 0`, `is_active = True`.
   - **Désactivation** : les lignes de cette source **non vues** lors de ce
     crawl → `missed_crawls += 1` ; si `missed_crawls >= DEACTIVATE_AFTER`
     (ex. 3) → `is_active = False`.
   - **Garde-fou sélecteur cassé** : si `crawl(...)` renvoie 0 offre alors que
     la source a > `SUSPICIOUS_EMPTY_THRESHOLD` lignes actives → log
     `warning`, **on saute l'étape de désactivation pour cette source** (on ne
     vide pas la base sur un parsing cassé).
   - Log structuré par source : pages récupérées, offres trouvées, insérées,
     mises à jour, désactivées, erreurs.
2. Planifié via l'`APScheduler` existant dans `main.py` :
   `scheduler.add_job(lambda: run_crawl(database.SessionLocal), trigger="interval", hours=CRAWL_INTERVAL_HOURS, id="crawl")`.
   `CRAWL_INTERVAL_HOURS` par défaut `3`, configurable en env.

Pas de `BackgroundTasks` ni de `lock_user_for_rate_limit` ici (job scheduler
avec sa propre session, hors cycle requête) → la classe de deadlock de la
Phase 4 ne s'applique pas.

### 4. `CrawledListingClient` (`job_search/crawled_listings.py`)

Implémente le `Protocol` `SearchClient` mais lit la base au lieu du réseau :

```python
class CrawledListingClient:
    def __init__(self, db_session_factory): ...
    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        # SELECT ... FROM crawled_listing
        #   WHERE is_active
        #     AND (title ILIKE %kw% OR snippet ILIKE %kw%)   -- par mot-clé
        #     AND (location ILIKE %loc% OR :loc IS NULL)
        #     AND (contract_type = :ct OR :ct IS NULL)
        #     AND (is_remote OR NOT :remote_only)
        #   ORDER BY COALESCE(posted_at, first_seen_at) DESC
        #   LIMIT :cap
        # → mappe chaque ligne en JobListing
```

- Enregistré dans `get_job_search_clients()` comme une source de plus.
- `search_jobs()` (`aggregator.py`) le traite **sans cas particulier** : ses
  résultats sont mergés, dédupliqués par URL, et scorés comme les autres.
- Encapsulé pour qu'un incident DB sur cette source lève `JobSearchSourceError`
  → atterrit dans `unavailable_sources`, n'échoue pas toute la recherche.

### 5. Champ `is_remote` sur `JobListing` (nouveau)

`job_search/schemas.py` — `JobListing` gagne `is_remote: bool = False`.

- Sources 100 % remote (Jobicy, WWR, RemoteOK) → `True` d'office.
- Autres sources live + crawlées → dérivé de l'heuristique texte existante
  (`REMOTE_INDICATORS` de `aggregator.py`, réutilisée dans un helper
  `is_remote_from_text(title, snippet, location)`).
- Exposé dans la réponse de `/job-search/search` → **badge « Remote »** sur les
  cartes d'offres de `frontend-v3` (composant carte d'offre dans
  `offres/page.tsx`).

### 6. Remote comme mode de recherche

`aggregator.py` / endpoint `/job-search/search` :

- Quand `criteria.remote` est vrai : la **localisation devient optionnelle**
  (pas d'erreur si absente) et le filtre géographique n'est **pas** appliqué
  aux offres `is_remote = True` (une offre remote pertinente ne doit pas être
  écartée parce que sa localisation nominale est « Paris » ou « Worldwide »).
- L'heuristique `_passes_filters` de `aggregator.py` est ajustée : si
  `criteria.remote`, on garde toute offre `is_remote = True` **ou** matchée par
  `REMOTE_INDICATORS` (au lieu du seul test texte actuel).
- Frontend : le libellé de la case onboarding « Ouvert(e) au télétravail »
  (`StepLocationAndContract.tsx`) et le toggle remote de la recherche
  d'offres restent tels quels visuellement ; seul le comportement backend
  change.

### 7. `LocationAutocomplete` (frontend-v3)

**Jeu de données embarqué**, pas d'API externe au runtime.

- Source : dataset ouvert de villes (*countries-states-cities* ou GeoNames
  `cities500`), **filtré au build** aux pays cibles + France : Sénégal, Côte
  d'Ivoire, Cameroun, Gabon, Bénin, Togo, Congo, Burkina Faso, Mali +
  grandes villes françaises. Entrées `{ name, region, country, countryCode }`.
  Quelques milliers de lignes.
- Livré comme fichier statique dans `frontend-v3/public/locations.json`
  (généré par un petit script `scripts/build-locations.mjs` commité avec le
  dataset source ou son URL).
- Composant `components/onboarding/LocationAutocomplete.tsx` (ou
  `components/common/`) : au focus, charge le JSON une fois (cache mémoire
  module) ; à la frappe, dropdown des 8-10 meilleures correspondances
  (préfixe prioritaire, puis sous-chaîne), **insensible aux accents**
  (réutiliser la normalisation existante — `frontend-v3/lib/utils.ts` /
  équivalent du `normalize_company_name` backend). Sélectionner une
  suggestion ajoute le tag.
- Remplace le `TagInput` brut à **deux endroits** :
  `StepLocationAndContract.tsx` (onboarding) et le champ localisation de la
  recherche d'offres (`offres/page.tsx`).
- **Dégradation gracieuse** : si le JSON ne charge pas, le champ retombe sur
  la saisie libre `TagInput` actuelle (pas d'échec bloquant).
- Élargir la liste de pays plus tard = étendre le filtre du script de build.

### 8. Configuration (`config.py` / env)

Nouvelles clés :

| Clé | Défaut | Rôle |
|---|---|---|
| `CRAWL_INTERVAL_HOURS` | `3` | période du job de crawl |
| `CRAWL_MAX_PAGES` | `10` | pages de listing max par site et par crawl |
| `CRAWL_REQUEST_DELAY_SECONDS` | `1` | délai entre requêtes d'un crawler |
| `CRAWL_DEACTIVATE_AFTER` | `3` | absences consécutives avant `is_active = False` |
| `ENABLED_CRAWLERS` | `emploi_dakar,senjob,africwork:sn` | liste blanche des crawlers actifs |
| `CRAWLER_CONTACT_URL` | — | URL de contact mise dans le User-Agent du bot |
| `RELIEFWEB_APPNAME` | — | `appname` pour l'API ReliefWeb |

## Flux de données

### Recherche utilisateur (`POST /job-search/search`)

```
critères user
  │
  ├─ cache mémoire 15 min (search_cache) ─── hit ──▶ résultats scorés
  │                                          miss
  ▼
search_jobs(criteria, clients)
  ├─ France Travail   (live, API)      ┐
  ├─ Adzuna           (live, API)      │
  ├─ La Bonne Altern. (live, API)      │
  ├─ ReliefWeb        (live, API)      │  chaque client → list[JobListing]
  ├─ Jobicy           (live, API)      │  JobSearchSourceError → unavailable_sources
  ├─ NGO Jobs / WWR   (live, RSS+cache)│
  └─ CrawledListing   (DB: crawled_listing WHERE is_active) ┘
  │
  │  (Greenhouse/Lever restent sur leur chemin actuel séparé : découverte
  │   d'entreprises par slug via background_discovery, inchangé)
  │
  ▼
merge + dédup par URL + filtres remote/exclude + is_remote
  │
  ▼
score_listing (compatibilité) par offre
  │
  ▼
mise en cache + réponse (avec is_remote par offre, unavailable_sources)
```

### Crawl périodique (job APScheduler, toutes les 3h)

```
run_crawl
  └─ pour chaque crawler activé (try/except isolant) :
       crawl() → list[CrawledListingData]
         │
         ▼
       upsert par url dans crawled_listing
         ├─ nouvelle       → INSERT (first_seen_at, missed_crawls=0)
         ├─ revue          → UPDATE contenu, last_seen_at, missed_crawls=0
         └─ absente ce run → missed_crawls++ ; si ≥ 3 → is_active=False
              (sauf si crawl() a renvoyé 0 sur une source non vide → warning, skip désactivation)
         │
         ▼
       log structuré par source
```

## Gestion d'erreurs

- **Crawlers** : `try/except` isolant par site dans `run_crawl`. Un site en
  panne (réseau, markup changé, 5xx) → log `exception`, les autres continuent.
- **Sélecteur cassé** : garde-fou « 0 offre sur source non vide » → pas de
  désactivation en masse.
- **Sources live nouvelles** : lèvent `JobSearchSourceError` comme les
  existantes → `unavailable_sources` → UI « source indisponible ». Réutilisé
  tel quel.
- **`CrawledListingClient`** : incident DB → `JobSearchSourceError`, la
  recherche renvoie les autres sources.
- **`LocationAutocomplete`** : échec de chargement du dataset → repli sur
  `TagInput` libre.
- **SSRF** : tout fetch de crawler passe par le helper validé (schéma
  http/https, résolution DNS filtrée des adresses privées/réservées, cap
  taille, cap redirections) extrait de `offer_ingestion/scraper.py`.

## Tests

Ciblés sur ce qui porte le risque, pas exhaustifs (cf. contrainte
d'économie de tokens du projet). SQLite pour l'unitaire, Postgres + navigateur
réel pour le flux à risque.

| Cible | Type | Notes |
|---|---|---|
| Parsers de crawlers | Unitaire + fixtures HTML | Un snapshot réel par site dans `tests/fixtures/crawlers/` ; test du mapping page → `CrawledListingData`. Fixture à régénérer quand le markup change. |
| Upsert `crawled_listing` | Unitaire (SQLite) | insert / re-vue / `missed_crawls` / désactivation après N / garde-fou 0-offre |
| `CrawledListingClient.search()` | Unitaire (SQLite) | filtrage mots-clés / lieu / contrat / remote sur lignes seedées |
| Nouvelles sources live | Unitaire | réponse API mockée → `list[JobListing]` ; erreur HTTP → `JobSearchSourceError` |
| Merge agrégateur | Unitaire | crawlé + live fusionnent, dédup par URL, `is_remote` correct, scoring uniforme |
| Mode remote | Unitaire | `criteria.remote` → localisation optionnelle, offres `is_remote` non filtrées géographiquement |
| `LocationAutocomplete` | Composant | frappe filtre, insensible aux accents, sélection ajoute un tag, repli si dataset absent |
| Flux complet | **Navigateur réel + Postgres/Docker** | vrai `run_crawl` → recherche dans le navigateur → offres crawlées visibles, scorées, badge Remote, ouverture workspace OK ; `docker logs` propres, zéro erreur console. Rappel : `docker compose up -d --build backend` après toute modif backend. |

## Découpage en phases (chacune = un commit scopé sur `feature/talya-inspired-rebuild`)

1. **Sources live API/RSS** : helper HTTP partagé, `ReliefWeb`, `Jobicy`,
   `NGO Jobs`/`WWR`/`RemoteOK` (flux + cache), enregistrement dans
   `get_job_search_clients()`, tests unitaires.
2. **Infra crawl** : modèle `CrawledListing` + migration,
   `job_search/crawlers/http.py` (SSRF partagé), `crawl_runner.run_crawl`,
   `CrawledListingClient`, job APScheduler, config. Tests upsert + client.
3. **Crawlers concrets** : `emploi_dakar.py`, `senjob.py`, `africwork.py` +
   fixtures HTML + tests parsers. Vérif d'un vrai crawl contre Postgres.
4. **Remote premier plan** : `is_remote` sur `JobListing`, helper
   `is_remote_from_text`, ajustement `_passes_filters` / mode remote,
   badge Remote frontend. Tests.
5. **`LocationAutocomplete`** : script de build du dataset,
   `public/locations.json`, composant, intégration onboarding + recherche
   d'offres. Tests composant.
6. **Vérif navigateur réelle** de bout en bout + corrections.
7. **Validation** (hors code) :
   - 7a — dogfooding par l'utilisateur ~3 semaines, journal des observations.
   - 7b — test avec 5-10 chercheurs d'emploi à Dakar (réseau + groupes
     Facebook emploi), observation guidée : onboarding → première recherche →
     une candidature complète. Notes : blocages, pertinence ressentie,
     rétention, volonté de payer et moyen (mobile money ?).
   - Sortie : court doc de conclusions décidant la suite (approche « business
     scaffolding », approche « moat agrégation multi-pays », plus de sources,
     test de prix…).

## Décisions et alternatives écartées

- **Crawl + stockage plutôt que scraping à la volée** pour les sites locaux :
  pas d'API de recherche, scraping en chemin de requête = lent, fragile,
  rate-limité, mauvaise UX. Le crawl périodique découple la fragilité du
  chemin utilisateur.
- **`ILIKE` plutôt que `tsvector`** pour la v1 : volume faible, simplicité ;
  évolution documentée si besoin.
- **Dataset de villes embarqué plutôt que GeoNames/Nominatim en direct** :
  pas de clé, pas de rate limit, pas de latence réseau sur un champ de
  formulaire, fonctionne hors-ligne en dev. Coût : curation au build,
  acceptable pour ~10 pays.
- **APScheduler existant plutôt qu'un worker/orchestrateur dédié** : un job
  périodique de plus ne justifie pas l'infra.
- **Pas de scraping LinkedIn** : risque juridique (CGU, jurisprudence hiQ) et
  fragilité technique ; le chemin paste-URL existant couvre le besoin
  ponctuel.
- **Additif, rien retiré** : les sources françaises restent — un utilisateur
  au Sénégal regarde aussi des offres en France et en remote ; les retirer
  n'apporterait rien et casserait l'usage actuel.
