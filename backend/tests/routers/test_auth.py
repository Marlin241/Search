def test_register_creates_user(client):
    response = client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert "id" in body


def test_register_duplicate_email_returns_409(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "s3cret!"})
    response = client.post("/auth/register", json={"email": "dup@example.com", "password": "other"})
    assert response.status_code == 409


def test_login_returns_token(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!"})
    response = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "s3cret!"}
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_wrong_password_returns_401(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!"})
    response = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "wrong"}
    )
    assert response.status_code == 401


def test_me_requires_valid_token(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!"})
    login = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "s3cret!"}
    )
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "jane@example.com"

    unauthorized = client.get("/auth/me")
    assert unauthorized.status_code == 401
