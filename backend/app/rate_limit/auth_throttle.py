from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth_attempt import AuthAttempt
from app.utils.time import utcnow

_LIMITS: dict[str, tuple[int, timedelta]] = {
    "login": (8, timedelta(minutes=15)),
    "register": (5, timedelta(minutes=60)),
    "forgot_password": (5, timedelta(minutes=60)),
    "access_request": (5, timedelta(minutes=60)),
}


class AuthThrottleExceeded(Exception):
    pass


def record_auth_attempt(db: Session, *, action: str, identifier: str) -> None:
    db.add(AuthAttempt(action=action, identifier=identifier))
    db.commit()


def check_auth_throttle(db: Session, *, action: str, identifier: str) -> None:
    max_count, window = _LIMITS[action]
    since = utcnow() - window
    count = db.scalar(
        select(func.count())
        .select_from(AuthAttempt)
        .where(
            AuthAttempt.action == action,
            AuthAttempt.identifier == identifier,
            AuthAttempt.created_at >= since,
        )
    )
    if count is not None and count >= max_count:
        raise AuthThrottleExceeded(
            "Trop de tentatives. Réessaie dans quelques minutes."
        )


def clear_auth_attempts(db: Session, *, action: str, identifier: str) -> None:
    db.query(AuthAttempt).filter_by(action=action, identifier=identifier).delete()
    db.commit()
