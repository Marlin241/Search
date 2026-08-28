import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.jobicy import JobicyClient
from app.job_search.schemas import SearchCriteria

API_URL = "https://jobicy.com/api/v2/remote-jobs"

_PAYLOAD = {
    "jobs": [
        {
            "id": 1,
            "url": "https://jobicy.com/jobs/acme-python-developer",
            "jobTitle": "Python Developer",
            "companyName": "Acme",
            "jobGeo": "Anywhere",
            "jobType": ["full-time"],
            "jobDescription": "<p>Build things</p>",
            "pubDate": "2026-08-20 10:00:00",
            "salaryMin": 90000,
            "salaryMax": 120000,
            "salaryCurrency": "USD",
        },
        {
            "id": 2,
            "url": "https://jobicy.com/jobs/acme-designer",
            "jobTitle": "Product Designer",
            "companyName": "Acme",
            "jobGeo": "Anywhere",
            "jobType": ["full-time"],
            "jobDescription": "<p>Design things</p>",
            "pubDate": "2026-08-19 10:00:00",
        },
    ]
}


@respx.mock
def test_search_returns_keyword_matched_listings():
    respx.get(API_URL).mock(return_value=httpx.Response(200, json=_PAYLOAD))
    client = JobicyClient()
    listings = client.search(SearchCriteria(keywords="python", remote=True))
    assert [lst.title for lst in listings] == ["Python Developer"]
    assert listings[0].source == "jobicy"
    assert listings[0].is_remote is True
    assert listings[0].salary == "90000 - 120000 USD"
    assert listings[0].posted_at is not None
    assert "<p>" not in listings[0].snippet


@respx.mock
def test_returns_empty_without_network_when_located_and_not_remote():
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json=_PAYLOAD))
    client = JobicyClient()
    result = client.search(SearchCriteria(keywords="python", location="Dakar"))
    assert result == []
    assert route.call_count == 0


@respx.mock
def test_queries_when_no_location_even_if_remote_flag_absent():
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json=_PAYLOAD))
    client = JobicyClient()
    client.search(SearchCriteria(keywords="python"))
    assert route.call_count == 1


@respx.mock
def test_raises_on_http_error():
    respx.get(API_URL).mock(return_value=httpx.Response(502))
    with pytest.raises(JobSearchSourceError):
        JobicyClient().search(SearchCriteria(keywords="python", remote=True))


@respx.mock
def test_raises_on_malformed_json():
    respx.get(API_URL).mock(return_value=httpx.Response(200, text="nope"))
    with pytest.raises(JobSearchSourceError):
        JobicyClient().search(SearchCriteria(keywords="python", remote=True))
