from app.models.company_ats_mapping import CompanyAtsMapping


def test_create_found_mapping(db_session):
    db_session.add(
        CompanyAtsMapping(company_name="acme", source="greenhouse", slug="acme")
    )
    db_session.commit()

    fetched = (
        db_session.query(CompanyAtsMapping)
        .filter(CompanyAtsMapping.company_name == "acme")
        .first()
    )
    assert fetched.source == "greenhouse"
    assert fetched.slug == "acme"
    assert fetched.checked_at is not None


def test_create_not_found_mapping_allows_null_source_and_slug(db_session):
    db_session.add(
        CompanyAtsMapping(company_name="obscure-corp", source=None, slug=None)
    )
    db_session.commit()

    fetched = (
        db_session.query(CompanyAtsMapping)
        .filter(CompanyAtsMapping.company_name == "obscure-corp")
        .first()
    )
    assert fetched.source is None
    assert fetched.slug is None


def test_company_name_is_unique(db_session):
    from sqlalchemy.exc import IntegrityError

    db_session.add(
        CompanyAtsMapping(company_name="acme", source="greenhouse", slug="acme")
    )
    db_session.commit()

    db_session.add(
        CompanyAtsMapping(company_name="acme", source="lever", slug="acme-2")
    )
    try:
        db_session.commit()
        assert False, "expected IntegrityError"
    except IntegrityError:
        db_session.rollback()
