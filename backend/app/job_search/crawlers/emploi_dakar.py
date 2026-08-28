import logging
import re
import time
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from app.job_search.crawlers.base import CrawledListingData, CrawlerConfig
from app.job_search.crawlers.http import CrawlFetchError, fetch_text

logger = logging.getLogger(__name__)

SITEMAP_PATH = "/job_listing-sitemap.xml"
_REMOTE_MARKERS = ("teletravail", "remote", "distanciel")
_SNIPPET_MAX = 600

# A sitemap <urlset> is flat: one <url> block per entry, each with a <loc>
# and (usually) a <lastmod>. Extracted with regex rather than an XML parser
# on purpose - the stdlib XML parsers are vulnerable to entity-expansion
# ("billion laughs") attacks and defusedxml is not a project dependency,
# whereas this shape needs nothing more than substring matching.
_URL_BLOCK_RE = re.compile(r"<url\b[^>]*>(.*?)</url>", re.DOTALL | re.IGNORECASE)
_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.DOTALL | re.IGNORECASE)
_LASTMOD_RE = re.compile(r"<lastmod>\s*(.*?)\s*</lastmod>", re.DOTALL | re.IGNORECASE)


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _sitemap_entries(xml: str) -> list[tuple[str, str]]:
    """Return (loc, lastmod) pairs from a <urlset> sitemap. lastmod is ""
    when the entry omits it."""
    entries: list[tuple[str, str]] = []
    for block in _URL_BLOCK_RE.findall(xml):
        loc_match = _LOC_RE.search(block)
        if loc_match is None or not loc_match.group(1).strip():
            continue
        lastmod_match = _LASTMOD_RE.search(block)
        lastmod = lastmod_match.group(1).strip() if lastmod_match else ""
        entries.append((loc_match.group(1).strip(), lastmod))
    return entries


def _parse_offer(html: str, url: str) -> CrawledListingData | None:
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one(".single_job_listing")
    h1 = soup.find("h1")
    if box is None or h1 is None:
        return None

    title = h1.get_text(" ", strip=True)
    company_el = box.find(class_="company")
    location_el = box.find(class_="location")
    company = None
    if company_el:
        # `.company` can wrap a logo <img>, a <strong> with the name, and a
        # "Site web" link. The <strong> is the clean name when present.
        strong = company_el.find("strong")
        company = (strong or company_el).get_text(" ", strip=True) or None
    location = location_el.get_text(" ", strip=True) if location_el else None

    contract_types = [li.get_text(strip=True) for li in box.select("li.job-type")]
    contract_type = " / ".join(t for t in contract_types if t) or None

    posted_at: datetime | None = None
    time_el = box.find("time")
    datetime_attr = str(time_el.get("datetime", "")) if time_el else ""
    if datetime_attr:
        try:
            posted_at = datetime.fromisoformat(datetime_attr)
        except ValueError:
            posted_at = None

    desc_el = box.find(class_="job_description")
    if desc_el:
        snippet = desc_el.get_text(" ", strip=True)[:_SNIPPET_MAX]
    else:
        og = soup.find("meta", property="og:description")
        snippet = (str(og.get("content", "")) if og else "")[:_SNIPPET_MAX]

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
    """Crawls emploidakar.com (WordPress + WP Job Manager). The site exposes
    no search API, but its Yoast sitemap `job_listing-sitemap.xml` lists
    every offer URL with a `lastmod`; each offer page is static HTML with a
    stable `.single_job_listing` block. We take the `max_offers` most
    recently modified entries per run."""

    source = "emploi_dakar"

    def crawl(
        self, config: CrawlerConfig, http_client: httpx.Client
    ) -> list[CrawledListingData]:
        base_host = urlsplit(config.base_url).hostname or ""
        allowed_hosts = frozenset({base_host.lower()})
        sitemap_url = config.base_url.rstrip("/") + SITEMAP_PATH
        xml = fetch_text(
            sitemap_url, http_client, allowed_hosts=allowed_hosts
        )  # propagates CrawlFetchError

        entries = _sitemap_entries(xml)
        entries.sort(key=lambda entry: entry[1], reverse=True)  # newest lastmod first
        selected = entries[: config.max_offers]

        results: list[CrawledListingData] = []
        for offer_url, _lastmod in selected:
            time.sleep(config.request_delay_seconds)
            try:
                html = fetch_text(offer_url, http_client, allowed_hosts=allowed_hosts)
            except CrawlFetchError as exc:
                logger.warning("emploi_dakar: skipping %s (%s)", offer_url, exc)
                continue
            data = _parse_offer(html, offer_url)
            if data is not None:
                results.append(data)
        return results
