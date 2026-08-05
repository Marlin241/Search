from datetime import datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings


_BCRYPT_MAX_BYTES = 72


def _bcrypt_safe_bytes(password: str) -> bytes:
    """Encode and truncate to bcrypt's 72-byte limit.

    bcrypt (>=4.1) raises ValueError instead of silently truncating
    over-length input, so this guards hash/verify calls against both
    over-length new passwords and over-length login attempts.
    """
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_safe_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_bcrypt_safe_bytes(password), hashed_password.encode("utf-8"))


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return payload["sub"]
