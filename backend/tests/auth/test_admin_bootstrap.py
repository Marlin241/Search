from app.auth.admin_bootstrap import promote_configured_admins
from app.auth.security import hash_password
from app.models.user import User


def _user(db, email, *, is_admin=False):
    row = User(
        email=email, hashed_password=hash_password("s3cret!1"), is_admin=is_admin
    )
    db.add(row)
    db.commit()
    return row


def test_promotes_matching_existing_account(db_session):
    _user(db_session, "founder@example.com")
    promoted = promote_configured_admins(db_session, {"founder@example.com"})
    assert promoted == ["founder@example.com"]
    assert db_session.query(User).filter_by(email="founder@example.com").one().is_admin


def test_match_is_case_insensitive(db_session):
    _user(db_session, "Founder@Example.com")
    promote_configured_admins(db_session, {"founder@example.com"})
    assert db_session.query(User).filter_by(email="Founder@Example.com").one().is_admin


def test_skips_accounts_not_listed(db_session):
    _user(db_session, "someone@example.com")
    assert promote_configured_admins(db_session, {"founder@example.com"}) == []
    assert (
        not db_session.query(User).filter_by(email="someone@example.com").one().is_admin
    )


def test_never_demotes(db_session):
    _user(db_session, "ex-admin@example.com", is_admin=True)
    # ex-admin is no longer in the configured set -> stays admin.
    assert promote_configured_admins(db_session, {"founder@example.com"}) == []
    assert db_session.query(User).filter_by(email="ex-admin@example.com").one().is_admin


def test_empty_set_is_a_noop(db_session):
    _user(db_session, "founder@example.com")
    assert promote_configured_admins(db_session, set()) == []


def test_already_admin_not_reported(db_session):
    _user(db_session, "founder@example.com", is_admin=True)
    assert promote_configured_admins(db_session, {"founder@example.com"}) == []
