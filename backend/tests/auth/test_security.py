import jwt
import pytest

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("s3cret!")
    assert hashed != "s3cret!"
    assert verify_password("s3cret!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_hash_and_verify_password_over_72_bytes_does_not_raise():
    # bcrypt (>=4.1) raises ValueError on hash/verify for input over 72
    # bytes instead of silently truncating; hash_password/verify_password
    # must guard against that so an over-length password never crashes with
    # an unhandled 500 (this is the defense-in-depth path for /auth/login,
    # which cannot be protected by a Pydantic Field constraint since
    # OAuth2PasswordRequestForm is not a Pydantic model).
    long_password = "a" * 200
    hashed = hash_password(long_password)
    assert verify_password(long_password, hashed) is True
    assert verify_password("b" * 200, hashed) is False


def test_verify_password_over_72_bytes_against_normal_hash_does_not_raise():
    hashed = hash_password("s3cret!1")
    assert verify_password("a" * 200, hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token(subject="jane@example.com")
    assert decode_access_token(token) == "jane@example.com"


def test_decode_invalid_token_raises():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-real-token")
