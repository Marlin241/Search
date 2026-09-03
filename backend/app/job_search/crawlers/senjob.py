import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag

from app.job_search.crawlers.base import CrawledListingData, CrawlerConfig
from app.job_search.crawlers.http import CrawlFetchError, fetch_text
from app.job_search.text_utils import html_to_text

logger = logging.getLogger(__name__)

LISTING_PATH = "/offres-d-emploi.php"
_MAX_PAGES = 12
_SNIPPET_MAX = 12_000
_REMOTE_MARKERS = ("teletravail", "remote", "distanciel", "a distance")

# Offer detail pages: /sn/jobseekers/<slug>_e_<id>.html
_OFFER_HREF_RE = re.compile(r"/jobseekers/[^\"?#]+_e_\d+\.html$")
_ISO_DATE_RE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")

# Contract type is not a structured field on Senjob; infer it from the text.
# Order matters: "stage" must win over a stray "CDD" mention in the body.
_CONTRACT_RULES: tuple[tuple[str, str], ...] = (
    ("stagiaire", "Stage"),
    ("stage", "Stage"),
    ("alternance", "Alternance"),
    ("apprentissage", "Alternance"),
    ("freelance", "Freelance"),
    ("consultance", "Freelance"),
    ("interim", "Intérim"),
    ("cdd", "CDD"),
    ("cdi", "CDI"),
)


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


@dataclass(frozen=True)
class _ListingRow:
    url: str
    title: str
    location: str | None
    posted_at: datetime | None


def _row_location(tr: Tag) -> str | None:
    marker = tr.select_one(".glyphicon-map-marker")
    if marker is None or marker.parent is None:
        return None
    text = marker.parent.get_text(" ", strip=True)
    return text or None


def _row_posted_at(tr: Tag) -> datetime | None:
    match = _ISO_DATE_RE.search(tr.get_text(" ", strip=True))
    if match is None:
        return None
    try:
        return datetime.fromisoformat(match.group(1))
    except ValueError:
        return None


def _listing_rows(html: str) -> list[_ListingRow]:
    """Every offer link on a listing page, de-duplicated by URL (a handful
    of offers are repeated as sponsored rows), each paired with the title,
    location and publication date shown in its row."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[_ListingRow] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str) or not _OFFER_HREF_RE.search(href):
            continue
        if href in seen:
            continue
        seen.add(href)
        tr = anchor.find_parent("tr")
        tr = tr if isinstance(tr, Tag) else None
        rows.append(
            _ListingRow(
                url=href,
                title=anchor.get_text(" ", strip=True),
                location=_row_location(tr) if tr else None,
                posted_at=_row_posted_at(tr) if tr else None,
            )
        )
    return rows


def _infer_contract_type(haystack: str) -> str | None:
    normalized = _strip_accents(haystack)
    for needle, label in _CONTRACT_RULES:
        if needle in normalized:
            return label
    return None


def _parse_offer(html: str, row: _ListingRow) -> CrawledListingData | None:
    soup = BeautifulSoup(html, "html.parser")

    title = row.title
    title_tag = soup.find("title")
    if title_tag:
        clean = title_tag.get_text(strip=True)
        if clean:
            title = clean
    if not title:
        return None

    og = soup.find("meta", property="og:description")
    snippet = html_to_text(str(og.get("content", "")) if og else "")[:_SNIPPET_MAX]
    if not snippet:
        return None

    haystack = _strip_accents(f"{title} {row.location or ''} {snippet}")
    is_remote = any(marker in haystack for marker in _REMOTE_MARKERS)

    return CrawledListingData(
        url=row.url,
        title=title,
        company=None,
        location=row.location,
        snippet=snippet,
        salary=None,
        contract_type=_infer_contract_type(f"{title} {snippet}"),
        is_remote=is_remote,
        posted_at=row.posted_at,
    )


class SenjobCrawler:
    """Crawls senjob.com (Afrique de l'Ouest francophone job board, PHP,
    server-rendered). No search API, no sitemap, no RSS: paginate the
    listing at `/offres-d-emploi.php?page=N`, collect offer URLs (de-duped),
    then fetch each `_e_<id>.html` detail page for its full description
    (carried in the `og:description` meta tag). Stops once `max_offers`
    distinct offers are gathered or a page yields nothing new."""

    source = "senjob"

    def crawl(
        self, config: CrawlerConfig, http_client: httpx.Client
    ) -> list[CrawledListingData]:
        base_host = urlsplit(config.base_url).hostname or ""
        allowed_hosts = frozenset({base_host.lower()})
        listing_url = config.base_url.rstrip("/") + LISTING_PATH

        collected: dict[str, _ListingRow] = {}
        for page in range(1, _MAX_PAGES + 1):
            page_url = listing_url if page == 1 else f"{listing_url}?page={page}"
            if page == 1:
                html = fetch_text(page_url, http_client, allowed_hosts=allowed_hosts)
            else:
                try:
                    html = fetch_text(
                        page_url, http_client, allowed_hosts=allowed_hosts
                    )
                except CrawlFetchError as exc:
                    logger.warning(
                        "senjob: stopping pagination at %s (%s)", page_url, exc
                    )
                    break

            new_on_page = 0
            for listing_row in _listing_rows(html):
                absolute = urljoin(page_url, listing_row.url)
                if absolute in collected:
                    continue
                collected[absolute] = _ListingRow(
                    url=absolute,
                    title=listing_row.title,
                    location=listing_row.location,
                    posted_at=listing_row.posted_at,
                )
                new_on_page += 1
                if len(collected) >= config.max_offers:
                    break
            if len(collected) >= config.max_offers or new_on_page == 0:
                break

        results: list[CrawledListingData] = []
        for listing_row in list(collected.values())[: config.max_offers]:
            time.sleep(config.request_delay_seconds)
            try:
                html = fetch_text(
                    listing_row.url, http_client, allowed_hosts=allowed_hosts
                )
            except CrawlFetchError as exc:
                logger.warning("senjob: skipping %s (%s)", listing_row.url, exc)
                continue
            data = _parse_offer(html, listing_row)
            if data is not None:
                results.append(data)
        return results
