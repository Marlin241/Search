# Plan B — Infra de crawl + crawler Emploi Dakar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persister les offres de job boards locaux sénégalais dans une table `crawled_listing` alimentée par un crawl périodique, et les servir à la recherche via un client DB qui implémente le même `Protocol` `SearchClient` que les sources live — avec un premier crawler concret : Emploi Dakar.

**Architecture:** Un job APScheduler appelle `run_crawl` toutes les ~3h ; pour chaque crawler activé, il récupère des `CrawledListingData` normalisés et les upsert par URL dans `crawled_listing` (nouvelles → INSERT, revues → UPDATE + `last_seen_at`, absentes N fois → `is_active=False`). À la recherche, `CrawledListingClient.search()` lit cette table (filtres mots-clés / lieu / contrat / remote en SQL) et renvoie des `JobListing` ; l'agrégateur le traite comme n'importe quelle source. Le crawler Emploi Dakar lit le sitemap `job_listing-sitemap.xml` du site puis parse chaque page d'offre (HTML statique, WP Job Manager).

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2 (`Mapped`/`mapped_column`), Alembic (migrations écrites à la main), httpx, BeautifulSoup (`html.parser` / `xml`… voir note lxml), APScheduler, pytest + `respx`.

**Spec:** `docs/superpowers/specs/2026-08-28-sources-afrique-ouest-design.md` — « Famille 2 — Sources crawlées », composants 1-4 et 8.

## Global Constraints

- **Purement additif** : ne modifier la signature d'aucune source existante ; ne changer aucun comportement de `frontend-v3`.
- **Branche** : `feature/talya-inspired-rebuild` uniquement, jamais `main`. Commits scopés (`git add <chemins>` explicites, jamais `-A`).
- **Après toute modif backend testée en réel** : `docker compose up -d --build backend` depuis la racine du repo, puis `docker logs search-backend-1` + `curl http://localhost:8000/docs`. Le crawl écrit en base — les vérifications réelles se font contre le Postgres dockerisé, pas SQLite.
- **Migration Alembic écrite à la main** (le projet ne fait pas d'autogenerate) : `down_revision = "9c3b2b7e5a41"` (head actuelle — vérifier avec `alembic heads` avant d'écrire, prendre la vraie head si elle a bougé). `server_default` sur toute colonne non-nullable pour que la migration passe sur des lignes existantes (il n'y en a pas ici, mais c'est la convention du repo — cf. `4afb7f1be9a4`).
- **Pas de `BackgroundTasks` ni `lock_user_for_rate_limit`** dans ce plan : `run_crawl` est un job scheduler avec sa propre session (`database.SessionLocal`), hors cycle requête → la classe de deadlock de la Phase 4 ne s'applique pas. Ne pas introduire de `BackgroundTasks` ici.
- **`JobSearchSourceError`** (`app.job_search.errors`) reste la seule exception qu'un `SearchClient` laisse remonter à l'agrégateur.
- **Nommage `JobListing.source` / `CrawledListing.source`** : `emploi_dakar`. Le client DB agrégé s'enregistre sous la clé `"crawled"` dans `get_job_search_clients()`.
- **Politesse crawl** : User-Agent `ATSDiagnosticBot/1.0 (+<CRAWLER_CONTACT_URL>)`, délai `CRAWL_REQUEST_DELAY_SECONDS` entre requêtes, plafond `CRAWL_MAX_OFFERS_PER_SITE` de pages d'offres par site et par passage.
- **Note lxml / BeautifulSoup XML** : `BeautifulSoup(x, "xml")` exige `lxml`, **absent** du projet. Pour parser le sitemap XML, utiliser `BeautifulSoup(x, "html.parser")` (fonctionne sur le XML de sitemap : les balises `<loc>` / `<lastmod>` sont lues correctement en minuscules) — **ne pas** ajouter `lxml`.

---

## File Structure

**Créés :**
- `backend/app/models/crawled_listing.py` — modèle `CrawledListing`.
- `backend/alembic/versions/<rev>_add_crawled_listing.py` — migration (créer le fichier ; `<rev>` = valeur générée, voir Task 1).
- `backend/app/job_search/crawlers/__init__.py` — vide.
- `backend/app/job_search/crawlers/http.py` — `fetch_text(url, http_client)` : GET validé (schéma http/https, hôte non privé), cap taille de réponse, cap redirections. Lève `CrawlFetchError`.
- `backend/app/job_search/crawlers/base.py` — dataclasses `CrawledListingData` et `CrawlerConfig` ; protocole `Crawler`.
- `backend/app/job_search/crawlers/emploi_dakar.py` — `crawl(config, http_client) -> list[CrawledListingData]`.
- `backend/app/job_search/crawl_runner.py` — `run_crawl(db_session_factory)` + `_upsert_listings` + `_deactivate_stale`.
- `backend/app/job_search/crawled_listings.py` — `CrawledListingClient` (implémente `SearchClient`, lit `crawled_listing`).
- `backend/tests/job_search/crawlers/__init__.py` — vide.
- `backend/tests/job_search/crawlers/test_http.py`
- `backend/tests/job_search/crawlers/test_emploi_dakar.py`
- `backend/tests/job_search/crawlers/fixtures/emploi_dakar_sitemap.xml` — extrait réel du sitemap (3-4 `<url>`).
- `backend/tests/job_search/crawlers/fixtures/emploi_dakar_offer.html` — une page d'offre réelle enregistrée.
- `backend/tests/job_search/test_crawl_runner.py`
- `backend/tests/job_search/test_crawled_listings_client.py`
- `backend/tests/models/test_crawled_listing.py`

**Modifiés :**
- `backend/app/models/__init__.py` — importer + exporter `CrawledListing`.
- `backend/app/config.py` — nouvelles clés.
- `backend/app/job_search/dependencies.py` — enregistrer `"crawled"`.
- `backend/app/routers/job_search.py` — `"crawled"` dans `primary_clients`.
- `backend/app/job_search/daily_search.py` — `"crawled"` dans `primary_clients`.
- `backend/app/main.py` — job APScheduler `crawl`.
- `backend/tests/routers/test_job_search.py` — ajouter `"crawled": EmptyPrimaryClient()` à `_default_clients` et aux 2 dicts inline.
- `backend/tests/job_search/test_daily_search.py` — ajouter `"crawled": _EmptyClient()` à `_clients()`.

---

## Task 1 : Modèle `CrawledListing` + migration

**Files:**
- Create: `backend/app/models/crawled_listing.py`
- Create: `backend/alembic/versions/<rev>_add_crawled_listing.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/models/test_crawled_listing.py`

**Interfaces:**
- Produces : classe `CrawledListing` (table `crawled_listing`) avec les colonnes :
  `id` int PK ; `url` str(2048) unique not-null indexé ; `source` str(64) not-null indexé ; `title` str(500) not-null ; `company` str(255) nullable ; `location` str(255) nullable ; `snippet` Text not-null default `""` ; `salary` str(255) nullable ; `contract_type` str(64) nullable ; `is_remote` bool not-null default `False` ; `posted_at` DateTime nullable ; `first_seen_at` DateTime not-null ; `last_seen_at` DateTime not-null indexé ; `is_active` bool not-null default `True` indexé ; `missed_crawls` int not-null default `0`.

