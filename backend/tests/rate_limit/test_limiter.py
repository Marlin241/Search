from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.rate_limit.limiter import (
    check_rate_limit,
    lock_user_for_rate_limit,
    RateLimitExceeded,
    MAX_DIAGNOSTICS_PER_HOUR,
)


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


def test_lock_user_for_rate_limit_does_not_error_on_sqlite(db_session):
    # SQLite (the test database) doesn't support meaningful row-level
    # locking, so `lock_user_for_rate_limit` must detect the dialect and
    # no-op the `.with_for_update()` call rather than issuing it. This test
    # can't prove locking semantics under SQLite (nothing to test there
    # without real concurrency), but it does prove the dialect-detection
    # branch is exercised and doesn't raise.
    user = _make_user(db_session)

    lock_user_for_rate_limit(db_session, user.id)  # should not raise

    # The session must remain fully usable afterwards (no lingering lock
    # statement, no broken transaction state).
    check_rate_limit(db_session, user.id)


def test_lock_then_check_rate_limit_still_enforces_limit_sequentially(db_session):
    # Simulates the router's call order (lock, then check) for sequential
    # requests, proving the added lock call doesn't interfere with the
    # existing sequential rate-limit behavior.
    user = _make_user(db_session)
    _add_diagnostics(db_session, user.id, MAX_DIAGNOSTICS_PER_HOUR)
    import pytest

    lock_user_for_rate_limit(db_session, user.id)  # should not raise
    with pytest.raises(RateLimitExceeded):
        check_rate_limit(db_session, user.id)


from app.models.personalization_request_log import PersonalizationRequestLog
from app.rate_limit.limiter import MAX_PERSONALIZATIONS_PER_HOUR, check_personalization_rate_limit


def _add_personalization_logs(db_session, user_id: int, count: int) -> None:
    for _ in range(count):
        db_session.add(PersonalizationRequestLog(user_id=user_id))
    db_session.commit()


def test_personalization_allows_under_limit(db_session):
    user = _make_user(db_session)
    _add_personalization_logs(db_session, user.id, MAX_PERSONALIZATIONS_PER_HOUR - 1)
    check_personalization_rate_limit(db_session, user.id)  # should not raise


def test_personalization_blocks_at_limit(db_session):
    user = _make_user(db_session)
    _add_personalization_logs(db_session, user.id, MAX_PERSONALIZATIONS_PER_HOUR)
    import pytest

    with pytest.raises(RateLimitExceeded):
        check_personalization_rate_limit(db_session, user.id)


def test_diagnostic_and_personalization_rate_limits_are_independent(db_session):
    user = _make_user(db_session)
    _add_diagnostics(db_session, user.id, MAX_DIAGNOSTICS_PER_HOUR)
    # The diagnostic limit is maxed out, but personalization has its own counter.
    check_personalization_rate_limit(db_session, user.id)  # should not raise
