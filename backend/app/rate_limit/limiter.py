from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.diagnostic import Diagnostic

MAX_DIAGNOSTICS_PER_HOUR = 10


class RateLimitExceeded(Exception):
    pass


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
