import logging
import re
import time
import unicodedata
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.job_search.crawlers.base import CrawledListingData, CrawlerConfig
from app.job_search.crawlers.http import CrawlFetchError, fetch_text

logger = logging.getLogger(__name__)

LISTING_PATH = "/page/all"
_SNIPPET_MAX = 12_000
_REMOTE_MARKERS = ("teletravail", "remote", "distanciel", "a distance")

# Offer detail pages: /offre-<id>-<slug>.html
_OFFER_HREF_RE = re.compile(r"/offre-\d+-[^\"?#]+\.html$")

# The offer's whole "fiche" is rendered as plain text inside .post-body. Its
# og: tags are boilerplate placeholders ("Lorem ipsum...") - useless. The
# body opens with: "<company> <badge> Postuler <TITLE> Secteur <x> Lieu <y>
# Niveau <z> Date limite <d> Publiée le <d> ... Détails de l'offre <body>".
_HEADER_RE = re.compile(
    r"^(?P<company>.+?)\s+"
    r"(?P<badge>Emploi|Stage|Alternance|Consultance|Bénévolat|Volontariat)\s+"
    r"Postuler\s+",
    re.IGNORECASE,
)
_LIEU_RE = re.compile(r"Lieu\s+(.+?)\s+(?:Niveau|Date limite|Publiée|Secteur)")
_PUBLIEE_RE = re.compile(r"Publiée le\s+(\d{2})/(\d{2})/(\d{4})")
_CONTRACT_RE = re.compile(
    r"TYPE DE CONTRAT\s*:?\s*(CDI|CDD|Stage|Freelance|Int[eé]rim|Alternance)",
    re.IGNORECASE,
)
_BADGE_CONTRACT = {"stage": "Stage", "alternance": "Alternance"}
_DETAILS_MARKER = "Détails de l'offre"


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _clean_title(raw: str) -> str:
    # "<TITLE> - Offres d'emploi - Educarriere.ci | Emploi - Educarriere.ci"
    return re.split(r"\s+-\s+Offres|\s+\|\s+", raw, maxsplit=1)[0].strip()


def _listing_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str) or not _OFFER_HREF_RE.search(href):
            continue
        if href in seen:
            continue
        seen.add(href)
        urls.append(href)
    return urls


def _parse_offer(html: str, url: str) -> CrawledListingData | None:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = _clean_title(title_tag.get_text(strip=True)) if title_tag else ""
    if not title:
        return None

    body = soup.select_one("div.post-body.post-content")
    if body is None:
        return None
    for style in body.find_all("style"):
        style.decompose()
    text = re.sub(r"\s+", " ", body.get_text(" ", strip=True))
    if not text:
        return None

    header = _HEADER_RE.match(text)
    company = header.group("company").strip() if header else None
    badge = header.group("badge").lower() if header else ""

    contract_type: str | None = None
    contract_match = _CONTRACT_RE.search(text)
    if contract_match:
        raw = contract_match.group(1).lower()
        contract_type = {"interim": "Intérim", "intérim": "Intérim"}.get(
            raw, raw.upper() if len(raw) <= 3 else raw.capitalize()
        )
    elif badge in _BADGE_CONTRACT:
        contract_type = _BADGE_CONTRACT[badge]

    lieu_match = _LIEU_RE.search(text)
    location = lieu_match.group(1).strip() if lieu_match else None

    posted_at: datetime | None = None
    publiee_match = _PUBLIEE_RE.search(text)
    if publiee_match:
        day, month, year = publiee_match.groups()
        try:
            posted_at = datetime.fromisoformat(f"{year}-{month}-{day}")
        except ValueError:
            posted_at = None

    marker = text.find(_DETAILS_MARKER)
    snippet_source = text[marker + len(_DETAILS_MARKER) :] if marker != -1 else text
    snippet = snippet_source.strip()[:_SNIPPET_MAX]

    haystack = _strip_accents(f"{title} {location or ''} {snippet}")
    is_remote = any(marker_ in haystack for marker_ in _REMOTE_MARKERS)

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


class EducarriereCrawler:
    """Crawls emploi.educarriere.ci (Côte d'Ivoire job board, server-rendered).
    No search API, no sitemap, no RSS, and pagination is broken (`/page/all`
    always returns the same page), so this reads that single listing page for
    the ~30 current offer URLs and fetches each `/offre-<id>-<slug>.html`
    detail page. The detail page's og: tags are placeholder boilerplate; the
    real fiche is plain text inside `div.post-body` and is parsed by labelled
    markers (Secteur / Lieu / Publiée le / TYPE DE CONTRAT)."""

    source = "educarriere_ci"

    def crawl(
        self, config: CrawlerConfig, http_client: httpx.Client
    ) -> list[CrawledListingData]:
        base_host = urlsplit(config.base_url).hostname or ""
        allowed_hosts = frozenset({base_host.lower()})
        listing_url = config.base_url.rstrip("/") + LISTING_PATH

        html = fetch_text(listing_url, http_client, allowed_hosts=allowed_hosts)
        offer_urls = [urljoin(listing_url, href) for href in _listing_urls(html)][
            : config.max_offers
        ]

        results: list[CrawledListingData] = []
        for offer_url in offer_urls:
            time.sleep(config.request_delay_seconds)
            try:
                offer_html = fetch_text(
                    offer_url, http_client, allowed_hosts=allowed_hosts
                )
            except CrawlFetchError as exc:
                logger.warning("educarriere: skipping %s (%s)", offer_url, exc)
                continue
            data = _parse_offer(offer_html, offer_url)
            if data is not None:
                results.append(data)
        return results
