from datetime import timedelta

import pytest

from app.models.llm_call_log import LlmCallLog
from app.models.user import User
from app.rate_limit.llm_quota import (
    QuotaExceeded,
    enforce_monthly_quota,
    monthly_limit,
    record_llm_call,
    usage_summary,
    used_this_month,
)
from app.utils.time import utcnow


def _user(db, **kw):
    u = User(email="u@e.com", hashed_password="x", **kw)
    db.add(u)
    db.commit()
    return u


def test_llm_call_log_row_roundtrips(db_session):
    u = _user(db_session, quota_overrides={"cv": 20})
    db_session.add(
        LlmCallLog(
            user_id=u.id,
            feature="cv",
            model="claude-sonnet-5",
            input_tokens=1200,
            output_tokens=800,
        )
    )
    db_session.commit()
    row = db_session.query(LlmCallLog).one()
    assert row.feature == "cv" and row.input_tokens == 1200
    assert db_session.get(User, u.id).quota_overrides == {"cv": 20}


def test_default_limit_and_override(db_session):
    u = _user(db_session, quota_overrides={"cv": 20})
    assert monthly_limit(u, "cv") == 20
    assert monthly_limit(u, "diagnostic") == 7


def test_enforce_raises_at_limit(db_session):
    u = _user(db_session)
    for _ in range(7):
        record_llm_call(db_session, user_id=u.id, feature="diagnostic")
    assert used_this_month(db_session, u.id, "diagnostic") == 7
    with pytest.raises(QuotaExceeded) as ei:
        enforce_monthly_quota(db_session, u, "diagnostic")
    assert ei.value.feature == "diagnostic" and ei.value.limit == 7
    assert "réinitialise" in ei.value.as_dict()["message"]


def test_last_month_calls_do_not_count(db_session):
    u = _user(db_session)
    row = LlmCallLog(user_id=u.id, feature="cv")
    db_session.add(row)
    db_session.flush()
    row.created_at = utcnow().replace(day=1) - timedelta(days=2)
    db_session.commit()
    assert used_this_month(db_session, u.id, "cv") == 0


def test_usage_summary_shape(db_session):
    u = _user(db_session)
    record_llm_call(db_session, user_id=u.id, feature="cv")
    summary = {row["feature"]: row for row in usage_summary(db_session, u)}
    assert summary["cv"]["used"] == 1 and summary["cv"]["limit"] == 5
    assert set(summary) == {
        "diagnostic",
        "cv",
        "lettre",
        "compatibility",
        "interview_prep",
        "ats_prefill",
    }
