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


def test_admin_overview_forbidden_for_normal_user(client, user_headers):
    assert client.get("/admin/overview", headers=user_headers).status_code == 403


def test_overview_counts_users(client, admin_headers, user_headers):
    body = client.get("/admin/overview", headers=admin_headers).json()
    assert body["users_total"] >= 2
    assert "llm_features_enabled" in body


def test_users_list_includes_invite_note_and_usage(client, admin_headers):
    rows = client.get("/admin/users", headers=admin_headers).json()
    admin_row = next(r for r in rows if r["email"] == "admin@e.com")
    assert admin_row["invite_note"] == "admin"
    assert len(admin_row["usage"]) == 6


def test_patch_quota_sets_and_clears_override(client, db_session, admin_headers):
    uid = db_session.query(User).filter_by(email="admin@e.com").one().id
    resp = client.patch(
        f"/admin/users/{uid}/quota",
        headers=admin_headers,
        json={"feature": "cv", "limit": 25},
    )
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.get(User, uid).quota_overrides == {"cv": 25}
    client.patch(
        f"/admin/users/{uid}/quota",
        headers=admin_headers,
        json={"feature": "cv", "limit": None},
    )
    db_session.expire_all()
    assert db_session.get(User, uid).quota_overrides is None


def test_cannot_disable_self(client, db_session, admin_headers):
    uid = db_session.query(User).filter_by(email="admin@e.com").one().id
    resp = client.patch(
        f"/admin/users/{uid}/active", headers=admin_headers, json={"active": False}
    )
    assert resp.status_code == 400


def test_generate_and_revoke_invites(client, admin_headers):
    codes = client.post(
        "/admin/invites", headers=admin_headers, json={"count": 3, "note": "vague 2"}
    ).json()["codes"]
    assert len(codes) == 3
    listing = client.get("/admin/invites", headers=admin_headers).json()
    assert any(r["code"] == codes[0] and r["note"] == "vague 2" for r in listing)
    assert (
        client.delete(f"/admin/invites/{codes[0]}", headers=admin_headers).status_code
        == 204
    )


def test_llm_toggle(client, admin_headers):
    assert (
        client.post(
            "/admin/llm-toggle", headers=admin_headers, json={"enabled": False}
        ).json()["enabled"]
        is False
    )
    assert (
        client.get("/admin/overview", headers=admin_headers).json()[
            "llm_features_enabled"
        ]
        is False
    )
    client.post("/admin/llm-toggle", headers=admin_headers, json={"enabled": True})


def test_feedback_list_and_handle(client, db_session, admin_headers):
    from app.models.feedback import Feedback

    db_session.add(Feedback(user_id=None, page="/offres", message="super utile"))
    db_session.commit()
    rows = client.get("/admin/feedback", headers=admin_headers).json()
    assert rows[0]["message"] == "super utile"
    assert (
        client.post(
            f"/admin/feedback/{rows[0]['id']}/handled", headers=admin_headers
        ).status_code
        == 204
    )
