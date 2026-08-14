from datetime import UTC, datetime, timedelta

from app.applications.reminders import _is_notification_time, run_application_reminders
from app.models.application import (
    APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
    APPLICATION_STATUS_EN_COURS,
    APPLICATION_STATUS_SOUMISE_AUTO,
    Application,
)
from app.models.diagnostic import Diagnostic
from app.models.saved_search import SavedSearch
from app.models.user import User


def test_is_notification_time_matches_local_8am():
    now = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)  # 8h à Paris en été
    assert _is_notification_time("Europe/Paris", now) is True


def test_is_notification_time_does_not_match_other_hours():
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    assert _is_notification_time("Europe/Paris", now) is False


def _make_user(db_session, email: str = "jane@example.com") -> User:
    user = User(email=email, hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    return user


def _make_diagnostic(db_session, user: User) -> Diagnostic:
    diagnostic = Diagnostic(
        user_id=user.id,
        cv_text="cv",
        offer_text="offer",
        overall_score=1,
        structural_score=1,
        structural_issues=[],
        semantic_score=1,
        missing_keywords=[],
        recommendations=[],
    )
    db_session.add(diagnostic)
    db_session.commit()
    return diagnostic


def _make_application(db_session, user, diagnostic, offer_url, **overrides):
    defaults = {
        "user_id": user.id,
        "diagnostic_id": diagnostic.id,
        "offer_url": offer_url,
        "source": "manual",
        "company_name": "Acme",
        "job_title": "Développeur Python",
        "ats_type": None,
        "status": APPLICATION_STATUS_EN_COURS,
    }
    defaults.update(overrides)
    application = Application(**defaults)
    db_session.add(application)
    db_session.commit()
    return application


class _FixedDatetime:
    """Minimal stand-in for the `datetime` class exposing only what
    run_application_reminders calls (`datetime.now(UTC)`), so tests can
    freeze "now" without a third-party time-freezing dependency."""

    def __init__(self, fixed_now):
        self._fixed_now = fixed_now

    def now(self, tz=None):
        return self._fixed_now


_NOW = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)  # 8h à Paris
_TEN_DAYS_AGO = _NOW.replace(tzinfo=None) - timedelta(days=10)
_TWO_DAYS_AGO = _NOW.replace(tzinfo=None) - timedelta(days=2)


def test_run_application_reminders_selects_and_marks_application_to_relance(
    db_session, monkeypatch
):
    user = _make_user(db_session)
    db_session.add(
        SavedSearch(
            user_id=user.id,
            keywords="python",
            exclude_keywords=[],
            timezone="Europe/Paris",
            enabled=True,
        )
    )
    db_session.commit()
    diagnostic = _make_diagnostic(db_session, user)
    application = _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
    )
    application_id = application.id
    user_email = user.email  # captured before run_application_reminders closes
    # the session below - accessing user.email afterwards would raise
    # DetachedInstanceError (db.close() expires already-loaded attributes,
    # but a fresh query like db_session.get(...) below still works fine).

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(
            (to_email, to_relance, to_finalize)
        ),
    )
    monkeypatch.setattr("app.applications.reminders.datetime", _FixedDatetime(_NOW))

    run_application_reminders(lambda: db_session)

    assert len(sent) == 1
    assert sent[0][0] == user_email
    assert len(sent[0][1]) == 1  # to_relance
    assert sent[0][2] == []  # to_finalize

    refreshed = db_session.get(Application, application_id)
    assert refreshed.reminder_sent_at is not None


def test_run_application_reminders_selects_application_to_finalize(
    db_session, monkeypatch
):
    user = _make_user(db_session)
    diagnostic = _make_diagnostic(db_session, user)
    _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
        created_at=_TEN_DAYS_AGO,
    )

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(
            (to_email, to_relance, to_finalize)
        ),
    )
    # No SavedSearch for this user - falls back to UTC, so 6h UTC is not
    # their notification hour. Use 8h UTC instead.
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert len(sent) == 1
    assert sent[0][1] == []  # to_relance
    assert len(sent[0][2]) == 1  # to_finalize


def test_run_application_reminders_excludes_recent_applications(
    db_session, monkeypatch
):
    user = _make_user(db_session)
    diagnostic = _make_diagnostic(db_session, user)
    _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TWO_DAYS_AGO,
    )

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(to_email),
    )
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert sent == []


def test_run_application_reminders_excludes_already_reminded(db_session, monkeypatch):
    user = _make_user(db_session)
    diagnostic = _make_diagnostic(db_session, user)
    _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
        reminder_sent_at=_TWO_DAYS_AGO,
    )

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(to_email),
    )
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert sent == []


def test_run_application_reminders_skips_users_outside_their_notification_hour(
    db_session, monkeypatch
):
    user = _make_user(db_session)
    diagnostic = _make_diagnostic(db_session, user)
    _make_application(
        db_session,
        user,
        diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
    )

    sent = []
    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email",
        lambda to_email, to_relance, to_finalize: sent.append(to_email),
    )
    # No SavedSearch -> UTC fallback; 14h UTC is never the notification hour.
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 14, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert sent == []


def test_run_application_reminders_continues_after_one_user_email_fails(
    db_session, monkeypatch
):
    jane = _make_user(db_session, email="jane@example.com")
    jane_diagnostic = _make_diagnostic(db_session, jane)
    _make_application(
        db_session,
        jane,
        jane_diagnostic,
        "https://example.com/job/1",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
    )

    bob = _make_user(db_session, email="bob@example.com")
    bob_diagnostic = _make_diagnostic(db_session, bob)
    _make_application(
        db_session,
        bob,
        bob_diagnostic,
        "https://example.com/job/2",
        status=APPLICATION_STATUS_SOUMISE_AUTO,
        submitted_at=_TEN_DAYS_AGO,
    )

    from app.notifications.resend_client import EmailSendError

    sent = []

    def fake_send(to_email, to_relance, to_finalize):
        if to_email == "jane@example.com":
            raise EmailSendError("boom")
        sent.append(to_email)

    monkeypatch.setattr(
        "app.applications.reminders.send_application_reminders_email", fake_send
    )
    monkeypatch.setattr(
        "app.applications.reminders.datetime",
        _FixedDatetime(datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
    )

    run_application_reminders(lambda: db_session)

    assert sent == ["bob@example.com"]
