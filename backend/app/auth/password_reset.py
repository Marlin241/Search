import hashlib
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.config import get_settings
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.utils.time import utcnow


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _invalidate_active(db: Session, user_id: int) -> None:
    now = utcnow()
    for row in db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.used_at.is_(None),
    ):
        row.used_at = now


def create_reset_token(db: Session, user: User) -> str:
    """Invalidate any active token for the user, mint a new one, return the
    plaintext (never stored)."""
    _invalidate_active(db, user.id)
    token = secrets.token_urlsafe(32)
    ttl = get_settings().password_reset_token_ttl_minutes
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash(token),
            expires_at=utcnow() + timedelta(minutes=ttl),
        )
    )
    db.commit()
    return token


def consume_reset_token(db: Session, token: str, new_password: str) -> bool:
    row = db.query(PasswordResetToken).filter_by(token_hash=_hash(token)).one_or_none()
    if row is None or row.used_at is not None or row.expires_at < utcnow():
        return False
    user = db.get(User, row.user_id)
    if user is None:
        return False
    user.hashed_password = hash_password(new_password)
    row.used_at = utcnow()
    _invalidate_active(db, user.id)
    db.commit()
    return True
