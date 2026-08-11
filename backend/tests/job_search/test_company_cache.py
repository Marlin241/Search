from app.job_search.company_cache import get_cached_mapping, save_mapping
from app.models.company_ats_mapping import CompanyAtsMapping


def test_get_cached_mapping_returns_none_when_absent(db_session):
    assert get_cached_mapping(db_session, "Acme") is None


def test_save_then_get_cached_mapping_returns_found_result(db_session):
    save_mapping(db_session, "Acme", "greenhouse", "acme")

    mapping = get_cached_mapping(db_session, "Acme")

    assert mapping is not None
    assert mapping.source == "greenhouse"
    assert mapping.slug == "acme"


def test_save_then_get_cached_mapping_returns_not_found_result(db_session):
    save_mapping(db_session, "Obscure Corp", None, None)

    mapping = get_cached_mapping(db_session, "Obscure Corp")

    assert mapping is not None
    assert mapping.source is None
    assert mapping.slug is None


def test_get_cached_mapping_matches_regardless_of_casing_and_accents(db_session):
    save_mapping(db_session, "L'Oréal", "lever", "loreal")

    assert get_cached_mapping(db_session, "loreal") is not None
    assert get_cached_mapping(db_session, "LOREAL") is not None


def test_save_mapping_ignores_duplicate_insert_for_same_normalized_name(db_session):
    save_mapping(db_session, "Acme", "greenhouse", "acme")
    save_mapping(db_session, "ACME", "lever", "acme-2")  # same normalized name, should not crash or overwrite

    rows = db_session.query(CompanyAtsMapping).filter(CompanyAtsMapping.company_name == "acme").all()
    assert len(rows) == 1
    assert rows[0].source == "greenhouse"  # first write wins
