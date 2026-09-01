import pytest

from app.models.access_request import AccessRequest
from app.notifications.resend_client import EmailSendError


@pytest.fixture()
def emails(monkeypatch):
    """Capture les envois d'email du routeur sans toucher au réseau."""
    sent = {"confirmation": [], "notification": []}
    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_confirmation",
        lambda to: sent["confirmation"].append(to),
    )
    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_notification",
        lambda *a, **k: sent["notification"].append((a, k)),
    )
    return sent


def _payload(**over):
    base = {"email": "cand@example.com", "note": "dev backend, dispo tout de suite"}
    base.update(over)
    return base


def test_valid_request_stores_row_and_returns_204(client, db_session, emails):
    resp = client.post("/access-requests", json=_payload(email="CAND@Example.com  "))
    assert resp.status_code == 204
    row = db_session.query(AccessRequest).one()
    assert row.email == "cand@example.com"  # normalisé minuscule + trim
    assert row.note == "dev backend, dispo tout de suite"
    assert row.status == "pending"
    assert row.handled_at is None
    assert emails["confirmation"] == ["cand@example.com"]
    assert len(emails["notification"]) == 1


def test_honeypot_filled_is_silently_dropped(client, db_session, emails):
    resp = client.post("/access-requests", json=_payload(company="Acme Corp"))
    assert resp.status_code == 204
    assert db_session.query(AccessRequest).count() == 0
    assert emails["confirmation"] == []


def test_invalid_email_is_422(client, emails):
    assert (
        client.post("/access-requests", json=_payload(email="pas-un-email")).status_code
        == 422
    )


def test_note_too_long_is_422(client, emails):
    assert (
        client.post("/access-requests", json=_payload(note="x" * 1001)).status_code
        == 422
    )


def test_rate_limited_after_5_in_an_hour(client, db_session, emails):
    for i in range(5):
        assert (
            client.post(
                "/access-requests", json=_payload(email=f"u{i}@e.com")
            ).status_code
            == 204
        )
    resp = client.post("/access-requests", json=_payload(email="u6@e.com"))
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "rate_limited"


def test_confirmation_email_failure_does_not_break_request(
    client, db_session, monkeypatch
):
    def boom(*a, **k):
        raise EmailSendError("nope")

    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_confirmation", boom
    )
    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_notification",
        lambda *a, **k: None,
    )
    resp = client.post("/access-requests", json=_payload())
    assert resp.status_code == 204
    assert db_session.query(AccessRequest).count() == 1


def test_notification_email_failure_does_not_break_request(
    client, db_session, monkeypatch
):
    def boom(*a, **k):
        raise EmailSendError("nope")

    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_confirmation",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_notification", boom
    )
    resp = client.post("/access-requests", json=_payload())
    assert resp.status_code == 204
    assert db_session.query(AccessRequest).count() == 1
