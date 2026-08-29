def _register_and_login(client, email: str = "jane@example.com") -> str:
    from tests._helpers import register_and_login

    return register_and_login(client, email)


def test_get_saved_search_returns_404_when_none_exists(client):
    token = _register_and_login(client)
    response = client.get(
        "/job-search/saved-search", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


def test_put_saved_search_creates_it(client):
    token = _register_and_login(client)
    response = client.put(
        "/job-search/saved-search",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "keywords": "python backend",
            "location": "Paris",
            "contract_type": "CDI",
            "remote": True,
            "exclude_keywords": ["stage"],
            "timezone": "Europe/Paris",
            "enabled": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["keywords"] == "python backend"
    assert body["timezone"] == "Europe/Paris"
    assert body["enabled"] is True

    get_response = client.get(
        "/job-search/saved-search", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 200
    assert get_response.json()["keywords"] == "python backend"


def test_put_saved_search_updates_existing(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/job-search/saved-search",
        headers=headers,
        json={
            "keywords": "python",
            "exclude_keywords": [],
            "timezone": "Europe/Paris",
            "enabled": True,
        },
    )

    response = client.put(
        "/job-search/saved-search",
        headers=headers,
        json={
            "keywords": "python senior",
            "exclude_keywords": [],
            "timezone": "Europe/Paris",
            "enabled": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["keywords"] == "python senior"
    assert body["enabled"] is False


def test_put_saved_search_rejects_invalid_timezone(client):
    token = _register_and_login(client)
    response = client.put(
        "/job-search/saved-search",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "keywords": "python",
            "exclude_keywords": [],
            "timezone": "Not/A_Real_Zone",
            "enabled": True,
        },
    )
    assert response.status_code == 422