- [ ] **Step 1: Écrire le test qui échoue**

`backend/tests/models/test_crawled_listing.py` :

```python
from datetime import UTC, datetime

from app.models.crawled_listing import CrawledListing


def test_crawled_listing_persists_with_defaults(db_session):
    now = datetime(2026, 8, 28, tzinfo=UTC).replace(tzinfo=None)
    row = CrawledListing(
        url="https://www.emploidakar.com/offre-demploi/x/",
        source="emploi_dakar",
        title="Développeur",
        first_seen_at=now,
        last_seen_at=now,
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(CrawledListing).one()
    assert fetched.is_active is True
    assert fetched.is_remote is False
    assert fetched.missed_crawls == 0
    assert fetched.snippet == ""


def test_crawled_listing_url_is_unique(db_session):
    import pytest
    from sqlalchemy.exc import IntegrityError

    now = datetime(2026, 8, 28).replace(microsecond=0)
    for _ in range(2):
        db_session.add(
            CrawledListing(
                url="https://dup/", source="s", title="t",
                first_seen_at=now, last_seen_at=now,
            )
        )
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/models/test_crawled_listing.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.crawled_listing'`

- [ ] **Step 3: Écrire le modèle**

`backend/app/models/crawled_listing.py` :

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CrawledListing(Base):
    """A job offer discovered on a crawled local job board (no search API of
    its own). Populated by app.job_search.crawl_runner.run_crawl on a
    schedule and read back at search time by
    app.job_search.crawled_listings.CrawledListingClient. Keyed by `url`;
    `is_active` goes False after `missed_crawls` reaches
    settings.crawl_deactivate_after consecutive absences."""

    __tablename__ = "crawled_listing"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    salary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_remote: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    missed_crawls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
