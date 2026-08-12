from app.job_search.company_cache import get_cached_mapping, save_mapping
from app.job_search.seed_companies import cache_known_seed_mappings, get_seed_companies


def test_get_seed_companies_matches_senegal():
    assert get_seed_companies("Sénégal") != []


def test_get_seed_companies_matches_dakar_case_and_accent_insensitive():
    assert get_seed_companies("dakar") == get_seed_companies("DAKAR")
    assert get_seed_companies("Dakar, Sénégal") == get_seed_companies("dakar")


def test_get_seed_companies_returns_empty_for_unrelated_location():
    assert get_seed_companies("Paris") == []


def test_get_seed_companies_returns_empty_for_none():
    assert get_seed_companies(None) == []


def test_cache_known_seed_mappings_caches_waves_real_greenhouse_slug(db_session):
    cache_known_seed_mappings(db_session, "Dakar")

    mapping = get_cached_mapping(db_session, "Wave")
    assert mapping is not None
    assert mapping.source == "greenhouse"
    assert mapping.slug == "wavemm1"


def test_cache_known_seed_mappings_is_noop_for_unrelated_location(db_session):
    cache_known_seed_mappings(db_session, "Paris")

    assert get_cached_mapping(db_session, "Wave") is None


def test_cache_known_seed_mappings_overwrites_a_stale_mismatched_mapping(db_session):
    # Mirrors what the fragile name-guessing discovery flow produces: it
    # guesses the slug "wave" from the company name "Wave", gets a 404, and
    # caches that as "no ATS" forever — shadowing the real "wavemm1" board.
    save_mapping(db_session, "Wave", None, None)

    cache_known_seed_mappings(db_session, "Dakar")

    mapping = get_cached_mapping(db_session, "Wave")
    assert mapping.source == "greenhouse"
    assert mapping.slug == "wavemm1"


def test_cache_known_seed_mappings_leaves_an_already_correct_mapping_untouched(db_session):
    save_mapping(db_session, "Wave", "greenhouse", "wavemm1")
    original_checked_at = get_cached_mapping(db_session, "Wave").checked_at

    cache_known_seed_mappings(db_session, "Dakar")

    mapping = get_cached_mapping(db_session, "Wave")
    assert mapping.checked_at == original_checked_at
