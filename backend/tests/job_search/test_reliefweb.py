import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.reliefweb import ReliefWebClient
from app.job_search.schemas import SearchCriteria

API_URL = "https://api.reliefweb.int/v1/jobs"

_ONE_JOB = {
    "data": [
        {
            "id": "123",
            "fields": {
                "title": "Logisticien",
                "url": "https://api.reliefweb.int/v1/jobs/123",
                "url_alias": "https://reliefweb.int/job/123/logisticien",
                "source": [{"name": "ACTED"}],
                "country": [{"name": "Senegal"}],
                "city": [{"name": "Dakar"}],
                "date": {"created": "2026-08-20T00:00:00+00:00"},
                "body": "Nous recherchons un logisticien basé à Dakar.",
            },
        }
    ]
}


@respx.mock
def test_search_returns_normalized_listings():
    respx.get(API_URL).mock(return_value=httpx.Response(200, json=_ONE_JOB))
    client = ReliefWebClient(appname="ats-diagnostic", countries=["Senegal"])
    listings = client.search(SearchCriteria(keywords="logisticien"))
    assert len(listings) == 1
    lst = listings[0]
    assert lst.title == "Logisticien"
    assert lst.company == "ACTED"
    assert lst.location == "Dakar, Senegal"
    assert lst.url == "https://reliefweb.int/job/123/logisticien"
    assert lst.source == "reliefweb"
    assert lst.posted_at is not None


@respx.mock
def test_search_sends_keywords_and_country_filter():
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json={"data": []}))
    client = ReliefWebClient(
        appname="ats-diagnostic", countries=["Senegal", "Cameroon"]
    )
    client.search(SearchCriteria(keywords="wash"))
    request = route.calls.last.request
    assert "appname=ats-diagnostic" in str(request.url)
    assert "query%5Bvalue%5D=wash" in str(request.url)
    assert str(request.url).count("filter%5Bvalue%5D%5B%5D=") == 2


@respx.mock
def test_search_falls_back_to_url_when_no_alias():
    payload = {
        "data": [
            {
                "id": "9",
                "fields": {
                    "title": "T",
                    "url": "https://api.reliefweb.int/v1/jobs/9",
                    "source": [{"name": "X"}],
                    "country": [{"name": "Mali"}],
                    "date": {"created": "2026-08-01T00:00:00+00:00"},
                    "body": "b",
                },
            }
        ]
    }
    respx.get(API_URL).mock(return_value=httpx.Response(200, json=payload))
    client = ReliefWebClient(appname="a", countries=["Mali"])
    listings = client.search(SearchCriteria(keywords="t"))
    assert listings[0].url == "https://api.reliefweb.int/v1/jobs/9"


@respx.mock
def test_search_raises_on_http_error():
    respx.get(API_URL).mock(return_value=httpx.Response(500))
    client = ReliefWebClient(appname="a", countries=["Senegal"])
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="x"))


@respx.mock
def test_search_raises_on_malformed_json():
    respx.get(API_URL).mock(return_value=httpx.Response(200, text="<html>"))
    client = ReliefWebClient(appname="a", countries=["Senegal"])
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="x"))


@respx.mock
def test_search_skips_entries_missing_required_fields():
    payload = {"data": [{"id": "1", "fields": {"body": "no title, no url"}}]}
    respx.get(API_URL).mock(return_value=httpx.Response(200, json=payload))
    client = ReliefWebClient(appname="a", countries=["Senegal"])
    assert client.search(SearchCriteria(keywords="x")) == []
