def test_register_creates_user(client):
    response = client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!1"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert "id" in body


def test_register_duplicate_email_returns_409(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "s3cret!1"})
    response = client.post("/auth/register", json={"email": "dup@example.com", "password": "otherpw1"})
    assert response.status_code == 409


def test_login_returns_token(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!1"})
    response = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "s3cret!1"}
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_wrong_password_returns_401(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!1"})
    response = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "wrong"}
    )
    assert response.status_code == 401


def test_register_password_under_min_length_returns_422(client):
    response = client.post(
        "/auth/register", json={"email": "short@example.com", "password": "sh0rt!"}
    )
    assert response.status_code == 422


def test_register_password_over_max_length_returns_422(client):
    response = client.post(
        "/auth/register",
        json={"email": "long@example.com", "password": "a" * 73},
    )
    assert response.status_code == 422


def test_login_with_over_length_password_returns_401_not_500(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!1"})
    response = client.post(
        "/auth/login",
        data={"username": "jane@example.com", "password": "a" * 100},
    )
    assert response.status_code == 401


def test_me_requires_valid_token(client):
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!1"})
    login = client.post(
        "/auth/login", data={"username": "jane@example.com", "password": "s3cret!1"}
    )
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "jane@example.com"

    unauthorized = client.get("/auth/me")
    assert unauthorized.status_code == 401
