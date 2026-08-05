from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.rate_limit.limiter import check_rate_limit, RateLimitExceeded, MAX_DIAGNOSTICS_PER_HOUR


def _make_user(db_session) -> User:
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    return user


def _add_diagnostics(db_session, user_id: int, count: int) -> None:
    for _ in range(count):
        db_session.add(
            Diagnostic(
                user_id=user_id,
                cv_text="cv",
                offer_text="offer",
                overall_score=1,
                structural_score=1,
                structural_issues=[],
                semantic_score=1,
                missing_keywords=[],
                recommendations=[],
            )
        )
    db_session.commit()


def test_allows_under_limit(db_session):
    user = _make_user(db_session)
    _add_diagnostics(db_session, user.id, MAX_DIAGNOSTICS_PER_HOUR - 1)
    check_rate_limit(db_session, user.id)  # should not raise


def test_blocks_at_limit(db_session):
    user = _make_user(db_session)
    _add_diagnostics(db_session, user.id, MAX_DIAGNOSTICS_PER_HOUR)
    import pytest

    with pytest.raises(RateLimitExceeded):
        check_rate_limit(db_session, user.id)
