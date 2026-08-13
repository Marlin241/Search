import pytest
from sqlalchemy.exc import IntegrityError

from app.models.saved_search import SavedSearch
from app.models.user import User


def test_create_saved_search_with_defaults(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(SavedSearch(user_id=user.id, keywords="python backend"))
    db_session.commit()

    fetched = (
        db_session.query(SavedSearch).filter(SavedSearch.user_id == user.id).first()
    )
    assert fetched.keywords == "python backend"
    assert fetched.location is None
    assert fetched.exclude_keywords == []
    assert fetched.timezone == "Europe/Paris"
    assert fetched.enabled is True
    assert fetched.created_at is not None


def test_saved_search_user_id_is_unique(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(SavedSearch(user_id=user.id, keywords="a"))
    db_session.commit()

    db_session.add(SavedSearch(user_id=user.id, keywords="b"))
    with pytest.raises(IntegrityError):
        db_session.commit()
