import pytest

from app.models.access_request import AccessRequest
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


def _seed(db_session, n=3):
    for i in range(n):
        db_session.add(AccessRequest(email=f"c{i}@e.com", note=f"note {i}"))
    db_session.commit()


def test_list_requires_admin(client, user_headers):
    assert client.get("/admin/access-requests", headers=user_headers).status_code == 403


def test_list_returns_all_desc(client, db_session, admin_headers):
    _seed(db_session)
    rows = client.get("/admin/access-requests", headers=admin_headers).json()
    assert [r["email"] for r in rows] == ["c2@e.com", "c1@e.com", "c0@e.com"]


def test_list_pending_filters_handled(client, db_session, admin_headers):
    _seed(db_session, 2)
    first = db_session.query(AccessRequest).order_by(AccessRequest.id).first()
    client.post(f"/admin/access-requests/{first.id}/handled", headers=admin_headers)
    rows = client.get(
        "/admin/access-requests?pending=true", headers=admin_headers
    ).json()
    assert len(rows) == 1
    assert rows[0]["email"] == "c1@e.com"


def test_mark_handled_sets_timestamp_and_is_idempotent(
    client, db_session, admin_headers
):
    _seed(db_session, 1)
    rid = db_session.query(AccessRequest).one().id
    assert (
        client.post(
            f"/admin/access-requests/{rid}/handled", headers=admin_headers
        ).status_code
        == 204
    )
    db_session.expire_all()
    first_ts = db_session.query(AccessRequest).one().handled_at
    assert first_ts is not None
    assert (
        client.post(
            f"/admin/access-requests/{rid}/handled", headers=admin_headers
        ).status_code
        == 204
    )
    db_session.expire_all()
    assert db_session.query(AccessRequest).one().handled_at == first_ts


def test_mark_handled_unknown_id_404(client, admin_headers):
    assert (
        client.post(
            "/admin/access-requests/999/handled", headers=admin_headers
        ).status_code
        == 404
    )
