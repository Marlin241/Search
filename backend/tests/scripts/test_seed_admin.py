import pytest

from app.auth.security import hash_password, verify_password
from app.models.user import User
from scripts.seed_admin import upsert_admin


def _existing(db, email, *, is_admin=False, password="old-pass1"):
    row = User(email=email, hashed_password=hash_password(password), is_admin=is_admin)
    db.add(row)
    db.commit()
    return row


def test_creates_missing_account_as_admin(db_session):
    msg = upsert_admin(db_session, "founder@example.com", "s3cret!1")
    user = db_session.query(User).filter_by(email="founder@example.com").one()
    assert user.is_admin
    assert verify_password("s3cret!1", user.hashed_password)
    assert user.consent_version is not None
    assert "créé" in msg


def test_creating_requires_a_password(db_session):
    with pytest.raises(ValueError):
        upsert_admin(db_session, "founder@example.com", None)
    with pytest.raises(ValueError):
        upsert_admin(db_session, "founder@example.com", "short")


def test_promotes_existing_account_without_touching_password(db_session):
    _existing(db_session, "founder@example.com", password="keep-me-1")
    upsert_admin(db_session, "founder@example.com", None)
    user = db_session.query(User).filter_by(email="founder@example.com").one()
    assert user.is_admin
    assert verify_password("keep-me-1", user.hashed_password)


def test_resets_password_only_when_one_is_given(db_session):
    _existing(db_session, "founder@example.com", is_admin=True, password="old-pass1")
    upsert_admin(db_session, "founder@example.com", "new-pass1")
    user = db_session.query(User).filter_by(email="founder@example.com").one()
    assert verify_password("new-pass1", user.hashed_password)


def test_email_is_normalized(db_session):
    upsert_admin(db_session, "  Founder@Example.com  ", "s3cret!1")
    assert db_session.query(User).filter_by(email="founder@example.com").one()
