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
