from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.diagnostic import Diagnostic
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.user import User

MAX_DIAGNOSTICS_PER_HOUR = 10
MAX_PERSONALIZATIONS_PER_HOUR = 10


class RateLimitExceeded(Exception):
    pass


def lock_user_for_rate_limit(db: Session, user_id: int) -> None:
    """Take a row lock on the user's own User row for the rest of the request.

    This serializes diagnostic creation per-user so the rate-limit check and
    the resulting insert are effectively atomic with respect to other
    concurrent requests from the same user, closing a TOCTOU race where N
    concurrent requests could all pass `check_rate_limit` before any of
    their Diagnostic rows exist.

    PostgreSQL supports `SELECT ... FOR UPDATE` row-level locking; SQLite
    (used in this project's test suite) does not support meaningful
    row-level locking, so on SQLite this is a no-op. That's safe because the
    test suite never issues concurrent requests against the same SQLite
    connection/session, and production runs on PostgreSQL, where the lock
    genuinely applies.
    """
    query = select(User.id).where(User.id == user_id)
    if db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    db.execute(query)


def check_rate_limit(db: Session, user_id: int) -> None:
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count()).select_from(Diagnostic).where(
            Diagnostic.user_id == user_id,
            Diagnostic.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_DIAGNOSTICS_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_DIAGNOSTICS_PER_HOUR} diagnostics par heure atteinte. Réessaie plus tard."
        )


def check_personalization_rate_limit(db: Session, user_id: int) -> None:
    """Counts CV and lettre generations combined, over the last hour.

    Backed by PersonalizationRequestLog rather than PersonalizedDocument
    because the latter is upserted (one row per diagnostic+kind, overwritten
    on regeneration) and would not reflect how many generations actually
    happened - repeated regenerations of the same document would only ever
    count as one row.
    """
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count()).select_from(PersonalizationRequestLog).where(
            PersonalizationRequestLog.user_id == user_id,
            PersonalizationRequestLog.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_PERSONALIZATIONS_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_PERSONALIZATIONS_PER_HOUR} générations par heure atteinte. Réessaie plus tard."
        )
