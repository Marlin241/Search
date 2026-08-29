import pytest

from scripts.invites import generate_codes


@pytest.fixture()
def invite_code(db_session):
    (code,) = generate_codes(db_session, count=1, note="test")
    return code


def _register(client, invite_code, email="jane@example.com", password="s3cret!1"):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "invite_code": invite_code,
            "accept_terms": True,
        },
    )


def test_register_creates_user(client, invite_code):
    response = _register(client, invite_code)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert "id" in body


def test_register_duplicate_email_returns_409(client, db_session):
    codes = generate_codes(db_session, count=2, note="dup")
    _register(client, codes[0], email="dup@example.com")
    response = _register(client, codes[1], email="dup@example.com", password="otherpw1")
    assert response.status_code == 409


def test_login_returns_token(client, invite_code):
    _register(client, invite_code)
    response = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "s3cret!1"}
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_wrong_password_returns_401(client, invite_code):
    _register(client, invite_code)
    response = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "wrong"}
    )
    assert response.status_code == 401


def test_register_password_under_min_length_returns_422(client, invite_code):
    response = _register(client, invite_code, email="short@example.com", password="sh0rt!")
    assert response.status_code == 422


def test_register_password_over_max_length_returns_422(client, invite_code):
    response = _register(
        client, invite_code, email="long@example.com", password="a" * 73
    )
    assert response.status_code == 422


def test_login_with_over_length_password_returns_401_not_500(client, invite_code):
    _register(client, invite_code)
    response = client.post(
        "/auth/login",
        data={"username": "jane@example.com", "password": "a" * 100},
    )
    assert response.status_code == 401


def test_me_requires_valid_token(client, invite_code):
    _register(client, invite_code)
    login = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "s3cret!1"}
    )
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "jane@example.com"

    unauthorized = client.get("/auth/me")
    assert unauthorized.status_code == 401


# --- invite code + consent ---


def test_register_without_invite_code_returns_422(client):
    resp = client.post(
        "/auth/register",
        json={"email": "x@e.com", "password": "s3cret!1", "accept_terms": True},
    )
    assert resp.status_code == 422


def test_register_with_unknown_code_returns_400(client):
    resp = client.post(
        "/auth/register",
        json={
            "email": "x@e.com",
            "password": "s3cret!1",
            "invite_code": "bogus",
            "accept_terms": True,
        },
    )
    assert resp.status_code == 400


def test_register_without_accept_terms_returns_422(client, invite_code):
    resp = client.post(
        "/auth/register",
        json={
            "email": "x@e.com",
            "password": "s3cret!1",
            "invite_code": invite_code,
            "accept_terms": False,
        },
    )
    assert resp.status_code == 422


def test_register_consumes_code_and_stamps_consent(client, db_session, invite_code):
    assert _register(client, invite_code).status_code == 201
    from app.models.invite_code import InviteCode
    from app.models.user import User

    row = db_session.query(InviteCode).filter_by(code=invite_code).one()
    assert row.used_at is not None and row.used_by_user_id is not None
    user = db_session.query(User).filter_by(email="jane@example.com").one()
    assert user.consent_version == "2026-09" and user.consent_accepted_at is not None


def test_code_cannot_be_reused(client, invite_code):
    assert _register(client, invite_code, email="a@e.com").status_code == 201
    assert _register(client, invite_code, email="b@e.com").status_code == 400


def test_login_blocks_after_8_failures(client, invite_code):
    _register(client, invite_code, email="j@e.com")
    for _ in range(8):
        client.post("/auth/login", data={"username": "j@e.com", "password": "wrong"})
    resp = client.post("/auth/login", data={"username": "j@e.com", "password": "wrong"})
    assert resp.status_code == 429
