from datetime import timedelta

from app.models.invite_code import InviteCode
from app.utils.time import utcnow


def test_invite_code_row_roundtrips(db_session):
    code = InviteCode(
        code="abc123", note="pour Awa", expires_at=utcnow() + timedelta(days=30)
    )
    db_session.add(code)
    db_session.commit()
    fetched = db_session.query(InviteCode).filter_by(code="abc123").one()
    assert fetched.used_by_user_id is None
    assert fetched.used_at is None
    assert fetched.note == "pour Awa"
