from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchClient, SearchCriteria

# Substrings that mark a listing as remote-friendly, matched
# case-insensitively against the listing's location and snippet. None of the
# four source APIs expose a clean boolean remote flag on their listing
# objects, so this text heuristic is the only source-agnostic option.
REMOTE_INDICATORS = ("remote", "télétravail", "distanciel")


def _matches_any(text_fragments: list[str | None], needles: tuple[str, ...] | list[str]) -> bool:
    haystack = " ".join(fragment for fragment in text_fragments if fragment).lower()
    return any(needle.lower() in haystack for needle in needles if needle)


def _passes_filters(listing: JobListing, criteria: SearchCriteria) -> bool:
    if criteria.exclude_keywords and _matches_any(
        [listing.title, listing.snippet], criteria.exclude_keywords
    ):
        return False
    if criteria.remote and not _matches_any([listing.location, listing.snippet], REMOTE_INDICATORS):
        return False
    return True


def search_jobs(criteria: SearchCriteria, clients: dict[str, SearchClient]) -> tuple[list[JobListing], list[str]]:
    listings: list[JobListing] = []
    unavailable_sources: list[str] = []
    for source_name, source_client in clients.items():
        try:
            listings.extend(source_client.search(criteria))
        except JobSearchSourceError:
            unavailable_sources.append(source_name)

    # `remote` and `exclude_keywords` are applied here, once, on the merged
    # result set rather than inside each of the four source clients: both
    # filters are purely textual and source-agnostic, so duplicating them
    # per client would be four chances to drift out of sync, and none of the
    # upstream APIs offers an equivalent server-side filter we could push
    # down anyway.
    return [listing for listing in listings if _passes_filters(listing, criteria)], unavailable_sources
