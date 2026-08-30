import pytest

from app.models.user import User
from scripts.invites import generate_codes


@pytest.fixture()
def admin_headers(client, db_session):
    (code,) = generate_codes(db_session, count=1, note="admin")
    client.post(
        "/auth/register",
        json={
            "email": "admin@e.com",
            "password": "s3cret!1",
            "invite_code": code,
            "accept_terms": True,
        },
    )
    db_session.query(User).filter_by(email="admin@e.com").update({"is_admin": True})
    db_session.commit()
    token = client.post(
        "/auth/login", data={"username": "admin@e.com", "password": "s3cret!1"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_headers(client, db_session):
    (code,) = generate_codes(db_session, count=1, note="u")
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


def test_me_reports_is_admin(client, admin_headers):
    assert client.get("/auth/me", headers=admin_headers).json()["is_admin"] is True


def test_disabled_account_cannot_login(client, db_session, user_headers):
    db_session.query(User).filter_by(email="u@e.com").update({"is_active": False})
    db_session.commit()
    resp = client.post(
        "/auth/login", data={"username": "u@e.com", "password": "s3cret!1"}
    )
    assert resp.status_code == 403
