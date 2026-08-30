import pytest

from scripts.invites import generate_codes


@pytest.fixture()
def authed(client, db_session):
    (code,) = generate_codes(db_session, count=1, note="t")
    client.post(
        "/auth/register",
        json={
            "email": "u@e.com",
            "password": "s3cret!1",
            "invite_code": code,
            "accept_terms": True,
        },
    )
    token = client.post(
        "/auth/login", data={"username": "u@e.com", "password": "s3cret!1"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_feedback_requires_auth(client):
    assert (
        client.post("/feedback", json={"page": "/offres", "message": "x"}).status_code
        == 401
    )


def test_feedback_stores_row_and_notifies(client, db_session, authed, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.routers.feedback.send_feedback_notification",
        lambda *a, **k: calls.append((a, k)),
    )
    resp = client.post(
        "/feedback", json={"page": "/offres", "message": "très utile"}, headers=authed
    )
    assert resp.status_code == 204
    from app.models.feedback import Feedback

    row = db_session.query(Feedback).one()
    assert row.message == "très utile"
    assert row.page == "/offres"
    assert row.user_id is not None
    assert len(calls) == 1


def test_feedback_empty_message_422(client, authed):
    assert (
        client.post(
            "/feedback", json={"page": "/x", "message": ""}, headers=authed
        ).status_code
        == 422
    )


def test_feedback_notification_failure_is_non_blocking(client, authed, monkeypatch):
    from app.notifications.resend_client import EmailSendError

    def _boom(*a, **k):
        raise EmailSendError("down")

    monkeypatch.setattr("app.routers.feedback.send_feedback_notification", _boom)
    assert (
        client.post(
            "/feedback", json={"page": "/x", "message": "y"}, headers=authed
        ).status_code
        == 204
    )
