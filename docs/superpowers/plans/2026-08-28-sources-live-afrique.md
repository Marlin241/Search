# Plan A — Sources live africaines (recherche d'emploi) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter quatre sources d'offres d'emploi orientées Afrique / remote (ReliefWeb, Jobicy, We Work Remotely, RemoteOK, NGO Jobs in Africa) au pipeline de recherche existant, sans rien retirer.

**Architecture:** Chaque source est un nouveau client isolé implémentant le `Protocol` `SearchClient` (`search(criteria) -> list[JobListing]`, lève `JobSearchSourceError` en cas de panne), branché dans l'agrégateur existant à côté des 5 sources actuelles. Deux sources sont des API JSON (ReliefWeb, Jobicy), trois sont des flux RSS parsés via `feedparser` par un unique client paramétré. Un petit cache TTL par URL de flux évite de re-télécharger les mêmes RSS à chaque recherche. L'agrégateur gagne une déduplication par URL car les sources remote se recouvrent.

**Tech Stack:** Python 3, FastAPI, httpx, `respx` (tests HTTP), `feedparser` (nouveau), pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-sources-afrique-ouest-design.md` (section « Famille 1 — Sources live », composants 5-6 partiellement — le champ `is_remote` first-class est explicitement laissé au Plan C).

## Global Constraints

- **Purement additif** : ne modifier la signature d'aucune source existante, ne retirer aucune source, ne changer aucun comportement de `frontend-v3`.
- **`requirements.txt` non épinglé** par convention du projet — ajouter `feedparser` sans version.
- **Commits scopés** : `git add <chemins explicites>`, jamais `git add -A`. Rester sur la branche `feature/talya-inspired-rebuild` (ne jamais commiter sur `main`).
- **Après toute modif backend testée en réel** : `docker compose up -d --build backend` depuis la racine du repo, puis `docker logs search-backend-1` et `curl http://localhost:8000/docs`.
- **Tests** : mock HTTP via `@respx.mock` + `httpx.Response`, comme `tests/job_search/test_adzuna.py`. Un client = un fichier de test dans `tests/job_search/`.
- **Nommage des sources** (`JobListing.source`) : `reliefweb`, `jobicy`, `weworkremotely`, `remoteok`, `ngojobs`.
- **`JobSearchSourceError`** (de `app.job_search.errors`) est la seule exception qu'un client a le droit de laisser remonter ; toute `httpx.HTTPError` / erreur de parsing est convertie en `JobSearchSourceError`.

---

## File Structure

**Créés :**
- `backend/app/job_search/feed_cache.py` — cache TTL mémoire, par URL, du corps brut d'un flux/réponse ; calqué sur `search_cache.py` (threading.Lock, dataclass d'entrée, purge des expirés).
- `backend/app/job_search/reliefweb.py` — `ReliefWebClient` (API JSON).
- `backend/app/job_search/jobicy.py` — `JobicyClient` (API JSON, remote-only).
- `backend/app/job_search/rss_feeds.py` — `RssFeedClient` paramétré (nom de source, liste d'URLs de flux, drapeau `remote_only`) ; sert We Work Remotely, RemoteOK, NGO Jobs.
- `backend/tests/job_search/test_feed_cache.py`
- `backend/tests/job_search/test_reliefweb.py`
- `backend/tests/job_search/test_jobicy.py`
- `backend/tests/job_search/test_rss_feeds.py`

**Modifiés :**
- `backend/requirements.txt` — `+ feedparser`.
- `backend/app/config.py` — nouvelles clés de settings.
- `backend/app/job_search/aggregator.py` — dédup par URL dans `search_jobs`.
- `backend/app/job_search/dependencies.py` — enregistrer les 4 nouveaux clients (`ngojobs` = un `RssFeedClient`, `weworkremotely`+`remoteok` idem).
- `backend/app/routers/job_search.py` — ajouter les nouveaux clients au dict `primary_clients` de `search()`.
- `backend/app/job_search/daily_search.py` — ajouter les nouveaux clients au dict `primary_clients` de `_process_saved_search`.
- `backend/tests/job_search/test_aggregator.py` — test de la dédup.

**Non modifiés (volontairement) :** `schemas.py` (le champ `is_remote` est au Plan C), `greenhouse.py`/`lever.py` (chemin de découverte séparé, hors sujet).

---

## Task 1 : Cache TTL de flux (`feed_cache.py`) + dépendance `feedparser`

**Files:**
- Create: `backend/app/job_search/feed_cache.py`
- Create: `backend/tests/job_search/test_feed_cache.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: `app.utils.time.utcnow` (déjà utilisé par `search_cache.py`).
- Produces :
  - `feed_cache.get_or_fetch(url: str, http_client: httpx.Client, ttl: datetime.timedelta) -> str`
    — renvoie le corps texte de la réponse `GET url`. Sur cache hit non expiré : renvoie la valeur mémorisée sans requête réseau. Sur miss/expiré : fait le `GET`, lève `JobSearchSourceError` si `httpx.HTTPError` ou statut ≥ 400, mémorise et renvoie le `.text`.
  - `feed_cache.clear() -> None` — vide le cache (usage test).

- [ ] **Step 1: Écrire le test qui échoue**

`backend/tests/job_search/test_feed_cache.py` :

```python
from datetime import timedelta

import httpx
import pytest
import respx

from app.job_search import feed_cache
from app.job_search.errors import JobSearchSourceError

FEED_URL = "https://example.com/feed.rss"


@pytest.fixture(autouse=True)
def _clear_cache():
    feed_cache.clear()
    yield
    feed_cache.clear()


@respx.mock
def test_fetches_and_returns_body_on_miss():
    route = respx.get(FEED_URL).mock(return_value=httpx.Response(200, text="<rss/>"))
    with httpx.Client() as client:
        body = feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))
    assert body == "<rss/>"
    assert route.call_count == 1


