from datetime import timedelta

from app.models.invite_code import InviteCode
from app.utils.time import utcnow
from scripts.invites import generate_codes, list_codes, revoke_code


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


def test_generate_codes_creates_unique_unused_codes(db_session):
    codes = generate_codes(db_session, count=3, note="batch 1")
    assert len(codes) == 3 == len(set(codes))
    rows = list_codes(db_session)
    assert {r.code for r in rows} == set(codes)
    assert all(r.used_at is None and r.note == "batch 1" for r in rows)


def test_revoke_unused_code_succeeds_used_code_fails(db_session):
    (code,) = generate_codes(db_session, count=1, note=None)
    assert revoke_code(db_session, code) is True
    assert revoke_code(db_session, "nope") is False
