from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invite_code import InviteCode
from app.utils.time import utcnow


class InviteCodeError(Exception):
    """Raised when an invite code is unknown, already used, or expired."""


def redeem_invite_code(db: Session, code: str) -> InviteCode:
    """Look up an invite code, taking a row lock (non-SQLite) so two
    concurrent registrations can't consume the same code. Does NOT commit -
    the caller stamps used_by_user_id / used_at and commits."""
    query = select(InviteCode).where(InviteCode.code == code)
    if db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    row = db.execute(query).scalar_one_or_none()
    if row is None:
        raise InviteCodeError("Code d'invitation invalide.")
    if row.used_at is not None:
        raise InviteCodeError("Ce code d'invitation a déjà été utilisé.")
    if row.expires_at is not None and row.expires_at < utcnow():
        raise InviteCodeError("Ce code d'invitation a expiré.")
    return row