@respx.mock
def test_second_call_within_ttl_does_not_refetch():
    route = respx.get(FEED_URL).mock(return_value=httpx.Response(200, text="<rss/>"))
    with httpx.Client() as client:
        feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))
        feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))
    assert route.call_count == 1


@respx.mock
def test_raises_job_search_source_error_on_http_error():
    respx.get(FEED_URL).mock(return_value=httpx.Response(503))
    with httpx.Client() as client:
        with pytest.raises(JobSearchSourceError):
            feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))


@respx.mock
def test_raises_job_search_source_error_on_transport_error():
    respx.get(FEED_URL).mock(side_effect=httpx.ConnectError("boom"))
    with httpx.Client() as client:
        with pytest.raises(JobSearchSourceError):
            feed_cache.get_or_fetch(FEED_URL, client, timedelta(minutes=30))
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `cd backend && python -m pytest tests/job_search/test_feed_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.job_search.feed_cache'`

- [ ] **Step 3: Implémenter `feed_cache.py`**

`backend/app/job_search/feed_cache.py` :

```python
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

from app.job_search.errors import JobSearchSourceError
from app.utils.time import utcnow


@dataclass
class _Entry:
    body: str
    cached_at: datetime = field(default_factory=utcnow)


_lock = threading.Lock()
_cache: dict[str, _Entry] = {}


def clear() -> None:
    with _lock:
        _cache.clear()


def get_or_fetch(url: str, http_client: httpx.Client, ttl: timedelta) -> str:
    cutoff = utcnow() - ttl
    with _lock:
        entry = _cache.get(url)
        if entry is not None and entry.cached_at >= cutoff:
            return entry.body

    try:
        response = http_client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JobSearchSourceError(f"Flux {url} indisponible: {exc}") from exc

    body = response.text
    with _lock:
        _cache[url] = _Entry(body=body)
    return body
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `cd backend && python -m pytest tests/job_search/test_feed_cache.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Ajouter `feedparser` aux dépendances**

