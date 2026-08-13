import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.lever import LeverJobBoardClient
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings_for_given_companies():
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
    listings = client.search(SearchCriteria(keywords="python"), ["acme"])

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
    listings = client.search(SearchCriteria(keywords=""), ["acme"])

    assert len(listings) == 1


@respx.mock
def test_search_matches_french_keyword_against_english_only_title():
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "text": "Software Engineer",
                    "categories": {"location": "Remote"},
                    "descriptionPlain": "Test",
                    "hostedUrl": "https://jobs.lever.co/acme/1",
                },
                {
                    "text": "Accountant",
                    "categories": {"location": "Dakar"},
                    "descriptionPlain": "Test",
                    "hostedUrl": "https://jobs.lever.co/acme/2",
                },
            ],
        )
    )

    client = LeverJobBoardClient()
    listings = client.search(SearchCriteria(keywords="développeur"), ["acme"])

    assert [listing.title for listing in listings] == ["Software Engineer"]


@respx.mock
def test_search_raises_on_http_error():
    respx.get("https://api.lever.co/v0/postings/unknown-co").mock(
        return_value=httpx.Response(404)
    )

    client = LeverJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"), ["unknown-co"])


def test_search_with_no_company_slugs_returns_empty_list():
    client = LeverJobBoardClient()
    assert client.search(SearchCriteria(keywords="python"), []) == []


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
        client.search(SearchCriteria(keywords="python"), ["acme"])
