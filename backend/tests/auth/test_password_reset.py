from datetime import timedelta

from app.auth.password_reset import consume_reset_token, create_reset_token
from app.auth.security import verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.utils.time import utcnow


def _user(db):
    u = User(email="u@e.com", hashed_password="x")
    db.add(u)
    db.commit()
    return u


def test_create_then_consume_sets_new_password(db_session):
    u = _user(db_session)
    token = create_reset_token(db_session, u)
    assert consume_reset_token(db_session, token, "newpass12") is True
    db_session.refresh(u)
    assert verify_password("newpass12", u.hashed_password)


def test_token_is_single_use(db_session):
    u = _user(db_session)
    token = create_reset_token(db_session, u)
    consume_reset_token(db_session, token, "newpass12")
    assert consume_reset_token(db_session, token, "another12") is False


def test_expired_token_rejected(db_session):
    u = _user(db_session)
    token = create_reset_token(db_session, u)
    row = db_session.query(PasswordResetToken).filter_by(user_id=u.id).one()
    row.expires_at = utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert consume_reset_token(db_session, token, "newpass12") is False


def test_creating_a_second_token_invalidates_the_first(db_session):
    u = _user(db_session)
    t1 = create_reset_token(db_session, u)
    create_reset_token(db_session, u)
    assert consume_reset_token(db_session, t1, "newpass12") is False