Ajouter la ligne `feedparser` à `backend/requirements.txt` (ordre alphabétique approximatif du fichier : après `fastapi`, avant `fpdf2` — ou simplement en fin de liste, le fichier n'est pas trié strictement). Puis :

Run: `cd backend && pip install feedparser && python -c "import feedparser; print(feedparser.__version__)"`
Expected: une version s'affiche sans erreur.

- [ ] **Step 6: Vérifier la suite complète job_search**

Run: `cd backend && python -m pytest tests/job_search/ -q`
Expected: PASS (aucune régression).

- [ ] **Step 7: Commit**

```bash
git add backend/app/job_search/feed_cache.py backend/tests/job_search/test_feed_cache.py backend/requirements.txt
git commit -m "feat(job-search): add TTL feed cache helper and feedparser dep

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 2 : `ReliefWebClient` (API JSON, ONG/humanitaire, Afrique de l'Ouest)

**Files:**
- Create: `backend/app/job_search/reliefweb.py`
- Create: `backend/tests/job_search/test_reliefweb.py`

**Interfaces:**
- Consumes: `SearchCriteria`, `JobListing` (`app.job_search.schemas`), `JobSearchSourceError` (`app.job_search.errors`), `parse_iso_datetime` (`app.job_search.timestamps`).
- Produces :
  - `class ReliefWebClient` avec `__init__(self, appname: str, countries: list[str], http_client: httpx.Client | None = None)` et `search(self, criteria: SearchCriteria) -> list[JobListing]`.
  - `source` des listings produits : `"reliefweb"`.

**Contexte API (vérifié 2026-08) :** `GET https://api.reliefweb.int/v1/jobs`
- Query params (répétables) : `appname=<appname>`, `profile=list`, `limit=20`,
  `query[value]=<keywords>`, `query[operator]=AND`,
  `fields[include][]=title` + `url` + `url_alias` + `source.name` + `country.name` + `city.name` + `date.created` + `body`,
  `filter[field]=country.name`, `filter[value][]=<pays>` (un par pays), `filter[operator]=OR`.
- Réponse : `{"data": [{"id": "...", "fields": {"title": "...", "url": "...", "url_alias": "...", "source": [{"name": "ACTED"}], "country": [{"name": "Senegal"}], "city": [{"name": "Dakar"}], "date": {"created": "2026-08-20T00:00:00+00:00"}, "body": "..."}}]}`
- `url_alias` est l'URL publique lisible ; `url` est l'URL API. Préférer `url_alias`, sinon `url`.

- [ ] **Step 1: Écrire le test qui échoue**

`backend/tests/job_search/test_reliefweb.py` :

```python
import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.reliefweb import ReliefWebClient
from app.job_search.schemas import SearchCriteria

API_URL = "https://api.reliefweb.int/v1/jobs"

_ONE_JOB = {
    "data": [
        {
            "id": "123",
            "fields": {
                "title": "Logisticien",
                "url": "https://api.reliefweb.int/v1/jobs/123",
                "url_alias": "https://reliefweb.int/job/123/logisticien",
                "source": [{"name": "ACTED"}],
                "country": [{"name": "Senegal"}],
                "city": [{"name": "Dakar"}],
                "date": {"created": "2026-08-20T00:00:00+00:00"},
                "body": "Nous recherchons un logisticien basé à Dakar.",
            },
        }
    ]
}


@respx.mock
def test_search_returns_normalized_listings():
    respx.get(API_URL).mock(return_value=httpx.Response(200, json=_ONE_JOB))
    client = ReliefWebClient(appname="ats-diagnostic", countries=["Senegal"])
    listings = client.search(SearchCriteria(keywords="logisticien"))
    assert len(listings) == 1
    lst = listings[0]
    assert lst.title == "Logisticien"
    assert lst.company == "ACTED"
    assert lst.location == "Dakar, Senegal"
    assert lst.url == "https://reliefweb.int/job/123/logisticien"
    assert lst.source == "reliefweb"
    assert lst.posted_at is not None


@respx.mock
def test_search_sends_keywords_and_country_filter():
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json={"data": []}))
    client = ReliefWebClient(
        appname="ats-diagnostic", countries=["Senegal", "Cameroon"]
    )
    client.search(SearchCriteria(keywords="wash"))
    request = route.calls.last.request
    assert "appname=ats-diagnostic" in str(request.url)
    assert "query%5Bvalue%5D=wash" in str(request.url)
    assert str(request.url).count("filter%5Bvalue%5D%5B%5D=") == 2


@respx.mock
def test_search_falls_back_to_url_when_no_alias():
    payload = {
        "data": [
            {
                "id": "9",
                "fields": {
                    "title": "T",
                    "url": "https://api.reliefweb.int/v1/jobs/9",
                    "source": [{"name": "X"}],
                    "country": [{"name": "Mali"}],
                    "date": {"created": "2026-08-01T00:00:00+00:00"},
                    "body": "b",
                },
            }
        ]
    }
    respx.get(API_URL).mock(return_value=httpx.Response(200, json=payload))
    client = ReliefWebClient(appname="a", countries=["Mali"])
    listings = client.search(SearchCriteria(keywords="t"))
    assert listings[0].url == "https://api.reliefweb.int/v1/jobs/9"


@respx.mock
def test_search_raises_on_http_error():
    respx.get(API_URL).mock(return_value=httpx.Response(500))
    client = ReliefWebClient(appname="a", countries=["Senegal"])
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="x"))


@respx.mock
def test_search_raises_on_malformed_json():
    respx.get(API_URL).mock(return_value=httpx.Response(200, text="<html>"))
    client = ReliefWebClient(appname="a", countries=["Senegal"])
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="x"))


@respx.mock
def test_search_skips_entries_missing_required_fields():
    payload = {"data": [{"id": "1", "fields": {"body": "no title, no url"}}]}
    respx.get(API_URL).mock(return_value=httpx.Response(200, json=payload))
    client = ReliefWebClient(appname="a", countries=["Senegal"])
    assert client.search(SearchCriteria(keywords="x")) == []
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `cd backend && python -m pytest tests/job_search/test_reliefweb.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.job_search.reliefweb'`

- [ ] **Step 3: Implémenter `reliefweb.py`**

`backend/app/job_search/reliefweb.py` :

```python
import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria
from app.job_search.timestamps import parse_iso_datetime

_API_URL = "https://api.reliefweb.int/v1/jobs"
_LIMIT = 20
_INCLUDE_FIELDS = (
    "title",
    "url",
    "url_alias",
    "source.name",
    "country.name",
    "city.name",
    "date.created",
    "body",
)


class ReliefWebClient:
    """ReliefWeb (api.reliefweb.int): humanitarian / NGO job postings, with
    strong coverage of West and Central Africa. Public API, no key; an
    `appname` identifying the caller is expected. Keyword search is
    server-side (query[value]); results are restricted to a configured set
    of countries via a country.name filter."""

    def __init__(
        self,
        appname: str,
        countries: list[str],
        http_client: httpx.Client | None = None,
    ):
        self._appname = appname
        self._countries = countries
        self._http = http_client or httpx.Client(timeout=10.0)

    def _params(self, criteria: SearchCriteria) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = [
            ("appname", self._appname),
            ("profile", "list"),
            ("limit", str(_LIMIT)),
            ("query[value]", criteria.keywords),
            ("query[operator]", "AND"),
            ("filter[field]", "country.name"),
            ("filter[operator]", "OR"),
        ]
        for field_name in _INCLUDE_FIELDS:
            params.append(("fields[include][]", field_name))
        for country in self._countries:
            params.append(("filter[value][]", country))
        return params

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        try:
            response = self._http.get(_API_URL, params=self._params(criteria))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(
                f"ReliefWeb: échec de la recherche: {exc}"
            ) from exc

        try:
            payload = response.json()
            listings: list[JobListing] = []
            for entry in payload.get("data", []):
                fields = entry.get("fields") or {}
                title = fields.get("title")
                url = fields.get("url_alias") or fields.get("url")
                if not title or not url:
                    continue
                sources = fields.get("source") or []
                company = sources[0].get("name", "") if sources else ""
                countries = [c.get("name") for c in (fields.get("country") or [])]
                cities = [c.get("name") for c in (fields.get("city") or [])]
                location = ", ".join(
                    part for part in [*cities[:1], *countries[:1]] if part
                ) or None
                created = (fields.get("date") or {}).get("created")
                listings.append(
                    JobListing(
                        title=title,
                        company=company,
                        location=location,
                        snippet=(fields.get("body") or "")[:500],
                        url=url,
                        source="reliefweb",
                        ats_type=None,
                        posted_at=parse_iso_datetime(created),
                    )
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobSearchSourceError("ReliefWeb: réponse invalide.") from exc

        return listings
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `cd backend && python -m pytest tests/job_search/test_reliefweb.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/reliefweb.py backend/tests/job_search/test_reliefweb.py
git commit -m "feat(job-search): add ReliefWeb source client

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 3 : `JobicyClient` (API JSON, remote-only)

**Files:**
- Create: `backend/app/job_search/jobicy.py`
- Create: `backend/tests/job_search/test_jobicy.py`

**Interfaces:**
- Consumes: `SearchCriteria`, `JobListing`, `JobSearchSourceError`, `parse_iso_datetime`, `keyword_matches_title` (`app.job_search.keyword_matching`).
- Produces :
  - `class JobicyClient` avec `__init__(self, http_client: httpx.Client | None = None)` et `search(self, criteria: SearchCriteria) -> list[JobListing]`.
  - **Règle remote-only** : si `criteria.remote` est falsy **et** `criteria.location` est renseigné (non vide), `search` renvoie `[]` sans appel réseau (une source 100 % remote ne doit pas polluer une recherche géolocalisée non-remote). Sinon, appel + filtrage mots-clés côté client sur le titre.
  - `source` : `"jobicy"`.

**Contexte API (vérifié 2026-08) :** `GET https://jobicy.com/api/v2/remote-jobs?count=50&tag=<keywords>`
- Réponse : `{"jobs": [{"id": 1, "url": "...", "jobTitle": "...", "companyName": "...", "jobGeo": "Anywhere", "jobType": ["full-time"], "jobDescription": "<p>...</p>", "pubDate": "2026-08-20 10:00:00", "salaryMin": 90000, "salaryMax": 120000, "salaryCurrency": "USD"}]}`
- `pubDate` : format `"YYYY-MM-DD HH:MM:SS"` → remplacer l'espace par `T` avant `parse_iso_datetime`.

- [ ] **Step 1: Écrire le test qui échoue**

`backend/tests/job_search/test_jobicy.py` :

```python
import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.jobicy import JobicyClient
from app.job_search.schemas import SearchCriteria

API_URL = "https://jobicy.com/api/v2/remote-jobs"

_PAYLOAD = {
    "jobs": [
        {
            "id": 1,
            "url": "https://jobicy.com/jobs/acme-python-developer",
            "jobTitle": "Python Developer",
            "companyName": "Acme",
            "jobGeo": "Anywhere",
            "jobType": ["full-time"],
            "jobDescription": "<p>Build things</p>",
            "pubDate": "2026-08-20 10:00:00",
            "salaryMin": 90000,
            "salaryMax": 120000,
            "salaryCurrency": "USD",
        },
        {
            "id": 2,
            "url": "https://jobicy.com/jobs/acme-designer",
            "jobTitle": "Product Designer",
            "companyName": "Acme",
            "jobGeo": "Anywhere",
            "jobType": ["full-time"],
            "jobDescription": "<p>Design things</p>",
            "pubDate": "2026-08-19 10:00:00",
        },
    ]
}


@respx.mock
def test_search_returns_keyword_matched_listings():
    respx.get(API_URL).mock(return_value=httpx.Response(200, json=_PAYLOAD))
    client = JobicyClient()
    listings = client.search(SearchCriteria(keywords="python", remote=True))
    assert [l.title for l in listings] == ["Python Developer"]
    assert listings[0].source == "jobicy"
    assert listings[0].salary == "90000 - 120000 USD"
    assert listings[0].posted_at is not None
    assert "<p>" not in listings[0].snippet


@respx.mock
def test_returns_empty_without_network_when_located_and_not_remote():
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json=_PAYLOAD))
    client = JobicyClient()
    result = client.search(SearchCriteria(keywords="python", location="Dakar"))
    assert result == []
    assert route.call_count == 0


@respx.mock
def test_queries_when_no_location_even_if_remote_flag_absent():
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json=_PAYLOAD))
    client = JobicyClient()
    client.search(SearchCriteria(keywords="python"))
    assert route.call_count == 1


@respx.mock
def test_raises_on_http_error():
    respx.get(API_URL).mock(return_value=httpx.Response(502))
    with pytest.raises(JobSearchSourceError):
        JobicyClient().search(SearchCriteria(keywords="python", remote=True))


@respx.mock
def test_raises_on_malformed_json():
    respx.get(API_URL).mock(return_value=httpx.Response(200, text="nope"))
    with pytest.raises(JobSearchSourceError):
        JobicyClient().search(SearchCriteria(keywords="python", remote=True))
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `cd backend && python -m pytest tests/job_search/test_jobicy.py -v`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter `jobicy.py`**

`backend/app/job_search/jobicy.py` :

```python
import re

import httpx

from app.job_search.errors import JobSearchSourceError
from app.job_search.keyword_matching import keyword_matches_title
from app.job_search.schemas import JobListing, SearchCriteria
from app.job_search.timestamps import parse_iso_datetime

_API_URL = "https://jobicy.com/api/v2/remote-jobs"
_COUNT = 50
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    return _TAG_RE.sub("", value or "").strip()


class JobicyClient:
    """Jobicy (jobicy.com/api/v2): remote-only job board, worldwide. Public
    API, no key. Every listing is remote, so this client contributes only
    when the search is remote-oriented: it returns nothing (without a
    network call) when the user pinned a location and did not ask for
    remote. Keyword filtering is client-side against the job title."""

    def __init__(self, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(timeout=10.0)

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        if not criteria.remote and (criteria.location or "").strip():
            return []

        try:
            response = self._http.get(
                _API_URL, params={"count": _COUNT, "tag": criteria.keywords}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JobSearchSourceError(f"Jobicy: échec de la recherche: {exc}") from exc

        try:
            payload = response.json()
            listings: list[JobListing] = []
            for job in payload.get("jobs", []):
                title = job.get("jobTitle")
                url = job.get("url")
                if not title or not url:
                    continue
                if not keyword_matches_title(criteria.keywords, title):
                    continue
                salary = None
                smin, smax = job.get("salaryMin"), job.get("salaryMax")
                currency = job.get("salaryCurrency") or ""
                if smin and smax:
                    salary = f"{smin} - {smax} {currency}".strip()
                pub = (job.get("pubDate") or "").replace(" ", "T")
                listings.append(
                    JobListing(
                        title=title,
                        company=job.get("companyName", ""),
                        location=job.get("jobGeo") or "Remote",
                        snippet=_strip_html(job.get("jobDescription", ""))[:500],
                        url=url,
                        source="jobicy",
                        ats_type=None,
                        salary=salary,
                        posted_at=parse_iso_datetime(pub),
                    )
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobSearchSourceError("Jobicy: réponse invalide.") from exc

        return listings
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `cd backend && python -m pytest tests/job_search/test_jobicy.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/jobicy.py backend/tests/job_search/test_jobicy.py
git commit -m "feat(job-search): add Jobicy remote-only source client

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 4 : `RssFeedClient` paramétré (We Work Remotely, RemoteOK, NGO Jobs)

**Files:**
- Create: `backend/app/job_search/rss_feeds.py`
- Create: `backend/tests/job_search/test_rss_feeds.py`

**Interfaces:**
- Consumes: `feedparser`, `feed_cache.get_or_fetch` (Task 1), `SearchCriteria`, `JobListing`, `JobSearchSourceError`, `keyword_matches_title`.
- Produces :
  - `class RssFeedClient` :
    `__init__(self, source_name: str, feed_urls: list[str], remote_only: bool, http_client: httpx.Client | None = None, ttl_minutes: int = 30)`
    et `search(self, criteria: SearchCriteria) -> list[JobListing]`.
  - Comportement : pour chaque URL de `feed_urls`, récupère le corps via `feed_cache.get_or_fetch`, parse avec `feedparser.parse(body)`, mappe chaque entrée en `JobListing` (`source=source_name`), garde celles dont le titre matche `criteria.keywords` (`keyword_matches_title`). Si `remote_only` et `criteria` est géolocalisée non-remote (`not criteria.remote and criteria.location`), renvoie `[]` sans requête (même règle que Jobicy). Déduplique par `link` au sein du client. Une erreur sur **une** URL de flux propage `JobSearchSourceError` (le flux fait partie intégrante de la source).
  - Titres We Work Remotely au format `"Entreprise: Intitulé"` → si le titre contient `": "`, `company` = partie gauche, `title` = partie droite ; sinon `company=""`, `title` = titre complet.

- [ ] **Step 1: Écrire le test qui échoue**

`backend/tests/job_search/test_rss_feeds.py` :

```python
import httpx
import pytest
import respx

from app.job_search import feed_cache
from app.job_search.errors import JobSearchSourceError
from app.job_search.rss_feeds import RssFeedClient
from app.job_search.schemas import SearchCriteria

FEED_A = "https://weworkremotely.com/remote-jobs.rss"

_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Acme: Senior Python Developer</title>
    <link>https://weworkremotely.com/remote-jobs/acme-python</link>
    <description>Remote Python role, worldwide.</description>
    <pubDate>Wed, 20 Aug 2026 10:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Globex: Product Designer</title>
    <link>https://weworkremotely.com/remote-jobs/globex-designer</link>
    <description>Design systems.</description>
    <pubDate>Tue, 19 Aug 2026 10:00:00 +0000</pubDate>
  </item>
</channel></rss>
"""


@pytest.fixture(autouse=True)
def _clear():
    feed_cache.clear()
    yield
    feed_cache.clear()


@respx.mock
def test_returns_keyword_matched_entries_with_company_split():
    respx.get(FEED_A).mock(return_value=httpx.Response(200, text=_RSS))
    client = RssFeedClient("weworkremotely", [FEED_A], remote_only=True)
    listings = client.search(SearchCriteria(keywords="python", remote=True))
    assert len(listings) == 1
    assert listings[0].title == "Senior Python Developer"
    assert listings[0].company == "Acme"
    assert listings[0].url == "https://weworkremotely.com/remote-jobs/acme-python"
    assert listings[0].source == "weworkremotely"
    assert listings[0].posted_at is not None


@respx.mock
def test_remote_only_returns_empty_when_located_and_not_remote():
    route = respx.get(FEED_A).mock(return_value=httpx.Response(200, text=_RSS))
    client = RssFeedClient("weworkremotely", [FEED_A], remote_only=True)
    assert client.search(SearchCriteria(keywords="python", location="Dakar")) == []
    assert route.call_count == 0


@respx.mock
def test_non_remote_only_feed_ignores_location_rule():
    respx.get(FEED_A).mock(return_value=httpx.Response(200, text=_RSS))
    client = RssFeedClient("ngojobs", [FEED_A], remote_only=False)
    listings = client.search(SearchCriteria(keywords="python", location="Dakar"))
    assert len(listings) == 1


@respx.mock
def test_dedupes_identical_links_across_feeds():
    feed_b = "https://example.com/b.rss"
    respx.get(FEED_A).mock(return_value=httpx.Response(200, text=_RSS))
    respx.get(feed_b).mock(return_value=httpx.Response(200, text=_RSS))
    client = RssFeedClient("ngojobs", [FEED_A, feed_b], remote_only=False)
    listings = client.search(SearchCriteria(keywords="python"))
    assert len(listings) == 1


@respx.mock
def test_raises_when_a_feed_url_is_unavailable():
    respx.get(FEED_A).mock(return_value=httpx.Response(500))
    client = RssFeedClient("ngojobs", [FEED_A], remote_only=False)
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `cd backend && python -m pytest tests/job_search/test_rss_feeds.py -v`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter `rss_feeds.py`**

`backend/app/job_search/rss_feeds.py` :

```python
import calendar
from datetime import UTC, datetime, timedelta

import feedparser
import httpx

from app.job_search import feed_cache
from app.job_search.keyword_matching import keyword_matches_title
from app.job_search.schemas import JobListing, SearchCriteria


def _entry_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)
    except (ValueError, OverflowError, OSError):
        return None


def _split_company_title(raw_title: str) -> tuple[str, str]:
    if ": " in raw_title:
        company, _, title = raw_title.partition(": ")
        return company.strip(), title.strip()
    return "", raw_title.strip()


class RssFeedClient:
    """Generic RSS/Atom job-feed adapter. One instance per logical source
    (We Work Remotely, RemoteOK, NGO Jobs in Africa), configured with one or
    more feed URLs. Feed bodies are cached per-URL (see feed_cache) so
    repeated searches within the TTL don't re-download them. Keyword
    filtering is client-side against the entry title. `remote_only` sources
    contribute nothing to a location-pinned, non-remote search."""

    def __init__(
        self,
        source_name: str,
        feed_urls: list[str],
        remote_only: bool,
        http_client: httpx.Client | None = None,
        ttl_minutes: int = 30,
    ):
        self._source = source_name
        self._feed_urls = feed_urls
        self._remote_only = remote_only
        self._http = http_client or httpx.Client(
            timeout=10.0, headers={"User-Agent": "ATSDiagnosticBot/1.0"}
        )
        self._ttl = timedelta(minutes=ttl_minutes)

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        if self._remote_only and not criteria.remote and (criteria.location or "").strip():
            return []

        listings: list[JobListing] = []
        seen_urls: set[str] = set()
        for feed_url in self._feed_urls:
            body = feed_cache.get_or_fetch(feed_url, self._http, self._ttl)
            parsed = feedparser.parse(body)
            for entry in parsed.entries:
                link = entry.get("link")
                raw_title = entry.get("title")
                if not link or not raw_title or link in seen_urls:
                    continue
                if not keyword_matches_title(criteria.keywords, raw_title):
                    continue
                seen_urls.add(link)
                company, title = _split_company_title(raw_title)
                summary = entry.get("summary", "") or entry.get("description", "")
                listings.append(
                    JobListing(
                        title=title,
                        company=company,
                        location="Remote" if self._remote_only else None,
                        snippet=summary[:500],
                        url=link,
                        source=self._source,
                        ats_type=None,
                        posted_at=_entry_datetime(entry),
                    )
                )
        return listings
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `cd backend && python -m pytest tests/job_search/test_rss_feeds.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/rss_feeds.py backend/tests/job_search/test_rss_feeds.py
git commit -m "feat(job-search): add parametrized RSS feed source client

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 5 : Déduplication par URL dans l'agrégateur

**Files:**
- Modify: `backend/app/job_search/aggregator.py` (fonction `search_jobs`, ~ lignes 51-71)
- Modify: `backend/tests/job_search/test_aggregator.py`

**Interfaces:**
- Consumes: rien de nouveau.
- Produces : `search_jobs` renvoie désormais au plus une `JobListing` par `url` (première rencontrée gagne — l'ordre d'itération des `clients` est préservé, donc les sources « primaires » historiques ont priorité sur les nouvelles). Signature inchangée.

- [ ] **Step 1: Ajouter le test qui échoue**

Ajouter à `backend/tests/job_search/test_aggregator.py` :

```python
def test_search_jobs_dedupes_listings_sharing_a_url():
    shared = JobListing(
        title="Dev",
        company="Acme",
        location="Remote",
        snippet="...",
        url="https://example.com/same",
        source="a",
        ats_type=None,
    )

    class ClientA:
        def search(self, criteria):
            return [shared]

    class ClientB:
        def search(self, criteria):
            return [shared.model_copy(update={"source": "b"})]

    listings, _ = search_jobs(
        SearchCriteria(keywords="dev"),
        {"a": ClientA(), "b": ClientB()},
    )
    assert len(listings) == 1
    assert listings[0].source == "a"
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `cd backend && python -m pytest tests/job_search/test_aggregator.py::test_search_jobs_dedupes_listings_sharing_a_url -v`
Expected: FAIL — `assert 2 == 1`

- [ ] **Step 3: Implémenter la dédup**

Dans `backend/app/job_search/aggregator.py`, `search_jobs` : après la boucle de collecte et avant le `return`, dédupliquer en conservant l'ordre. Remplacer le `return` final :

```python
    seen_urls: set[str] = set()
    deduped: list[JobListing] = []
    for listing in listings:
        if listing.url in seen_urls:
            continue
        seen_urls.add(listing.url)
        if _passes_filters(listing, criteria):
            deduped.append(listing)
    return deduped, unavailable_sources
```

(Supprimer l'ancienne compréhension de liste `return [listing for listing in listings if _passes_filters(...)], unavailable_sources`.)

- [ ] **Step 4: Lancer les tests de l'agrégateur**

Run: `cd backend && python -m pytest tests/job_search/test_aggregator.py -v`
Expected: PASS (tous, y compris le nouveau).

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/aggregator.py backend/tests/job_search/test_aggregator.py
git commit -m "feat(job-search): dedupe merged listings by URL in aggregator

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 6 : Câblage (config, dépendances, router, daily_search) + vérification réelle

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/job_search/dependencies.py`
- Modify: `backend/app/routers/job_search.py` (dict `primary_clients` dans `search`, ~ lignes 93-97)
- Modify: `backend/app/job_search/daily_search.py` (dict `primary_clients` dans `_process_saved_search`, ~ lignes 77-82)
- Modify: `backend/tests/job_search/test_daily_search.py` si un test construit les clients en dur (à vérifier — sinon ne pas toucher)

**Interfaces:**
- Consumes: `ReliefWebClient`, `JobicyClient`, `RssFeedClient` (Tasks 2-4).
- Produces : `get_job_search_clients()` renvoie un dict incluant les clés `reliefweb`, `jobicy`, `weworkremotely`, `remoteok`, `ngojobs`. Ces 5 clés sont ajoutées aux dicts `primary_clients` du router et de `daily_search`.

**Nouvelles clés `config.py`** (avec valeurs par défaut, section après `la_bonne_alternance_api_key`) :

```python
    reliefweb_appname: str = "ats-diagnostic-search"
    reliefweb_countries: list[str] = [
        "Senegal", "Ivory Coast", "Cameroon", "Gabon", "Benin",
        "Togo", "Mali", "Burkina Faso", "Congo",
    ]
    ngojobs_feed_urls: list[str] = ["https://ngojobsinafrica.com/media-rss/"]
    weworkremotely_feed_urls: list[str] = [
        "https://weworkremotely.com/remote-jobs.rss"
    ]
    remoteok_feed_urls: list[str] = ["https://remoteok.com/remote-jobs.rss"]
```

> Note d'implémentation : `pydantic-settings` parse une variable d'env `list[str]` en JSON (`RELIEFWEB_COUNTRIES='["Senegal","Mali"]'`). Les valeurs par défaut ci-dessus suffisent pour la v1 ; les URLs de flux NGO Jobs par pays pourront être ajoutées à `ngojobs_feed_urls` une fois leur format confirmé (le flux général `media-rss` est un défaut fonctionnel en attendant).

- [ ] **Step 1: Écrire le test de câblage qui échoue**

Ajouter `backend/tests/job_search/test_dependencies.py` :

```python
from app.job_search.dependencies import get_job_search_clients


def test_all_expected_sources_are_registered():
    get_job_search_clients.cache_clear()
    clients = get_job_search_clients()
    for key in (
        "france_travail", "adzuna", "la_bonne_alternance", "greenhouse", "lever",
        "reliefweb", "jobicy", "weworkremotely", "remoteok", "ngojobs",
    ):
        assert key in clients, key
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `cd backend && python -m pytest tests/job_search/test_dependencies.py -v`
Expected: FAIL — `AssertionError: reliefweb`

- [ ] **Step 3: Enregistrer les clients dans `dependencies.py`**

Dans `get_job_search_clients()`, ajouter aux entrées du dict retourné :

```python
        "reliefweb": ReliefWebClient(
            appname=settings.reliefweb_appname,
            countries=settings.reliefweb_countries,
        ),
        "jobicy": JobicyClient(),
        "weworkremotely": RssFeedClient(
            "weworkremotely", settings.weworkremotely_feed_urls, remote_only=True
        ),
        "remoteok": RssFeedClient(
            "remoteok", settings.remoteok_feed_urls, remote_only=True
        ),
        "ngojobs": RssFeedClient(
            "ngojobs", settings.ngojobs_feed_urls, remote_only=False
        ),
```

et les imports correspondants en haut du fichier (`from app.job_search.reliefweb import ReliefWebClient`, etc.).

- [ ] **Step 4: Lancer le test de câblage**

Run: `cd backend && python -m pytest tests/job_search/test_dependencies.py -v`
Expected: PASS

- [ ] **Step 5: Ajouter les sources au router**

Dans `backend/app/routers/job_search.py`, fonction `search`, étendre `primary_clients` :

```python
    primary_clients: dict[str, SearchClient] = {
        "france_travail": cast(SearchClient, clients["france_travail"]),
        "adzuna": cast(SearchClient, clients["adzuna"]),
        "la_bonne_alternance": cast(SearchClient, clients["la_bonne_alternance"]),
        "reliefweb": cast(SearchClient, clients["reliefweb"]),
        "jobicy": cast(SearchClient, clients["jobicy"]),
        "weworkremotely": cast(SearchClient, clients["weworkremotely"]),
        "remoteok": cast(SearchClient, clients["remoteok"]),
        "ngojobs": cast(SearchClient, clients["ngojobs"]),
    }
```

- [ ] **Step 6: Ajouter les sources à `daily_search.py`**

Même extension du dict `primary_clients` dans `_process_saved_search` (mêmes 5 clés `cast(SearchClient, clients[...])`).

- [ ] **Step 7: Lancer toute la suite backend**

Run: `cd backend && python -m pytest -q`
Expected: PASS (aucune régression). Si `tests/job_search/test_daily_search.py` casse parce qu'il asserte un nombre exact d'appels de sources, l'ajuster pour refléter les nouvelles sources (mocker les nouveaux clients pour renvoyer `[]`).

- [ ] **Step 8: Lint & types**

Run: `cd backend && ruff check app/ && ruff format --check app/ && mypy app/`
Expected: PASS (corriger le nécessaire).

- [ ] **Step 9: Vérification réelle (Docker + navigateur)**

```bash
docker compose up -d --build backend
docker logs --tail 50 search-backend-1
curl -s http://localhost:8000/docs -o /dev/null -w "%{http_code}\n"
```

Puis dans le navigateur (`claude-in-chrome`), connecté à `frontend-v3` :
1. Faire une recherche remote : mots-clés `python`, **sans localisation**, case remote cochée → vérifier que des offres `jobicy` / `weworkremotely` / `remoteok` apparaissent (champ source visible ou via `read_network_requests` sur la réponse `/job-search/search`).
2. Faire une recherche ONG : mots-clés `logisticien`, localisation `Dakar` → vérifier qu'au moins une offre `reliefweb` ou `ngojobs` apparaît.
3. Faire une recherche classique (`comptable`, `Paris`) → vérifier que les sources françaises répondent toujours et que les offres remote-only ne polluent PAS (règle Jobicy/RSS).
4. Ouvrir une offre d'une nouvelle source dans le workspace → pas d'erreur console, pas de 500 (`docker logs`).
5. Vérifier `unavailable_sources` dans la réponse : si une nouvelle source est listée indisponible en permanence, investiguer (mauvaise URL de flux, format d'API différent de la fixture) avant de conclure la tâche.

- [ ] **Step 10: Commit**

```bash
git add backend/app/config.py backend/app/job_search/dependencies.py backend/app/routers/job_search.py backend/app/job_search/daily_search.py backend/tests/job_search/test_dependencies.py
# + tests/job_search/test_daily_search.py seulement s'il a dû être ajusté
git commit -m "feat(job-search): wire African + remote sources into search and daily digest

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Self-Review (effectué à la rédaction)

**Couverture du spec (Famille 1) :**
- ReliefWeb (API) → Task 2 ✅
- Jobicy (API remote) → Task 3 ✅
- NGO Jobs in Africa (RSS) → Task 4 (`RssFeedClient` `ngojobs`, `remote_only=False`) ✅
- We Work Remotely / RemoteOK (RSS remote) → Task 4 ✅
- « flux RSS complets → fetch + cache mémoire + filtrage mémoire » → Task 1 (`feed_cache`) + Task 4 (filtrage `keyword_matches_title`) ✅
- « chaque source = un module implémentant `SearchClient`, enregistré dans `get_job_search_clients()` » → Tasks 2-4 + Task 6 ✅
- Dédup par URL (spec : « merge + dédup par URL ») → Task 5 ✅
- `JobSearchSourceError` → `unavailable_sources` réutilisé tel quel → aucune modif nécessaire, vérifié en Task 6 step 9 ✅

**Explicitement hors de ce plan (conforme au spec) :** champ `is_remote` first-class, badge Remote, mode remote côté `_passes_filters`, autocomplétion de localisation, table `crawled_listing` et crawlers → Plans B et C.

**Scan placeholders :** aucun « TBD/TODO ». Le seul point ouvert (URLs de flux NGO Jobs par pays) a un défaut fonctionnel concret (`media-rss`) et est documenté comme extension de config, pas comme blocage.

**Cohérence des types :** `search(criteria) -> list[JobListing]` partout ; constructeurs `__init__` avec `http_client: httpx.Client | None = None` comme les clients existants ; `feed_cache.get_or_fetch(url, http_client, ttl)` — même signature consommée en Task 4. `source` : `reliefweb` / `jobicy` / `weworkremotely` / `remoteok` / `ngojobs` — mêmes chaînes dans dependencies, router, daily_search, tests.

## Execution Handoff

Voir fin de conversation.
