import pytest

from app.models.access_request import AccessRequest
from app.models.invite_code import InviteCode
from app.models.user import User
from scripts.invites import generate_codes


@pytest.fixture(autouse=True)
def _stub_granted_email(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.routers.admin.send_access_granted_email",
        lambda to, code, url: sent.append((to, code, url)),
    )
    return sent


@pytest.fixture()
def granted_emails(_stub_granted_email):
    return _stub_granted_email


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


def _one_id(db_session):
    return db_session.query(AccessRequest).order_by(AccessRequest.id).first().id


def _access_codes(db_session):
    return (
        db_session.query(InviteCode)
        .filter(InviteCode.note.like("demande d'accès%"))
        .count()
    )


def test_list_requires_admin(client, user_headers):
    assert client.get("/admin/access-requests", headers=user_headers).status_code == 403


def test_list_returns_all_desc(client, db_session, admin_headers):
    _seed(db_session)
    rows = client.get("/admin/access-requests", headers=admin_headers).json()
    assert [r["email"] for r in rows] == ["c2@e.com", "c1@e.com", "c0@e.com"]
    assert all(r["status"] == "pending" for r in rows)


def test_list_pending_filters_out_decided(client, db_session, admin_headers):
    _seed(db_session, 2)
    rid = _one_id(db_session)
    client.post(f"/admin/access-requests/{rid}/dismiss", headers=admin_headers)
    rows = client.get(
        "/admin/access-requests?pending=true", headers=admin_headers
    ).json()
    assert [r["email"] for r in rows] == ["c1@e.com"]


def test_approve_generates_code_sets_status_and_emails(
    client, db_session, admin_headers, granted_emails
):
    _seed(db_session, 1)
    rid = _one_id(db_session)
    resp = client.post(f"/admin/access-requests/{rid}/approve", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["invite_code"]
    assert body["handled_at"] is not None

    # le code existe et est utilisable
    db_session.expire_all()
    code_row = db_session.query(InviteCode).filter_by(code=body["invite_code"]).one()
    assert code_row.used_at is None
    # email envoyé au demandeur avec le bon code + lien vers /login
    assert len(granted_emails) == 1
    to, code, login_url = granted_emails[0]
    assert to == "c0@e.com"
    assert code == body["invite_code"]
    assert login_url.endswith("/login")


def test_approve_is_idempotent_no_second_code(
    client, db_session, admin_headers, granted_emails
):
    _seed(db_session, 1)
    rid = _one_id(db_session)
    first = client.post(
        f"/admin/access-requests/{rid}/approve", headers=admin_headers
    ).json()
    second = client.post(
        f"/admin/access-requests/{rid}/approve", headers=admin_headers
    ).json()
    assert second["invite_code"] == first["invite_code"]
    assert _access_codes(db_session) == 1
    assert len(granted_emails) == 1


def test_dismiss_sets_status_without_email(
    client, db_session, admin_headers, granted_emails
):
    _seed(db_session, 1)
    rid = _one_id(db_session)
    resp = client.post(f"/admin/access-requests/{rid}/dismiss", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"
    assert _access_codes(db_session) == 0
    assert granted_emails == []


def test_dismiss_then_approve_is_noop(client, db_session, admin_headers):
    _seed(db_session, 1)
    rid = _one_id(db_session)
    client.post(f"/admin/access-requests/{rid}/dismiss", headers=admin_headers)
    body = client.post(
        f"/admin/access-requests/{rid}/approve", headers=admin_headers
    ).json()
    assert body["status"] == "dismissed"
    assert body["invite_code"] is None


def test_approve_unknown_id_404(client, admin_headers):
    assert (
        client.post(
            "/admin/access-requests/999/approve", headers=admin_headers
        ).status_code
        == 404
    )


def test_approve_email_failure_still_succeeds(
    client, db_session, admin_headers, monkeypatch
):
    def boom(*a, **k):
        from app.notifications.resend_client import EmailSendError

        raise EmailSendError("nope")

    monkeypatch.setattr("app.routers.admin.send_access_granted_email", boom)
    _seed(db_session, 1)
    rid = _one_id(db_session)
    resp = client.post(f"/admin/access-requests/{rid}/approve", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
