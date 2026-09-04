from app.job_search.unsubscribe import create_unsubscribe_token


def _register_and_login(client, email: str = "jane@example.com") -> str:
    from tests._helpers import register_and_login

    return register_and_login(client, email)


def test_unsubscribe_disables_the_saved_search(client):
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
    me = client.get("/auth/me", headers=headers).json()
    unsubscribe_token = create_unsubscribe_token(me["id"])

    response = client.get(
        f"/job-search/saved-search/unsubscribe?token={unsubscribe_token}"
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    saved = client.get("/job-search/saved-search", headers=headers).json()
    assert saved["enabled"] is False


def test_unsubscribe_is_idempotent(client):
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
    me = client.get("/auth/me", headers=headers).json()
    unsubscribe_token = create_unsubscribe_token(me["id"])

    client.get(f"/job-search/saved-search/unsubscribe?token={unsubscribe_token}")
    second_response = client.get(
        f"/job-search/saved-search/unsubscribe?token={unsubscribe_token}"
    )

    assert second_response.status_code == 200
    saved = client.get("/job-search/saved-search", headers=headers).json()
    assert saved["enabled"] is False


def test_unsubscribe_with_invalid_token_returns_400(client):
    response = client.get("/job-search/saved-search/unsubscribe?token=garbage")
    assert response.status_code == 400


def test_one_click_post_unsubscribe_disables_the_saved_search(client):
    """Le POST est ce que Gmail/Yahoo/Outlook déclenchent eux-mêmes pour le
    "List-Unsubscribe-Post" (RFC 8058) - jamais un clic humain direct."""
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
    me = client.get("/auth/me", headers=headers).json()
    unsubscribe_token = create_unsubscribe_token(me["id"])

    response = client.post(
        f"/job-search/saved-search/unsubscribe?token={unsubscribe_token}"
    )

    assert response.status_code == 200
    saved = client.get("/job-search/saved-search", headers=headers).json()
    assert saved["enabled"] is False


def test_one_click_post_unsubscribe_with_invalid_token_still_returns_200(client):
    # Le client mail n'affiche jamais le corps de la réponse : un token
    # invalide ne doit pas casser son UI de désabonnement en un clic.
    response = client.post("/job-search/saved-search/unsubscribe?token=garbage")
    assert response.status_code == 200
