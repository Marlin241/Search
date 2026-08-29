import pytest

from scripts.invites import generate_codes


@pytest.fixture()
def registered(client, db_session):
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
    return "u@e.com"


def test_forgot_password_always_204(client, registered):
    assert (
        client.post("/auth/forgot-password", json={"email": registered}).status_code
        == 204
    )
    assert (
        client.post("/auth/forgot-password", json={"email": "nobody@e.com"}).status_code
        == 204
    )


def test_full_reset_flow(client, db_session, registered, monkeypatch):
    sent: dict = {}
    monkeypatch.setattr(
        "app.routers.auth.send_password_reset_email",
        lambda to, url: sent.update(to=to, url=url),
    )
    client.post("/auth/forgot-password", json={"email": registered})
    token = sent["url"].split("token=")[1]
    assert (
        client.post(
            "/auth/reset-password", json={"token": token, "password": "brandnew1"}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/auth/login", data={"username": registered, "password": "brandnew1"}
        ).status_code
        == 200
    )


def test_reset_with_bad_token_returns_400(client):
    assert (
        client.post(
            "/auth/reset-password", json={"token": "nope", "password": "brandnew1"}
        ).status_code
        == 400
    )
