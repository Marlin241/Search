from app.job_search.dependencies import get_job_search_clients
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing
from app.main import app
from app.rate_limit.limiter import MAX_SEARCHES_PER_HOUR


def _register_and_login(client, email: str = "jane@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": email, "password": "s3cret!1"})
    return login.json()["access_token"]


class FakeWorkingClient:
    def search(self, criteria):
        return [
            JobListing(
                title="Développeur Python",
                company="Acme",
                location="Paris",
                snippet="...",
                url="https://example.com/1",
                source="fake",
                ats_type=None,
            )
        ]


class FakeFailingClient:
    def search(self, criteria):
        raise JobSearchSourceError("down")


def test_search_returns_listings_and_unavailable_sources(client):
    app.dependency_overrides[get_job_search_clients] = lambda: {
        "france_travail": FakeWorkingClient(),
        "adzuna": FakeFailingClient(),
    }
    token = _register_and_login(client)

    response = client.post(
        "/job-search/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"keywords": "python"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["listings"]) == 1
    assert body["unavailable_sources"] == ["adzuna"]


def test_search_requires_auth(client):
    app.dependency_overrides[get_job_search_clients] = lambda: {"france_travail": FakeWorkingClient()}
    response = client.post("/job-search/search", json={"keywords": "python"})
    assert response.status_code == 401


def test_search_rate_limited_after_max_per_hour(client):
    app.dependency_overrides[get_job_search_clients] = lambda: {"france_travail": FakeWorkingClient()}
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(MAX_SEARCHES_PER_HOUR):
        response = client.post("/job-search/search", headers=headers, json={"keywords": "python"})
        assert response.status_code == 200

    response = client.post("/job-search/search", headers=headers, json={"keywords": "python"})
    assert response.status_code == 429
