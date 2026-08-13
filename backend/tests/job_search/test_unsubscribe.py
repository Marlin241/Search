import pytest

from app.job_search.unsubscribe import (
    InvalidUnsubscribeTokenError,
    create_unsubscribe_token,
    verify_unsubscribe_token,
)


def test_create_then_verify_round_trip():
    token = create_unsubscribe_token(user_id=42)
    assert verify_unsubscribe_token(token) == 42


def test_verify_rejects_a_normal_login_token():
    import jwt

    from app.config import get_settings

    settings = get_settings()
    login_token = jwt.encode(
        {"sub": "42"}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(InvalidUnsubscribeTokenError):
        verify_unsubscribe_token(login_token)


def test_verify_rejects_garbage_token():
    with pytest.raises(InvalidUnsubscribeTokenError):
        verify_unsubscribe_token("not-a-real-token")


def test_unsubscribe_token_is_rejected_by_the_login_token_decoder():
    """The real vulnerability the derived signing key prevents: leaking a
    long-lived (365 day) unsubscribe token must never grant a login
    session, even though decode_access_token performs no purpose check of
    its own."""
    from jwt import InvalidTokenError

    from app.auth.security import decode_access_token

    token = create_unsubscribe_token(user_id=42)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_login_token_is_rejected_by_verify_unsubscribe_token():
    from app.auth.security import create_access_token

    login_token = create_access_token(subject="42")
    with pytest.raises(InvalidUnsubscribeTokenError):
        verify_unsubscribe_token(login_token)
