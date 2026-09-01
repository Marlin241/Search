import pytest

from app.rate_limit.auth_throttle import (
    AuthThrottleExceeded,
    check_auth_throttle,
    clear_auth_attempts,
    record_auth_attempt,
)


def test_login_allows_up_to_8_then_blocks(db_session):
    for _ in range(8):
        check_auth_throttle(db_session, action="login", identifier="a@e.com|1.2.3.4")
        record_auth_attempt(db_session, action="login", identifier="a@e.com|1.2.3.4")
    with pytest.raises(AuthThrottleExceeded):
        check_auth_throttle(db_session, action="login", identifier="a@e.com|1.2.3.4")


def test_clear_resets_the_counter(db_session):
    for _ in range(8):
        record_auth_attempt(db_session, action="login", identifier="k")
    clear_auth_attempts(db_session, action="login", identifier="k")
    check_auth_throttle(db_session, action="login", identifier="k")  # no raise


def test_separate_identifiers_do_not_interfere(db_session):
    for _ in range(8):
        record_auth_attempt(db_session, action="login", identifier="k1")
    check_auth_throttle(db_session, action="login", identifier="k2")  # no raise
