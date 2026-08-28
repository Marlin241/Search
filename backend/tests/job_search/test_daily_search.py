from datetime import UTC, datetime

import respx

from app.job_search.daily_search import _is_notification_time, run_daily_search
from app.job_search.schemas import JobListing
from app.models.notified_listing import NotifiedListing
from app.models.saved_search import SavedSearch
from app.models.user import User


def test_is_notification_time_matches_local_8am():
    saved_search = SavedSearch(timezone="Europe/Paris")
    # 6h UTC = 8h à Paris en été (UTC+2)
    now = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)
    assert _is_notification_time(saved_search, now) is True


def test_is_notification_time_does_not_match_other_hours():
    saved_search = SavedSearch(timezone="Europe/Paris")
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    assert _is_notification_time(saved_search, now) is False


class _EmptyClient:
    def search(self, criteria):
        return []


class _EmptySluggableClient:
    def search(self, criteria, company_slugs):
        return []


def _clients() -> dict[str, object]:
    return {
        "france_travail": _EmptyClient(),
        "adzuna": _EmptyClient(),
        "la_bonne_alternance": _EmptyClient(),
        "greenhouse": _EmptySluggableClient(),
        "lever": _EmptySluggableClient(),
        "reliefweb": _EmptyClient(),
        "jobicy": _EmptyClient(),
        "weworkremotely": _EmptyClient(),
        "ngojobs": _EmptyClient(),
    }


def _make_user_with_saved_search(db_session, email: str = "jane@example.com") -> User:
    user = User(email=email, hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
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
    return user


class _FixedDatetime:
    """Minimal stand-in for the `datetime` class exposing only what
    daily_search.run_daily_search calls (`datetime.now(UTC)`), so tests can
    freeze "now" without a third-party time-freezing dependency."""

    def __init__(self, fixed_now):
        self._fixed_now = fixed_now

    def now(self, tz=None):
        return self._fixed_now


@respx.mock
def test_run_daily_search_sends_email_and_records_notified_listings(
    db_session, monkeypatch
):
    user = _make_user_with_saved_search(db_session)
    user_id = user.id
    user_email = user.email

    class SingleListingClient:
        def search(self, criteria):
            return [
                JobListing(
                    title="Développeur Python",
                    company="",
                    location="Paris",
                    snippet="...",
                    url="https://example.com/job/1",
                    source="france_travail",
                    ats_type=None,
                )
            ]

    clients = _clients()
    clients["france_travail"] = SingleListingClient()
    monkeypatch.setattr(
        "app.job_search.daily_search.get_job_search_clients", lambda: clients
    )

    sent_emails = []
    monkeypatch.setattr(
        "app.job_search.daily_search.send_daily_digest_email",
        lambda to_email, listings, token: sent_emails.append((to_email, listings)),
    )

    now = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)  # 8h à Paris
    monkeypatch.setattr("app.job_search.daily_search.datetime", _FixedDatetime(now))

    run_daily_search(lambda: db_session)

    assert len(sent_emails) == 1
    assert sent_emails[0][0] == user_email
    assert len(sent_emails[0][1]) == 1

    notified = (
        db_session.query(NotifiedListing)
        .filter(NotifiedListing.user_id == user_id)
        .all()
    )
    assert len(notified) == 1
    assert notified[0].offer_url == "https://example.com/job/1"


@respx.mock
def test_run_daily_search_skips_already_notified_listings(db_session, monkeypatch):
    user = _make_user_with_saved_search(db_session)
    db_session.add(
        NotifiedListing(user_id=user.id, offer_url="https://example.com/job/1")
    )
    db_session.commit()

    class SingleListingClient:
        def search(self, criteria):
            return [
                JobListing(
                    title="Développeur Python",
                    company="",
                    location="Paris",
                    snippet="...",
                    url="https://example.com/job/1",
                    source="france_travail",
                    ats_type=None,
                )
            ]

    clients = _clients()
    clients["france_travail"] = SingleListingClient()
    monkeypatch.setattr(
        "app.job_search.daily_search.get_job_search_clients", lambda: clients
    )

    sent_emails = []
    monkeypatch.setattr(
        "app.job_search.daily_search.send_daily_digest_email",
        lambda to_email, listings, token: sent_emails.append((to_email, listings)),
    )

    now = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)
    monkeypatch.setattr("app.job_search.daily_search.datetime", _FixedDatetime(now))

    run_daily_search(lambda: db_session)

    assert sent_emails == []


@respx.mock
def test_run_daily_search_skips_users_outside_their_notification_hour(
    db_session, monkeypatch
):
    _make_user_with_saved_search(db_session)

    clients = _clients()
    monkeypatch.setattr(
        "app.job_search.daily_search.get_job_search_clients", lambda: clients
    )
    sent_emails = []
    monkeypatch.setattr(
        "app.job_search.daily_search.send_daily_digest_email",
        lambda to_email, listings, token: sent_emails.append((to_email, listings)),
    )

    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)  # 14h à Paris, pas 8h
    monkeypatch.setattr("app.job_search.daily_search.datetime", _FixedDatetime(now))

    run_daily_search(lambda: db_session)

    assert sent_emails == []


@respx.mock
def test_run_daily_search_continues_after_one_user_email_fails(db_session, monkeypatch):
    _make_user_with_saved_search(db_session, email="jane@example.com")
    _make_user_with_saved_search(db_session, email="bob@example.com")

    class SingleListingClient:
        def search(self, criteria):
            return [
                JobListing(
                    title="Développeur Python",
                    company="",
                    location="Paris",
                    snippet="...",
                    url="https://example.com/job/1",
                    source="france_travail",
                    ats_type=None,
                )
            ]

    clients = _clients()
    clients["france_travail"] = SingleListingClient()
    monkeypatch.setattr(
        "app.job_search.daily_search.get_job_search_clients", lambda: clients
    )

    from app.notifications.resend_client import EmailSendError

    sent_emails = []

    def fake_send(to_email, listings, token):
        if to_email == "jane@example.com":
            raise EmailSendError("boom")
        sent_emails.append(to_email)

    monkeypatch.setattr(
        "app.job_search.daily_search.send_daily_digest_email", fake_send
    )

    now = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)
    monkeypatch.setattr("app.job_search.daily_search.datetime", _FixedDatetime(now))

    run_daily_search(lambda: db_session)

    # bob's email still got sent despite jane's failing
    assert sent_emails == ["bob@example.com"]
