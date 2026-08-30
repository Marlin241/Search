from app.models.access_request import AccessRequest


def _payload(**over):
    base = {"email": "cand@example.com", "note": "dev backend, dispo tout de suite"}
    base.update(over)
    return base


def test_valid_request_stores_row_and_returns_204(client, db_session, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_notification",
        lambda *a, **k: calls.append((a, k)),
    )
    resp = client.post("/access-requests", json=_payload(email="CAND@Example.com  "))
    assert resp.status_code == 204
    row = db_session.query(AccessRequest).one()
    assert row.email == "cand@example.com"  # normalisé minuscule + trim
    assert row.note == "dev backend, dispo tout de suite"
    assert row.handled_at is None
    assert len(calls) == 1


def test_honeypot_filled_is_silently_dropped(client, db_session):
    resp = client.post("/access-requests", json=_payload(company="Acme Corp"))
    assert resp.status_code == 204
    assert db_session.query(AccessRequest).count() == 0


def test_invalid_email_is_422(client):
    assert (
        client.post("/access-requests", json=_payload(email="pas-un-email")).status_code
        == 422
    )


def test_note_too_long_is_422(client):
    assert (
        client.post("/access-requests", json=_payload(note="x" * 1001)).status_code
        == 422
    )


def test_rate_limited_after_5_in_an_hour(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_notification",
        lambda *a, **k: None,
    )
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


def test_email_failure_does_not_break_request(client, db_session, monkeypatch):
    def boom(*a, **k):
        from app.notifications.resend_client import EmailSendError

        raise EmailSendError("nope")

    monkeypatch.setattr(
        "app.routers.access_requests.send_access_request_notification", boom
    )
    resp = client.post("/access-requests", json=_payload())
    assert resp.status_code == 204
    assert db_session.query(AccessRequest).count() == 1


def test_no_admin_email_configured_still_204(client, db_session):
    # send_access_request_notification s'exécute réellement mais no-op car
    # settings.admin_notify_email == "" en test.
    resp = client.post("/access-requests", json=_payload())
    assert resp.status_code == 204
    assert db_session.query(AccessRequest).count() == 1
