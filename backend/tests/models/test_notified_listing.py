import pytest
from sqlalchemy.exc import IntegrityError

from app.models.notified_listing import NotifiedListing
from app.models.user import User


def test_create_notified_listing(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(
        NotifiedListing(user_id=user.id, offer_url="https://example.com/job/1")
    )
    db_session.commit()

    fetched = (
        db_session.query(NotifiedListing)
        .filter(NotifiedListing.user_id == user.id)
        .first()
    )
    assert fetched.offer_url == "https://example.com/job/1"
    assert fetched.notified_at is not None


def test_notified_listing_unique_per_user_and_url(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(
        NotifiedListing(user_id=user.id, offer_url="https://example.com/job/1")
    )
    db_session.commit()

    db_session.add(
        NotifiedListing(user_id=user.id, offer_url="https://example.com/job/1")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
