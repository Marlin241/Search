import httpx
import pytest
import respx

from app.job_search.adzuna import AdzunaClient
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import SearchCriteria

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/1"


@respx.mock
def test_search_returns_normalized_listings():
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Développeur Python",
                        "company": {"display_name": "Acme"},
                        "location": {"display_name": "Paris"},
                        "description": "Nous recherchons...",
                        "redirect_url": "https://www.adzuna.fr/land/ad/123",
                    }
                ]
            },
        )
    )

    client = AdzunaClient(app_id="id", app_key="key")
    listings = client.search(SearchCriteria(keywords="python"))

    assert len(listings) == 1
    assert listings[0].company == "Acme"
    assert listings[0].source == "adzuna"


@respx.mock
def test_search_raises_on_http_error():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(403))

    client = AdzunaClient(app_id="bad", app_key="bad")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_invalid_json():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text="not json"))

    client = AdzunaClient(app_id="id", app_key="key")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_company_field_wrong_shape():
    # Test for wrong-shaped-but-valid-JSON: company is a string instead of an object
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Développeur Python",
                        "company": "Acme",  # Wrong type: should be {"display_name": "..."}
                        "location": {"display_name": "Paris"},
                        "description": "Nous recherchons...",
                        "redirect_url": "https://www.adzuna.fr/land/ad/123",
                    }
                ]
            },
        )
    )

    client = AdzunaClient(app_id="id", app_key="key")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))
