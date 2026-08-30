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


def test_export_returns_account_shape(client, authed):
    resp = client.get("/auth/me/export", headers=authed)
    assert resp.status_code == 200
    assert 'filename="mes-donnees.json"' in resp.headers.get("content-disposition", "")
    body = resp.json()
    assert body["account"]["email"] == "u@e.com"
    assert "diagnostics" in body and "usage" in body


def test_delete_me_wrong_password_403(client, authed):
    resp = client.request(
        "DELETE", "/auth/me", headers=authed, json={"password": "nope"}
    )
    assert resp.status_code == 403


def test_delete_me_succeeds_and_login_then_fails(client, authed):
    resp = client.request(
        "DELETE", "/auth/me", headers=authed, json={"password": "s3cret!1"}
    )
    assert resp.status_code == 204
    login = client.post(
        "/auth/login", data={"username": "u@e.com", "password": "s3cret!1"}
    )
    assert login.status_code == 401
