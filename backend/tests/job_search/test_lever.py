import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.lever import LeverJobBoardClient
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings_for_followed_companies():
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "text": "Développeur Python",
                    "categories": {"location": "Paris"},
                    "descriptionPlain": "Nous recherchons un développeur Python.",
                    "hostedUrl": "https://jobs.lever.co/acme/1",
                },
                {
                    "text": "Chef de projet",
                    "categories": {"location": "Lyon"},
                    "descriptionPlain": "Gestion de projet.",
                    "hostedUrl": "https://jobs.lever.co/acme/2",
                },
            ],
        )
    )

    client = LeverJobBoardClient()
    listings = client.search(SearchCriteria(keywords="python", followed_companies=["acme"]))

    assert len(listings) == 1
    assert listings[0].title == "Développeur Python"
    assert listings[0].ats_type == "lever"
    assert listings[0].location == "Paris"


@respx.mock
def test_search_with_no_keyword_returns_all_jobs():
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "text": "Chef de projet",
                    "categories": {"location": "Lyon"},
                    "descriptionPlain": "Test",
                    "hostedUrl": "https://jobs.lever.co/acme/2",
                },
            ],
        )
    )

    client = LeverJobBoardClient()
    listings = client.search(SearchCriteria(keywords="", followed_companies=["acme"]))

    assert len(listings) == 1


@respx.mock
def test_search_raises_on_http_error():
    respx.get("https://api.lever.co/v0/postings/unknown-co").mock(return_value=httpx.Response(404))

    client = LeverJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python", followed_companies=["unknown-co"]))


def test_search_with_no_followed_companies_returns_empty_list():
    client = LeverJobBoardClient()
    assert client.search(SearchCriteria(keywords="python", followed_companies=[])) == []


@respx.mock
def test_search_raises_on_categories_field_wrong_shape():
    """Test for wrong-shaped-but-valid-JSON: categories is a string instead of an object"""
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "text": "Développeur Python",
                    "categories": "Paris",  # Wrong type: should be {"location": "..."}
                    "descriptionPlain": "Test",
                    "hostedUrl": "https://jobs.lever.co/acme/1",
                }
            ],
        )
    )

    client = LeverJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python", followed_companies=["acme"]))