```

Puis dans `backend/app/models/__init__.py` : ajouter `from app.models.crawled_listing import CrawledListing` (ordre alpha, après `compatibility_request_log`) et `"CrawledListing",` dans `__all__`.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd backend && ./venv/bin/python -m pytest tests/models/test_crawled_listing.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Écrire la migration**

Vérifier la head : `cd backend && ./venv/bin/alembic heads` → doit afficher `9c3b2b7e5a41`. Si différent, utiliser cette valeur comme `down_revision`.

Générer un identifiant de révision : `cd backend && ./venv/bin/python -c "import uuid; print(uuid.uuid4().hex[:12])"` → `<rev>`.

Créer `backend/alembic/versions/<rev>_add_crawled_listing.py` :

```python
"""add crawled_listing

Revision ID: <rev>
Revises: 9c3b2b7e5a41
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "<rev>"
down_revision: Union[str, Sequence[str], None] = "9c3b2b7e5a41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crawled_listing",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("salary", sa.String(length=255), nullable=True),
        sa.Column("contract_type", sa.String(length=64), nullable=True),
        sa.Column(
            "is_remote", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "missed_crawls", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.create_index(
        "ix_crawled_listing_url", "crawled_listing", ["url"], unique=True
    )
    op.create_index("ix_crawled_listing_source", "crawled_listing", ["source"])
    op.create_index(
        "ix_crawled_listing_last_seen_at", "crawled_listing", ["last_seen_at"]
    )
    op.create_index("ix_crawled_listing_is_active", "crawled_listing", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_crawled_listing_is_active", table_name="crawled_listing")
    op.drop_index("ix_crawled_listing_last_seen_at", table_name="crawled_listing")
    op.drop_index("ix_crawled_listing_source", table_name="crawled_listing")
    op.drop_index("ix_crawled_listing_url", table_name="crawled_listing")
    op.drop_table("crawled_listing")
```

- [ ] **Step 6: Vérifier la migration (aller-retour)**

Run:
```bash
cd backend && ./venv/bin/alembic upgrade head && ./venv/bin/alembic downgrade -1 && ./venv/bin/alembic upgrade head
```
Expected: aucune erreur ; la table `crawled_listing` existe après le dernier `upgrade`.
(Nécessite un Postgres joignable via `DATABASE_URL` — sinon faire cette étape après le `docker compose up` de la Task 6, et le noter.)

- [ ] **Step 7: Suite complète des modèles + lint/types**

Run: `cd backend && ./venv/bin/python -m pytest tests/models/ -q && ./venv/bin/ruff check app/ && ./venv/bin/mypy app/models/crawled_listing.py`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/crawled_listing.py backend/app/models/__init__.py backend/alembic/versions/<rev>_add_crawled_listing.py backend/tests/models/test_crawled_listing.py
git commit -m "feat(job-search): add CrawledListing model and migration

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 2 : `crawlers/http.py` — fetch validé et plafonné

**Files:**
- Create: `backend/app/job_search/crawlers/__init__.py` (vide)
- Create: `backend/app/job_search/crawlers/http.py`
- Create: `backend/tests/job_search/crawlers/__init__.py` (vide)
- Create: `backend/tests/job_search/crawlers/test_http.py`

**Interfaces:**
- Produces :
  - `class CrawlFetchError(Exception)` — échec de récupération/validation.
  - `fetch_text(url: str, http_client: httpx.Client, *, max_bytes: int = 3_000_000) -> str`
    — valide le schéma (`http`/`https` seulement) et rejette un hôte qui résout vers une adresse privée/loopback/link-local/reserved ; suit jusqu'à 5 redirections en revalidant chaque hop ; lit le corps en streaming en abandonnant au-delà de `max_bytes` ; renvoie le texte. Toute erreur → `CrawlFetchError`.
- Consumes: `httpx`, `ipaddress`, `socket`, `urllib.parse`.

> Note DRY : `app/offer_ingestion/scraper.py` a une logique de validation d'URL équivalente (`_validate_url`, `_read_body_with_cap`). Elle vit dans un autre package et sert un besoin différent (scraping d'une URL fournie par l'utilisateur). Ce plan **duplique volontairement** la partie validation dans `crawlers/http.py` plutôt que de refactorer un module qui marche — la mutualisation dans un `app/utils/` commun est un chantier séparé si elle se justifie.

- [ ] **Step 1: Écrire le test qui échoue**

`backend/tests/job_search/crawlers/test_http.py` :

```python
import httpx
import pytest
import respx

from app.job_search.crawlers.http import CrawlFetchError, fetch_text


@respx.mock
def test_returns_body_text():
    respx.get("https://example.com/x").mock(
        return_value=httpx.Response(200, text="<html>ok</html>")
    )
    with httpx.Client() as c:
        assert fetch_text("https://example.com/x", c) == "<html>ok</html>"


def test_rejects_non_http_scheme():
    with httpx.Client() as c:
        with pytest.raises(CrawlFetchError):
            fetch_text("file:///etc/passwd", c)


def test_rejects_private_host():
    with httpx.Client() as c:
        with pytest.raises(CrawlFetchError):
            fetch_text("http://127.0.0.1/x", c)
        with pytest.raises(CrawlFetchError):
            fetch_text("http://10.0.0.5/x", c)


@respx.mock
def test_http_error_becomes_crawl_fetch_error():
    respx.get("https://example.com/x").mock(return_value=httpx.Response(503))
    with httpx.Client() as c:
        with pytest.raises(CrawlFetchError):
            fetch_text("https://example.com/x", c)


@respx.mock
def test_body_over_cap_raises():
    respx.get("https://example.com/big").mock(
        return_value=httpx.Response(200, text="x" * 5000)
    )
    with httpx.Client() as c:
        with pytest.raises(CrawlFetchError):
            fetch_text("https://example.com/big", c, max_bytes=1000)
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/crawlers/test_http.py -q`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter `http.py`**

`backend/app/job_search/crawlers/http.py` :

```python
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_REDIRECTS = 5


class CrawlFetchError(Exception):
    pass


def _validate_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise CrawlFetchError(f"scheme '{parts.scheme}' not allowed")
    hostname = parts.hostname
    if not hostname:
        raise CrawlFetchError("missing hostname")
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise CrawlFetchError(f"cannot resolve '{hostname}': {exc}") from exc
    for info in addrinfo:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise CrawlFetchError(f"host '{hostname}' resolves to disallowed {ip}")


def fetch_text(
    url: str, http_client: httpx.Client, *, max_bytes: int = 3_000_000
) -> str:
    current = url
    try:
        for _ in range(_MAX_REDIRECTS + 1):
            _validate_url(current)
            with http_client.stream("GET", current) as response:
                if response.is_redirect:
                    loc = response.headers.get("location")
                    if not loc:
                        raise CrawlFetchError("redirect without Location")
                    current = str(httpx.URL(current).join(loc))
                    continue
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise CrawlFetchError(f"response exceeded {max_bytes} bytes")
                return body.decode("utf-8", errors="replace")
        raise CrawlFetchError("too many redirects")
    except httpx.HTTPError as exc:
        raise CrawlFetchError(f"fetch failed for {url}: {exc}") from exc
```

> Note : `http_client` doit être construit avec `follow_redirects=False` par l'appelant (le crawler) pour que la revalidation par hop fonctionne. Le préciser dans `emploi_dakar.py` / `crawl_runner.py`.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/crawlers/test_http.py -q`
Expected: PASS (5 tests)

- [ ] **Step 5: Lint / types / commit**

```bash
cd backend && ./venv/bin/ruff check app/job_search/crawlers/ tests/job_search/crawlers/ && ./venv/bin/ruff format app/job_search/crawlers/ tests/job_search/crawlers/ && ./venv/bin/mypy app/job_search/crawlers/http.py
git add backend/app/job_search/crawlers/__init__.py backend/app/job_search/crawlers/http.py backend/tests/job_search/crawlers/__init__.py backend/tests/job_search/crawlers/test_http.py
git commit -m "feat(job-search): add SSRF-safe capped fetch helper for crawlers

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 3 : Base crawler + crawler Emploi Dakar

**Files:**
- Create: `backend/app/job_search/crawlers/base.py`
- Create: `backend/app/job_search/crawlers/emploi_dakar.py`
- Create: `backend/tests/job_search/crawlers/test_emploi_dakar.py`
- Create: `backend/tests/job_search/crawlers/fixtures/emploi_dakar_sitemap.xml`
- Create: `backend/tests/job_search/crawlers/fixtures/emploi_dakar_offer.html`

**Interfaces:**
- Produces (`base.py`) :
  - `@dataclass(frozen=True) class CrawledListingData` : `url: str`, `title: str`, `company: str | None`, `location: str | None`, `snippet: str`, `salary: str | None`, `contract_type: str | None`, `is_remote: bool`, `posted_at: datetime | None`.
  - `@dataclass(frozen=True) class CrawlerConfig` : `source: str`, `base_url: str`, `max_offers: int`, `request_delay_seconds: float`, `user_agent: str`.
  - `class Crawler(Protocol)` : `source: str` ; `def crawl(self, config: CrawlerConfig, http_client: httpx.Client) -> list[CrawledListingData]: ...`
- Produces (`emploi_dakar.py`) :
  - `SITEMAP_PATH = "/job_listing-sitemap.xml"`
  - `class EmploiDakarCrawler` : `source = "emploi_dakar"` ; `crawl(config, http_client)` :
    1. `fetch_text(config.base_url + SITEMAP_PATH, http_client)` → parser les `<url>` : `(loc, lastmod)`.
    2. Trier par `lastmod` décroissant, garder les `config.max_offers` premières.
    3. Pour chacune : `time.sleep(config.request_delay_seconds)`, `fetch_text(loc, http_client)`, parser (`_parse_offer(html, url)`), accumuler. Une `CrawlFetchError` sur **une** offre est loggée (`logging.getLogger(__name__).warning`) et l'offre sautée — pas d'interruption. Une `CrawlFetchError` sur le **sitemap** est propagée.
  - `_parse_offer(html: str, url: str) -> CrawledListingData | None` — retourne `None` si `h1` absent (page inattendue).

**Sélecteurs Emploi Dakar (vérifiés sur le site 2026-08, WP Job Manager) :**
- titre : `soup.find("h1")` (niveau page)
- bloc : `soup.select_one(".single_job_listing")` ; si absent → `None`
- entreprise : `bloc.find(class_="company")` → `.get_text(" ", strip=True)`
- lieu : `bloc.find(class_="location")` → texte
- type contrat : `[li.get_text(strip=True) for li in bloc.select("li.job-type")]` → joint par `" / "` ou `None`
- date : `bloc.find("time")` → attribut `datetime` (`"2026-07-27"`) → `datetime.fromisoformat`
- description : `bloc.find(class_="job_description")` → `.get_text(" ", strip=True)[:600]` ; fallback `soup.find("meta", property="og:description")["content"]`
- `is_remote` : `True` si `"teletravail" in _strip_accents(f"{location} {title}")` ou `"remote"` / `"distanciel"`

- [ ] **Step 1: Enregistrer les fixtures réelles**

```bash
cd backend
curl -sL -A "Mozilla/5.0" "https://www.emploidakar.com/job_listing-sitemap.xml" -o /tmp/sm_full.xml
curl -sL -A "Mozilla/5.0" "$(./venv/bin/python -c "from bs4 import BeautifulSoup;s=BeautifulSoup(open('/tmp/sm_full.xml','rb').read(),'html.parser');print(s.find_all('url')[0].loc.get_text())")" -o tests/job_search/crawlers/fixtures/emploi_dakar_offer.html
```

Puis créer `tests/job_search/crawlers/fixtures/emploi_dakar_sitemap.xml` à la main, réduit à 3 `<url>` (copier 3 blocs `<url><loc>…</loc><lastmod>…</lastmod></url>` de `/tmp/sm_full.xml`, avec des `lastmod` distincts pour tester le tri). Exemple de forme :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.emploidakar.com/offre-demploi/aaa/</loc><lastmod>2026-08-20T10:00:00+00:00</lastmod></url>
  <url><loc>https://www.emploidakar.com/offre-demploi/bbb/</loc><lastmod>2026-08-25T10:00:00+00:00</lastmod></url>
  <url><loc>https://www.emploidakar.com/offre-demploi/ccc/</loc><lastmod>2026-08-10T10:00:00+00:00</lastmod></url>
</urlset>
```

- [ ] **Step 2: Écrire le test qui échoue**

`backend/tests/job_search/crawlers/test_emploi_dakar.py` :

```python
from pathlib import Path

import httpx
import pytest
import respx

from app.job_search.crawlers.base import CrawlerConfig
from app.job_search.crawlers.emploi_dakar import EmploiDakarCrawler, _parse_offer

FIXTURES = Path(__file__).parent / "fixtures"
SITEMAP = (FIXTURES / "emploi_dakar_sitemap.xml").read_text()
OFFER = (FIXTURES / "emploi_dakar_offer.html").read_text()

CONFIG = CrawlerConfig(
    source="emploi_dakar",
    base_url="https://www.emploidakar.com",
    max_offers=2,
    request_delay_seconds=0.0,
    user_agent="ATSDiagnosticBot/1.0 (+https://example.com)",
)


def test_parse_offer_extracts_core_fields():
    data = _parse_offer(OFFER, "https://www.emploidakar.com/offre-demploi/x/")
    assert data is not None
    assert data.title  # non-empty
    assert data.url == "https://www.emploidakar.com/offre-demploi/x/"
    assert data.snippet  # non-empty
    # posted_at parsed from <time datetime="YYYY-MM-DD"> when present
    # (don't assert an exact date - the fixture is a real page and will age)


def test_parse_offer_returns_none_without_h1():
    assert _parse_offer("<html><body>nope</body></html>", "https://x/") is None


@respx.mock
def test_crawl_reads_sitemap_then_fetches_capped_most_recent_offers():
    respx.get("https://www.emploidakar.com/job_listing-sitemap.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP)
    )
    # max_offers=2 -> only the two most recent lastmod entries (bbb, aaa)
    bbb = respx.get("https://www.emploidakar.com/offre-demploi/bbb/").mock(
        return_value=httpx.Response(200, text=OFFER)
    )
    aaa = respx.get("https://www.emploidakar.com/offre-demploi/aaa/").mock(
        return_value=httpx.Response(200, text=OFFER)
    )
    ccc = respx.get("https://www.emploidakar.com/offre-demploi/ccc/").mock(
        return_value=httpx.Response(200, text=OFFER)
    )

    with httpx.Client(follow_redirects=False) as client:
        results = EmploiDakarCrawler().crawl(CONFIG, client)

    assert len(results) == 2
    assert bbb.called and aaa.called and not ccc.called
    assert all(r.url.startswith("https://www.emploidakar.com/offre-demploi/") for r in results)


@respx.mock
def test_crawl_skips_an_offer_that_fails_to_fetch():
    respx.get("https://www.emploidakar.com/job_listing-sitemap.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP)
    )
    respx.get("https://www.emploidakar.com/offre-demploi/bbb/").mock(
        return_value=httpx.Response(200, text=OFFER)
    )
    respx.get("https://www.emploidakar.com/offre-demploi/aaa/").mock(
        return_value=httpx.Response(500)
    )
    with httpx.Client(follow_redirects=False) as client:
        results = EmploiDakarCrawler().crawl(CONFIG, client)
    assert len(results) == 1


@respx.mock
def test_crawl_propagates_a_sitemap_failure():
    respx.get("https://www.emploidakar.com/job_listing-sitemap.xml").mock(
        return_value=httpx.Response(503)
    )
    with httpx.Client(follow_redirects=False) as client:
        with pytest.raises(Exception):
            EmploiDakarCrawler().crawl(CONFIG, client)
```

- [ ] **Step 3: Lancer, vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/crawlers/test_emploi_dakar.py -q`
Expected: FAIL — module introuvable.

- [ ] **Step 4: Implémenter `base.py`**

`backend/app/job_search/crawlers/base.py` :

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx


@dataclass(frozen=True)
class CrawledListingData:
    url: str
    title: str
    company: str | None
    location: str | None
    snippet: str
    salary: str | None
    contract_type: str | None
    is_remote: bool
    posted_at: datetime | None


@dataclass(frozen=True)
class CrawlerConfig:
    source: str
    base_url: str
    max_offers: int
    request_delay_seconds: float
    user_agent: str


class Crawler(Protocol):
    source: str

    def crawl(
        self, config: CrawlerConfig, http_client: httpx.Client
    ) -> list[CrawledListingData]: ...
```

- [ ] **Step 5: Implémenter `emploi_dakar.py`**

`backend/app/job_search/crawlers/emploi_dakar.py` :

```python
import logging
import time
import unicodedata
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.job_search.crawlers.base import CrawledListingData, CrawlerConfig
from app.job_search.crawlers.http import CrawlFetchError, fetch_text

logger = logging.getLogger(__name__)

SITEMAP_PATH = "/job_listing-sitemap.xml"
_REMOTE_MARKERS = ("teletravail", "remote", "distanciel")


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _sitemap_entries(xml: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(xml, "html.parser")
    entries: list[tuple[str, str]] = []
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        if not loc or not loc.get_text(strip=True):
            continue
        lastmod = url_tag.find("lastmod")
        entries.append(
            (loc.get_text(strip=True), lastmod.get_text(strip=True) if lastmod else "")
        )
    return entries


def _parse_offer(html: str, url: str) -> CrawledListingData | None:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    box = soup.select_one(".single_job_listing")
    if h1 is None or box is None:
        return None

    title = h1.get_text(" ", strip=True)
    company_el = box.find(class_="company")
    location_el = box.find(class_="location")
    company = company_el.get_text(" ", strip=True) if company_el else None
    location = location_el.get_text(" ", strip=True) if location_el else None

    contract_types = [li.get_text(strip=True) for li in box.select("li.job-type")]
    contract_type = " / ".join(t for t in contract_types if t) or None

    posted_at: datetime | None = None
    time_el = box.find("time")
    if time_el and time_el.get("datetime"):
        try:
            posted_at = datetime.fromisoformat(time_el["datetime"])
        except ValueError:
            posted_at = None

    desc_el = box.find(class_="job_description")
    if desc_el:
        snippet = desc_el.get_text(" ", strip=True)[:600]
    else:
        og = soup.find("meta", property="og:description")
        snippet = (og.get("content", "") if og else "")[:600]

    haystack = _strip_accents(f"{location or ''} {title}")
    is_remote = any(marker in haystack for marker in _REMOTE_MARKERS)

    return CrawledListingData(
        url=url,
        title=title,
        company=company,
        location=location,
        snippet=snippet,
        salary=None,
        contract_type=contract_type,
        is_remote=is_remote,
        posted_at=posted_at,
    )


class EmploiDakarCrawler:
    source = "emploi_dakar"

    def crawl(
        self, config: CrawlerConfig, http_client: httpx.Client
    ) -> list[CrawledListingData]:
        sitemap_url = config.base_url.rstrip("/") + SITEMAP_PATH
        xml = fetch_text(sitemap_url, http_client)  # propagates CrawlFetchError

        entries = _sitemap_entries(xml)
        entries.sort(key=lambda e: e[1], reverse=True)  # newest lastmod first
        selected = entries[: config.max_offers]

        results: list[CrawledListingData] = []
        for offer_url, _lastmod in selected:
            time.sleep(config.request_delay_seconds)
            try:
                html = fetch_text(offer_url, http_client)
            except CrawlFetchError as exc:
                logger.warning("emploi_dakar: skipping %s (%s)", offer_url, exc)
                continue
            data = _parse_offer(html, offer_url)
            if data is not None:
                results.append(data)
        return results
```

- [ ] **Step 6: Lancer, vérifier le succès**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/crawlers/test_emploi_dakar.py -q`
Expected: PASS (5 tests). Si `test_parse_offer_extracts_core_fields` échoue sur `snippet`/`title` vide, inspecter la fixture `emploi_dakar_offer.html` réellement enregistrée et ajuster les sélecteurs dans `_parse_offer` (le site a pu changer depuis la rédaction) — puis relancer.

- [ ] **Step 7: Lint / types / commit**

```bash
cd backend && ./venv/bin/ruff check app/job_search/crawlers/ tests/job_search/crawlers/ && ./venv/bin/ruff format app/job_search/crawlers/ tests/job_search/crawlers/ && ./venv/bin/mypy app/job_search/crawlers/
git add backend/app/job_search/crawlers/base.py backend/app/job_search/crawlers/emploi_dakar.py backend/tests/job_search/crawlers/test_emploi_dakar.py backend/tests/job_search/crawlers/fixtures/
git commit -m "feat(job-search): add Emploi Dakar sitemap crawler

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 4 : `crawl_runner.py` — upsert et désactivation

**Files:**
- Create: `backend/app/job_search/crawl_runner.py`
- Create: `backend/tests/job_search/test_crawl_runner.py`

**Interfaces:**
- Consumes: `CrawledListing` (Task 1), `CrawledListingData`/`CrawlerConfig` (Task 3), `EmploiDakarCrawler` (Task 3), `get_settings`, `app.database`, `app.utils.time.utcnow`.
- Produces :
  - `ENABLED_CRAWLER_REGISTRY: dict[str, Crawler]` — `{"emploi_dakar": EmploiDakarCrawler()}`.
  - `run_crawl(db_session_factory: Callable[[], Session]) -> None` — pour chaque crawler dont la clé est dans `settings.enabled_crawlers`, dans un `try/except` isolant (log `exception`, continuer) : construit `CrawlerConfig` depuis les settings, un `httpx.Client(follow_redirects=False, headers={"User-Agent": config.user_agent}, timeout=15.0)`, appelle `crawler.crawl(...)`, puis `_apply(db, source, data_list)`.
  - `_apply(db: Session, source: str, items: list[CrawledListingData], *, deactivate_after: int, suspicious_empty_threshold: int) -> dict[str, int]` — upsert par `url` ; renvoie un compte `{"inserted", "updated", "deactivated", "skipped_deactivation"}`. Règles :
    - URL absente → INSERT, `first_seen_at = last_seen_at = utcnow()`, `missed_crawls = 0`.
    - URL présente (peu importe `source`, l'URL est globale) → UPDATE des champs de contenu, `last_seen_at = utcnow()`, `missed_crawls = 0`, `is_active = True`.
    - **Garde-fou** : si `items` est vide **et** `count(actives de cette source) > suspicious_empty_threshold` → ne rien désactiver, renvoyer `skipped_deactivation = 1`, log `warning`.
    - Sinon : pour chaque ligne active de `source` dont l'`url` n'est pas dans `items` → `missed_crawls += 1` ; si `>= deactivate_after` → `is_active = False`.
  - `db.commit()` en fin de `_apply`.

- [ ] **Step 1: Écrire le test qui échoue**

`backend/tests/job_search/test_crawl_runner.py` :

```python
from datetime import UTC, datetime

from app.job_search.crawl_runner import _apply
from app.job_search.crawlers.base import CrawledListingData
from app.models.crawled_listing import CrawledListing


def _data(url: str, title: str = "Dev") -> CrawledListingData:
    return CrawledListingData(
        url=url, title=title, company="Acme", location="Dakar", snippet="...",
        salary=None, contract_type="CDI", is_remote=False, posted_at=None,
    )


def test_apply_inserts_new_listings(db_session):
    counts = _apply(
        db_session, "emploi_dakar", [_data("https://x/1"), _data("https://x/2")],
        deactivate_after=3, suspicious_empty_threshold=5,
    )
    assert counts["inserted"] == 2
    rows = db_session.query(CrawledListing).all()
    assert {r.url for r in rows} == {"https://x/1", "https://x/2"}
    assert all(r.first_seen_at == r.last_seen_at for r in rows)


def test_apply_updates_and_resets_missed_crawls_on_reseen(db_session):
    old = datetime(2026, 1, 1)
    db_session.add(CrawledListing(
        url="https://x/1", source="emploi_dakar", title="Old",
        first_seen_at=old, last_seen_at=old, missed_crawls=2,
    ))
    db_session.commit()

    _apply(db_session, "emploi_dakar", [_data("https://x/1", title="New")],
           deactivate_after=3, suspicious_empty_threshold=5)

    row = db_session.query(CrawledListing).one()
    assert row.title == "New"
    assert row.missed_crawls == 0
    assert row.is_active is True
    assert row.last_seen_at > old
    assert row.first_seen_at == old


def test_apply_deactivates_after_threshold_absences(db_session):
    now = datetime(2026, 8, 1)
    db_session.add(CrawledListing(
        url="https://x/gone", source="emploi_dakar", title="Gone",
        first_seen_at=now, last_seen_at=now, missed_crawls=2, is_active=True,
    ))
    db_session.commit()

    _apply(db_session, "emploi_dakar", [_data("https://x/other")],
           deactivate_after=3, suspicious_empty_threshold=0)

    gone = db_session.query(CrawledListing).filter_by(url="https://x/gone").one()
    assert gone.missed_crawls == 3
    assert gone.is_active is False


def test_apply_skips_deactivation_when_crawl_suspiciously_empty(db_session):
    now = datetime(2026, 8, 1)
    for i in range(10):
        db_session.add(CrawledListing(
            url=f"https://x/{i}", source="emploi_dakar", title="t",
            first_seen_at=now, last_seen_at=now, is_active=True,
        ))
    db_session.commit()

    counts = _apply(db_session, "emploi_dakar", [],
                    deactivate_after=3, suspicious_empty_threshold=5)

    assert counts["skipped_deactivation"] == 1
    assert db_session.query(CrawledListing).filter_by(is_active=True).count() == 10
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_crawl_runner.py -q`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter `crawl_runner.py`**

`backend/app/job_search/crawl_runner.py` :

```python
import logging
from collections.abc import Callable

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.job_search.crawlers.base import Crawler, CrawledListingData, CrawlerConfig
from app.job_search.crawlers.emploi_dakar import EmploiDakarCrawler
from app.models.crawled_listing import CrawledListing
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

ENABLED_CRAWLER_REGISTRY: dict[str, Crawler] = {
    "emploi_dakar": EmploiDakarCrawler(),
}

_BASE_URLS = {
    "emploi_dakar": "https://www.emploidakar.com",
}


def _apply(
    db: Session,
    source: str,
    items: list[CrawledListingData],
    *,
    deactivate_after: int,
    suspicious_empty_threshold: int,
) -> dict[str, int]:
    counts = {"inserted": 0, "updated": 0, "deactivated": 0, "skipped_deactivation": 0}
    now = utcnow()
    seen_urls = {item.url for item in items}

    existing = {
        row.url: row
        for row in db.query(CrawledListing).filter(CrawledListing.source == source)
    }

    for item in items:
        row = existing.get(item.url)
        if row is None:
            db.add(
                CrawledListing(
                    url=item.url,
                    source=source,
                    title=item.title,
                    company=item.company,
                    location=item.location,
                    snippet=item.snippet,
                    salary=item.salary,
                    contract_type=item.contract_type,
                    is_remote=item.is_remote,
                    posted_at=item.posted_at,
                    first_seen_at=now,
                    last_seen_at=now,
                    missed_crawls=0,
                    is_active=True,
                )
            )
            counts["inserted"] += 1
        else:
            row.title = item.title
            row.company = item.company
            row.location = item.location
            row.snippet = item.snippet
            row.salary = item.salary
            row.contract_type = item.contract_type
            row.is_remote = item.is_remote
            row.posted_at = item.posted_at
            row.last_seen_at = now
            row.missed_crawls = 0
            row.is_active = True
            counts["updated"] += 1

    active_count = sum(1 for r in existing.values() if r.is_active)
    if not items and active_count > suspicious_empty_threshold:
        logger.warning(
            "%s: crawl returned 0 offers but %d active rows exist - skipping "
            "deactivation (selector likely broke)",
            source,
            active_count,
        )
        counts["skipped_deactivation"] = 1
    else:
        for url, row in existing.items():
            if url in seen_urls or not row.is_active:
                continue
            row.missed_crawls += 1
            if row.missed_crawls >= deactivate_after:
                row.is_active = False
                counts["deactivated"] += 1

    db.commit()
    return counts


def _config_for(source: str, settings) -> CrawlerConfig:
    return CrawlerConfig(
        source=source,
        base_url=_BASE_URLS[source],
        max_offers=settings.crawl_max_offers_per_site,
        request_delay_seconds=settings.crawl_request_delay_seconds,
        user_agent=(
            f"ATSDiagnosticBot/1.0 (+{settings.crawler_contact_url})"
            if settings.crawler_contact_url
            else "ATSDiagnosticBot/1.0"
        ),
    )


def run_crawl(db_session_factory: Callable[[], Session]) -> None:
    settings = get_settings()
    db = db_session_factory()
    try:
        for source in settings.enabled_crawlers:
            crawler = ENABLED_CRAWLER_REGISTRY.get(source)
            if crawler is None:
                logger.warning("unknown crawler '%s' in ENABLED_CRAWLERS", source)
                continue
            try:
                config = _config_for(source, settings)
                http_client = httpx.Client(
                    follow_redirects=False,
                    timeout=15.0,
                    headers={"User-Agent": config.user_agent},
                )
                try:
                    items = crawler.crawl(config, http_client)
                finally:
                    http_client.close()
                counts = _apply(
                    db,
                    source,
                    items,
                    deactivate_after=settings.crawl_deactivate_after,
                    suspicious_empty_threshold=settings.crawl_suspicious_empty_threshold,
                )
                logger.info("crawl %s: %s", source, counts)
            except Exception:
                logger.exception("crawl failed for source '%s'", source)
    finally:
        db.close()
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_crawl_runner.py -q`
Expected: PASS (4 tests). Le lint mypy sur `_config_for(..., settings)` non typé : annoter `settings: "Settings"` (import `from app.config import Settings` sous `TYPE_CHECKING`) ou laisser non annoté si le projet tolère (vérifier `./venv/bin/mypy app/job_search/crawl_runner.py`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/job_search/crawl_runner.py backend/tests/job_search/test_crawl_runner.py
git commit -m "feat(job-search): add crawl runner with upsert and staleness deactivation

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 5 : `CrawledListingClient` — source DB pour la recherche

**Files:**
- Create: `backend/app/job_search/crawled_listings.py`
- Create: `backend/tests/job_search/test_crawled_listings_client.py`

**Interfaces:**
- Consumes: `CrawledListing` (Task 1), `SearchCriteria`/`JobListing` (`app.job_search.schemas`), `JobSearchSourceError`, `keyword_matching` helpers, `app.database`.
- Produces :
  - `class CrawledListingClient` : `__init__(self, session_factory: Callable[[], Session] | None = None)` (défaut `app.database.SessionLocal`) ; `search(self, criteria: SearchCriteria) -> list[JobListing]`.
  - Requête : `CrawledListing.is_active.is_(True)` ; pour chaque mot du `criteria.keywords` (split sur espace, accents retirés) un `OR` de `ILIKE %mot%` sur `title` **ou** `snippet` — tous les mots doivent matcher (AND entre mots) ; si `criteria.location` → `unaccent(location) ILIKE %loc%` (SQLite n'a pas `unaccent` : filtrer en Python après la requête pour la portée de ce plan — cf. note) ; si `criteria.contract_type` → `contract_type ILIKE %ct%` ; si `criteria.remote` → `is_remote.is_(True)`. `ORDER BY COALESCE(posted_at, first_seen_at) DESC`, `LIMIT 50`.
  - Mappe chaque ligne → `JobListing(source=row.source, ats_type=None, is_remote=row.is_remote, ...)`.
  - Toute `SQLAlchemyError` → `JobSearchSourceError`.

> Note filtrage accents/lieu : pour rester simple et portable SQLite (tests) + Postgres (prod), faire le filtre mots-clés en SQL avec `ILIKE` (Postgres) / `like` insensible à la casse, **sans** `unaccent`, et appliquer le filtre `location` (accent-insensible) en Python sur le petit result-set (≤ 50 lignes après `LIMIT`… donc appliquer `location` **avant** le `LIMIT` : le faire en Python sur les lignes actives filtrées par mots-clés, puis trier et tronquer à 50). C'est acceptable au volume attendu (quelques milliers de lignes actives). Migration vers un index `tsvector` notée dans le spec si le volume l'exige.

- [ ] **Step 1: Écrire le test qui échoue**

`backend/tests/job_search/test_crawled_listings_client.py` :

```python
from datetime import datetime

from app.job_search.crawled_listings import CrawledListingClient
from app.job_search.schemas import SearchCriteria
from app.models.crawled_listing import CrawledListing


def _seed(db_session):
    rows = [
        CrawledListing(
            url="https://x/1", source="emploi_dakar",
            title="Développeur Python", snippet="Django, API REST",
            location="Dakar, Sénégal", contract_type="CDI", is_remote=False,
            first_seen_at=datetime(2026, 8, 1), last_seen_at=datetime(2026, 8, 1),
            posted_at=datetime(2026, 8, 1), is_active=True,
        ),
        CrawledListing(
            url="https://x/2", source="emploi_dakar",
            title="Comptable", snippet="Sage, fiscalité",
            location="Thiès", contract_type="CDD", is_remote=False,
            first_seen_at=datetime(2026, 8, 2), last_seen_at=datetime(2026, 8, 2),
            posted_at=datetime(2026, 8, 2), is_active=True,
        ),
        CrawledListing(
            url="https://x/3", source="emploi_dakar",
            title="Développeur backend (télétravail)", snippet="Node",
            location="Remote", contract_type="CDI", is_remote=True,
            first_seen_at=datetime(2026, 8, 3), last_seen_at=datetime(2026, 8, 3),
            posted_at=datetime(2026, 8, 3), is_active=True,
        ),
        CrawledListing(
            url="https://x/old", source="emploi_dakar",
            title="Développeur retiré", snippet="x", location="Dakar",
            is_remote=False, first_seen_at=datetime(2026, 7, 1),
            last_seen_at=datetime(2026, 7, 1), is_active=False,
        ),
    ]
    for r in rows:
        db_session.add(r)
    db_session.commit()


def test_search_matches_keyword_in_title_or_snippet(db_session):
    _seed(db_session)
    client = CrawledListingClient(session_factory=lambda: db_session)
    results = client.search(SearchCriteria(keywords="développeur"))
    urls = {r.url for r in results}
    assert urls == {"https://x/1", "https://x/3"}  # not the inactive one
    assert all(r.source == "emploi_dakar" for r in results)


def test_search_filters_by_location_accent_insensitive(db_session):
    _seed(db_session)
    client = CrawledListingClient(session_factory=lambda: db_session)
    results = client.search(
        SearchCriteria(keywords="développeur", location="senegal")
    )
    assert {r.url for r in results} == {"https://x/1"}


def test_search_remote_flag_restricts_to_remote_rows(db_session):
    _seed(db_session)
    client = CrawledListingClient(session_factory=lambda: db_session)
    results = client.search(SearchCriteria(keywords="développeur", remote=True))
    assert {r.url for r in results} == {"https://x/3"}
    assert results[0].is_remote is True


def test_search_orders_by_recency_desc(db_session):
    _seed(db_session)
    client = CrawledListingClient(session_factory=lambda: db_session)
    results = client.search(SearchCriteria(keywords="développeur"))
    assert [r.url for r in results] == ["https://x/3", "https://x/1"]
```

> Note : `JobListing` gagne `is_remote` au **Plan C**. Si le Plan C n'est pas encore fait au moment d'exécuter ce plan, retirer les assertions `.is_remote` et le kwarg `is_remote=` du mapping (le laisser à sa valeur par défaut). Vérifier `grep "is_remote" app/job_search/schemas.py` avant d'écrire le mapping.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_crawled_listings_client.py -q`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter `crawled_listings.py`**

`backend/app/job_search/crawled_listings.py` :

```python
import unicodedata
from collections.abc import Callable

from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import database
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria
from app.models.crawled_listing import CrawledListing

_RESULT_LIMIT = 50


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


class CrawledListingClient:
    """Reads crawled_listing (populated by crawl_runner) as a job-search
    source. Same SearchClient shape as the live source clients, so the
    aggregator merges/scores its results with no special-casing."""

    def __init__(self, session_factory: Callable[[], Session] | None = None):
        self._session_factory = session_factory or database.SessionLocal

    def search(self, criteria: SearchCriteria) -> list[JobListing]:
        words = [w for w in _strip_accents(criteria.keywords).split() if w]
        session = self._session_factory()
        try:
            query = session.query(CrawledListing).filter(
                CrawledListing.is_active.is_(True)
            )
            for word in words:
                like = f"%{word}%"
                query = query.filter(
                    or_(
                        func.lower(CrawledListing.title).like(like),
                        func.lower(CrawledListing.snippet).like(like),
                    )
                )
            if criteria.contract_type:
                query = query.filter(
                    func.lower(CrawledListing.contract_type).like(
                        f"%{criteria.contract_type.lower()}%"
                    )
                )
            if criteria.remote:
                query = query.filter(CrawledListing.is_remote.is_(True))

            rows = query.order_by(
                func.coalesce(
                    CrawledListing.posted_at, CrawledListing.first_seen_at
                ).desc()
            ).all()
        except SQLAlchemyError as exc:
            raise JobSearchSourceError(f"crawled_listing: {exc}") from exc
        finally:
            session.close()

        location_needle = (
            _strip_accents(criteria.location.strip())
            if (criteria.location or "").strip()
            else None
        )
        listings: list[JobListing] = []
        for row in rows:
            if location_needle is not None and location_needle not in _strip_accents(
                row.location or ""
            ):
                continue
            listings.append(
                JobListing(
                    title=row.title,
                    company=row.company or "",
                    location=row.location,
                    snippet=row.snippet,
                    url=row.url,
                    source=row.source,
                    ats_type=None,
                    salary=row.salary,
                    posted_at=row.posted_at,
                    is_remote=row.is_remote,
                )
            )
            if len(listings) >= _RESULT_LIMIT:
                break
        return listings
```

> Si `JobListing` n'a pas encore `is_remote` (Plan C non fait) : retirer la ligne `is_remote=row.is_remote,`.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_crawled_listings_client.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Lint / types / commit**

```bash
cd backend && ./venv/bin/ruff check app/job_search/crawled_listings.py tests/job_search/test_crawled_listings_client.py && ./venv/bin/ruff format app/job_search/crawled_listings.py tests/job_search/test_crawled_listings_client.py && ./venv/bin/mypy app/job_search/crawled_listings.py
git add backend/app/job_search/crawled_listings.py backend/tests/job_search/test_crawled_listings_client.py
git commit -m "feat(job-search): add CrawledListingClient DB-backed search source

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 6 : Câblage (config, deps, router, daily_search, scheduler) + vérification réelle

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/job_search/dependencies.py`
- Modify: `backend/app/routers/job_search.py`
- Modify: `backend/app/job_search/daily_search.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/routers/test_job_search.py`, `backend/tests/job_search/test_daily_search.py`
- Create: `backend/tests/job_search/test_crawl_scheduler_registration.py`

**Nouvelles clés `config.py`** (après `remoteok`… en fait après `weworkremotely_feed_urls`) :

```python
    enabled_crawlers: list[str] = ["emploi_dakar"]
    crawl_interval_hours: int = 3
    crawl_max_offers_per_site: int = 80
    crawl_request_delay_seconds: float = 1.0
    crawl_deactivate_after: int = 3
    crawl_suspicious_empty_threshold: int = 5
    crawler_contact_url: str = ""
```

**Interfaces:**
- Produces : `get_job_search_clients()` a une clé `"crawled"` → `CrawledListingClient()`. Les dicts `primary_clients` (router + daily_search) incluent `"crawled"`. `main.py` planifie `run_crawl` via APScheduler.

- [ ] **Step 1: Test de câblage qui échoue**

`backend/tests/job_search/test_crawl_scheduler_registration.py` :

```python
from app.job_search.dependencies import get_job_search_clients


def test_crawled_source_is_registered():
    get_job_search_clients.cache_clear()
    assert "crawled" in get_job_search_clients()
```

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_crawl_scheduler_registration.py -q`
Expected: FAIL — `assert 'crawled' in {...}`

- [ ] **Step 2: Config**

Ajouter les 7 clés ci-dessus à `Settings` dans `backend/app/config.py`.

- [ ] **Step 3: `dependencies.py`**

Ajouter l'import `from app.job_search.crawled_listings import CrawledListingClient` et l'entrée `"crawled": CrawledListingClient(),` au dict retourné par `get_job_search_clients()`.

- [ ] **Step 4: Lancer le test de câblage**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_crawl_scheduler_registration.py -q`
Expected: PASS

- [ ] **Step 5: Router + daily_search**

`backend/app/routers/job_search.py`, `search()` : ajouter à `primary_clients` :
```python
        "crawled": cast(SearchClient, clients["crawled"]),
```
`backend/app/job_search/daily_search.py`, `_process_saved_search()` : idem.

- [ ] **Step 6: Scheduler dans `main.py`**

Dans le `lifespan` de `backend/app/main.py`, après le job `application_reminders` :

```python
    scheduler.add_job(
        lambda: run_crawl(database.SessionLocal),
        trigger="interval",
        hours=settings.crawl_interval_hours,
        id="crawl",
    )
```

et l'import `from app.job_search.crawl_runner import run_crawl`. `settings` est déjà disponible au niveau module (`settings = get_settings()`).

- [ ] **Step 7: Réparer les fixtures de test existantes**

- `backend/tests/routers/test_job_search.py` : ajouter `"crawled": EmptyPrimaryClient(),` à `_default_clients` (base) **et** aux 2 dicts `dependency_overrides` inline (ceux qui listent `greenhouse`/`lever`).
- `backend/tests/job_search/test_daily_search.py` : ajouter `"crawled": _EmptyClient(),` à `_clients()`.

- [ ] **Step 8: Suite complète + lint + types**

Run:
```bash
cd backend && ./venv/bin/python -m pytest -q && ./venv/bin/ruff check app/ tests/ && ./venv/bin/ruff format --check app/ tests/ && ./venv/bin/mypy app/
```
Expected: PASS. Corriger les fixtures manquantes si un `KeyError: 'crawled'` apparaît.

- [ ] **Step 9: Vérification réelle (Docker + Postgres + navigateur)**

```bash
cd /home/roland/Documents/Search && docker compose up -d --build backend
docker exec search-backend-1 alembic upgrade head        # applique la migration crawled_listing
docker logs --tail 30 search-backend-1
curl -s -o /dev/null -w "docs %{http_code}\n" http://localhost:8000/docs
```

Déclencher un crawl réel manuellement (sans attendre 3h) :
```bash
docker exec search-backend-1 python -c "from app import database; from app.job_search.crawl_runner import run_crawl; run_crawl(database.SessionLocal)"
docker exec search-db-1 psql -U postgres -d ats_diagnostic -c "SELECT source, count(*), count(*) FILTER (WHERE is_active) AS active FROM crawled_listing GROUP BY source;"
```
Attendu : une ligne `emploi_dakar` avec plusieurs dizaines de lignes actives.

Puis, dans le navigateur (`claude-in-chrome`) sur `frontend-v3` (port 3002) :
1. Recherche `keywords="assistant"` ou un terme large, `location="Dakar"` → vérifier que des offres de source `emploi_dakar` apparaissent, scorées, avec le bon lieu.
2. Ouvrir une offre `emploi_dakar` dans le workspace → pas d'erreur console, pas de 500 (`docker logs`).
3. Vérifier `unavailable_sources` de la réponse `/job-search/search` : `crawled` ne doit pas y figurer.
4. Re-déclencher le crawl une 2ᵉ fois → le `SELECT` doit montrer un nombre de lignes stable (upsert, pas de doublons) et `updated` > 0 dans les logs.

- [ ] **Step 10: Commit**

```bash
git add backend/app/config.py backend/app/job_search/dependencies.py backend/app/routers/job_search.py backend/app/job_search/daily_search.py backend/app/main.py backend/tests/routers/test_job_search.py backend/tests/job_search/test_daily_search.py backend/tests/job_search/test_crawl_scheduler_registration.py
git commit -m "feat(job-search): schedule crawl and wire crawled_listing into search

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Self-Review (effectué à la rédaction)

**Couverture du spec (Famille 2, composants 1-4, 8) :**
- Composant 1 `CrawledListing` (toutes les colonnes du tableau du spec) → Task 1 ✅
- Composant 2 crawlers (`crawlers/`, un module par site, `CrawlerConfig`, fetch SSRF réutilisé, UA identifiable, délai, plafond pages, robots.txt vérifié) → Tasks 2-3 ✅ ; **Senjob et AfricWork explicitement reportés à un Plan B2** (Senjob : structure HTML à analyser ; emploisenegal.com : 403 bot-block) — conforme au spec (« un site qui bloque reste désactivé, ce n'est pas un blocage du chantier »).
- Composant 3 `crawl_runner.run_crawl` (try/except isolant par site, upsert par URL, désactivation après N, garde-fou 0-offre, log structuré, APScheduler `interval`) → Tasks 4, 6 ✅
- Composant 4 `CrawledListingClient` (même `Protocol` `SearchClient`, filtres SQL, `JobSearchSourceError`→`unavailable_sources`, pas de cas particulier dans l'agrégateur) → Tasks 5, 6 ✅
- Composant 8 config (`CRAWL_INTERVAL_HOURS`, `CRAWL_MAX_*`, `CRAWL_REQUEST_DELAY_SECONDS`, `CRAWL_DEACTIVATE_AFTER`, `ENABLED_CRAWLERS`, `CRAWLER_CONTACT_URL`) → Task 6 ✅ (`CRAWL_MAX_PAGES` du spec devient `crawl_max_offers_per_site`, sémantique adaptée au crawl sitemap→pages ; `RELIEFWEB_APPNAME` était au Plan A).
- Tests ciblés (parsers avec fixtures HTML réelles, upsert SQLite, client SQLite, vérif navigateur+Postgres du flux) → Tasks 1-6 ✅
- Pas de `BackgroundTasks`/`lock_user_for_rate_limit` → contrainte respectée, notée.

**Scan placeholders :** `<rev>` dans Task 1 est un identifiant à générer (commande fournie), pas un TODO. `settings` non typé dans `_config_for` : résolution indiquée. Aucune section vide.

**Cohérence des types :** `crawl(config: CrawlerConfig, http_client: httpx.Client) -> list[CrawledListingData]` — même signature Task 3 (déf) / Task 4 (appel). `_apply(db, source, items, *, deactivate_after, suspicious_empty_threshold) -> dict[str, int]` — mêmes kwargs Task 4 (déf) / tests. `CrawledListingClient(session_factory=...)` — même kwarg Task 5 (déf) / tests. `CrawledListing` colonnes : mêmes noms modèle (Task 1) / migration (Task 1) / `_apply` (Task 4) / client (Task 5) / tests. `source="emploi_dakar"` et clé `"crawled"` : cohérents router/deps/daily_search/tests.

**Dépendance au Plan C :** le mapping `JobListing(is_remote=...)` dans `CrawledListingClient` suppose le champ `is_remote` ajouté par le Plan C. Note explicite en Task 5 pour le retirer si le Plan C n'est pas encore exécuté. Aucune autre dépendance croisée.

## Execution Handoff

Voir fin de conversation.
