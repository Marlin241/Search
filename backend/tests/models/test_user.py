from app.models.user import User


def test_create_and_query_user(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    fetched = db_session.query(User).filter(User.email == "jane@example.com").first()
    assert fetched is not None
    assert fetched.hashed_password == "hashed"
    assert fetched.created_at is not None


def test_email_must_be_unique(db_session):
    db_session.add(User(email="dup@example.com", hashed_password="a"))
    db_session.commit()
    db_session.add(User(email="dup@example.com", hashed_password="b"))

    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db_session.commit()
