import time

import jwt
import pytest

from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("s3cret!")
    assert hashed != "s3cret!"
    assert verify_password("s3cret!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token(subject="jane@example.com")
    assert decode_access_token(token) == "jane@example.com"


def test_decode_invalid_token_raises():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-real-token")
