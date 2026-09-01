"""Shared test helpers."""

from scripts.invites import generate_codes


def register_and_login(
    client, email: str = "jane@example.com", password: str = "s3cret!1"
) -> str:
    """Register a fresh user (with a one-off invite code + consent) and return
    a bearer token. Relies on the `client` fixture stashing `db_session` on
    the TestClient (see tests/conftest.py)."""
    (code,) = generate_codes(client.db_session, count=1, note="test")
    resp = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "invite_code": code,
            "accept_terms": True,
        },
    )
    assert resp.status_code == 201, resp.text
    login = client.post("/auth/login", data={"username": email, "password": password})
    return login.json()["access_token"]
