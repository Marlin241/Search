from app.job_search.errors import JobSearchSourceError
from app.job_search.remote_signals import is_remote_from_text
from app.job_search.schemas import JobListing, SearchClient, SearchCriteria

# Contract types with no reliable server-side filter on any source: France
# Travail's typeContrat referential doesn't have codes for them (see
# france_travail.py), and Greenhouse/Lever/La Bonne Alternance don't expose a
# contract-type filter at all, so an "Alternance" search would otherwise
# return every contract type unfiltered - including plain CDI offers.
# "cdi"/"cdd"/"interim" aren't listed here because France Travail already
# filters those server-side; re-filtering them against the listing's title
# and 500-char snippet would risk dropping genuine matches that just don't
# happen to say "CDI" in that excerpt.
TEXT_ONLY_CONTRACT_TYPE_INDICATORS: dict[str, tuple[str, ...]] = {
    "alternance": ("alternance", "apprenti", "professionnalisation"),
    "stage": ("stage", "stagiaire"),
    "freelance": ("freelance", "indépendant", "independant", "auto-entrepreneur"),
}


def _matches_any(
    text_fragments: list[str | None], needles: tuple[str, ...] | list[str]
) -> bool:
    haystack = " ".join(fragment for fragment in text_fragments if fragment).lower()
    return any(needle.lower() in haystack for needle in needles if needle)


def _passes_filters(listing: JobListing, criteria: SearchCriteria) -> bool:
    if criteria.exclude_keywords and _matches_any(
        [listing.title, listing.snippet], criteria.exclude_keywords
    ):
        return False
    if criteria.contract_type:
        indicators = TEXT_ONLY_CONTRACT_TYPE_INDICATORS.get(
            criteria.contract_type.strip().lower()
        )
        if indicators and not _matches_any(
            [listing.title, listing.snippet], indicators
        ):
            return False
    return not (criteria.remote and not listing.is_remote)


def finalize_and_filter(
    listings: list[JobListing],
    criteria: SearchCriteria,
    *,
    seen_urls: set[str] | None = None,
) -> list[JobListing]:
    """Finalize `is_remote` (source value OR text heuristic) and apply the
    post-merge filters (`remote` / `exclude_keywords` / contract-type),
    deduplicating by URL. These filters are purely textual and
    source-agnostic, so they run once here rather than inside each source
    client. `seen_urls` lets a second listing set (the Greenhouse/Lever
    discovery path, which never goes through search_jobs) be merged without
    re-emitting a URL already returned by the primary sources; it is
    mutated in place with every URL kept.
    """
    if seen_urls is None:
        seen_urls = set()
    kept: list[JobListing] = []
    for listing in listings:
        if listing.url in seen_urls:
            continue
        seen_urls.add(listing.url)
        listing.is_remote = listing.is_remote or is_remote_from_text(
            listing.location, listing.snippet
        )
        if _passes_filters(listing, criteria):
            kept.append(listing)
    return kept


def search_jobs(
    criteria: SearchCriteria, clients: dict[str, SearchClient]
) -> tuple[list[JobListing], list[str]]:
    listings: list[JobListing] = []
    unavailable_sources: list[str] = []
    for source_name, source_client in clients.items():
        try:
            listings.extend(source_client.search(criteria))
        except JobSearchSourceError:
            unavailable_sources.append(source_name)

    return finalize_and_filter(listings, criteria), unavailable_sources
