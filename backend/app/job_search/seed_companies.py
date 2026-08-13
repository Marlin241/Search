from sqlalchemy.orm import Session

from app.job_search.company_cache import get_cached_mapping, save_mapping
from app.job_search.discovery import normalize_company_name
from app.utils.time import utcnow

_SENEGAL_LOCATION_KEYWORDS = ("senegal", "dakar")

# Best-effort candidates: probed via the normal guess-a-slug-from-the-name
# discovery flow, so only companies whose ATS slug happens to match their
# name will actually be found this way. Most West African startups don't
# use Greenhouse/Lever at all (Djamo uses Breezy HR, PayDunya has no ATS),
# so this alone rarely surfaces anything — kept in case any of them adopt
# one of these ATS later.
_SENEGAL_SEED_COMPANIES = [
    "Wave",
    "PayDunya",
    "InTouch",
    "Djamo",
    "Julaya",
    "Gozem",
]

# Verified by hand against the live Greenhouse/Lever APIs: real (source, slug)
# pairs for seed companies whose actual board slug doesn't match what
# generate_slug_candidates() would guess from the name (e.g. Wave's board is
# "wavemm1", not "wave"), so name-based guessing alone would never find them.
_KNOWN_SEED_ATS_MAPPINGS: dict[str, tuple[str, str]] = {
    "wave": ("greenhouse", "wavemm1"),
}


def get_seed_companies(location: str | None) -> list[str]:
    """Companies to probe for Greenhouse/Lever boards even when the primary
    sources (France Travail, Adzuna) return no results for this location,
    since both are France-scoped and never surface non-French companies."""
    if not location:
        return []
    normalized = normalize_company_name(location)
    if any(keyword in normalized for keyword in _SENEGAL_LOCATION_KEYWORDS):
        return list(_SENEGAL_SEED_COMPANIES)
    return []


def cache_known_seed_mappings(db: Session, location: str | None) -> None:
    """Pre-populate the ATS cache with verified seed mappings so they're
    found on the very first search instead of depending on the fragile
    name-guessing discovery flow to land on the right slug.

    Overwrites any existing cache entry that disagrees with the verified
    mapping: the regular discovery flow guesses a company's slug from its
    name and caches the (possibly wrong, e.g. a 404 "no ATS") result
    permanently, which would otherwise shadow the correct mapping forever."""
    for company_name in get_seed_companies(location):
        known = _KNOWN_SEED_ATS_MAPPINGS.get(normalize_company_name(company_name))
        if known is None:
            continue
        mapping = get_cached_mapping(db, company_name)
        if mapping is None:
            save_mapping(db, company_name, known[0], known[1])
        elif (mapping.source, mapping.slug) != known:
            mapping.source, mapping.slug = known
            mapping.checked_at = utcnow()
            db.commit()
