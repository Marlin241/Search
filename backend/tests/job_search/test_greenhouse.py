import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings_for_given_companies():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Développeur Python",
                        "location": {"name": "Paris"},
                        "content": "<p>Nous recherchons un <b>développeur Python</b>.</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    },
                    {
                        "title": "Chef de projet",
                        "location": {"name": "Lyon"},
                        "content": "<p>Gestion de projet.</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
                    },
                ]
            },
        )
    )

    client = GreenhouseJobBoardClient()
    listings = client.search(SearchCriteria(keywords="python"), ["acme"])

    assert len(listings) == 1
    assert listings[0].title == "Développeur Python"
    assert listings[0].ats_type == "greenhouse"
    assert "développeur Python" in listings[0].snippet


@respx.mock
def test_snippet_is_plain_text_when_content_is_entity_encoded():
    # The real Greenhouse API returns `content` as HTML-entity-encoded text
    # ("&lt;p&gt;...") - it must be unescaped before the tags are stripped,
    # or the snippet ends up showing "<p>...</p>" literally.
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Python Engineer",
                        "location": {"name": "Remote"},
                        "content": (
                            "&lt;div class=&quot;body&quot;&gt;&lt;p&gt;We build "
                            "things with Python&lt;/p&gt;&lt;/div&gt;"
                        ),
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/9",
                    }
                ]
            },
        )
    )

    client = GreenhouseJobBoardClient()
    listings = client.search(SearchCriteria(keywords="python"), ["acme"])

    assert listings[0].snippet == "We build things with Python"
    assert "<" not in listings[0].snippet
    assert "&lt;" not in listings[0].snippet
    assert "<b>" not in listings[0].snippet


@respx.mock
def test_search_with_no_keyword_returns_all_jobs():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={"jobs": [{"title": "Chef de projet", "absolute_url": "https://x"}]},
        )
    )

    client = GreenhouseJobBoardClient()
    listings = client.search(SearchCriteria(keywords=""), ["acme"])

    assert len(listings) == 1


@respx.mock
def test_search_matches_french_keyword_against_english_only_title():
    respx.get("https://boards-api.greenhouse.io/v1/boards/wavemm1/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Endpoint Engineer",
                        "location": {"name": "Remote"},
                        "content": "<p>...</p>",
                        "absolute_url": "https://boards.greenhouse.io/wavemm1/jobs/1",
                    },
                    {
                        "title": "Accountant",
                        "location": {"name": "Dakar, Senegal"},
                        "content": "<p>...</p>",
                        "absolute_url": "https://boards.greenhouse.io/wavemm1/jobs/2",
                    },
                ]
            },
        )
    )

    client = GreenhouseJobBoardClient()
    listings = client.search(SearchCriteria(keywords="ingénieur"), ["wavemm1"])

    assert [listing.title for listing in listings] == ["Endpoint Engineer"]


@respx.mock
def test_search_raises_on_http_error():
    respx.get("https://boards-api.greenhouse.io/v1/boards/unknown-co/jobs").mock(
        return_value=httpx.Response(404)
    )

    client = GreenhouseJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"), ["unknown-co"])


def test_search_with_no_company_slugs_returns_empty_list():
    client = GreenhouseJobBoardClient()
    assert client.search(SearchCriteria(keywords="python"), []) == []


@respx.mock
def test_search_raises_on_location_field_wrong_shape():
    """Test for wrong-shaped-but-valid-JSON: location is a string instead of an object"""
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Développeur Python",
                        "location": "Paris",  # Wrong type: should be {"name": "..."}
                        "content": "<p>Test</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    }
                ]
            },
        )
    )

    client = GreenhouseJobBoardClient()
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"), ["acme"])
