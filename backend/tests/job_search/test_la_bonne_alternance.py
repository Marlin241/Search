import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.la_bonne_alternance import COMMUNES_URL, SEARCH_URL, LaBonneAlternanceClient
from app.job_search.schemas import SearchCriteria


def _job(title: str = "Développeur en alternance") -> dict:
    return {
        "offer": {"title": title, "description": "Description de l'offre."},
        "workplace": {"name": "Acme", "location": {"address": "Paris"}},
        "apply": {"url": "https://labonnealternance.apprentissage.beta.gouv.fr/offres/123"},
    }


@respx.mock
def test_search_returns_normalized_listings():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"jobs": [_job()]}))

    client = LaBonneAlternanceClient(api_key="key123")
    listings = client.search(SearchCriteria(keywords="alternance"))

    assert len(listings) == 1
    assert listings[0].title == "Développeur en alternance"
    assert listings[0].company == "Acme"
    assert listings[0].location == "Paris"
    assert listings[0].url == "https://labonnealternance.apprentissage.beta.gouv.fr/offres/123"
    assert listings[0].source == "la_bonne_alternance"
    assert listings[0].ats_type is None


@respx.mock
def test_search_sends_api_key_as_bearer_token():
    search_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"jobs": []}))

    client = LaBonneAlternanceClient(api_key="key123")
    client.search(SearchCriteria(keywords="alternance"))

    assert search_route.calls[0].request.headers["Authorization"] == "Bearer key123"


@respx.mock
def test_search_filters_out_jobs_not_matching_keyword():
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"jobs": [_job("Développeur"), _job("Comptable")]})
    )

    client = LaBonneAlternanceClient(api_key="key123")
    listings = client.search(SearchCriteria(keywords="développeur"))

    assert [listing.title for listing in listings] == ["Développeur"]


@respx.mock
def test_search_resolves_city_name_to_coordinates():
    geocode_route = respx.get(COMMUNES_URL).mock(
        return_value=httpx.Response(200, json=[{"centre": {"coordinates": [2.3522, 48.8566]}}])
    )
    search_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"jobs": []}))

    client = LaBonneAlternanceClient(api_key="key123")
    client.search(SearchCriteria(keywords="alternance", location="Paris"))

    assert geocode_route.calls[0].request.url.params["nom"] == "Paris"
    assert search_route.calls[0].request.url.params["longitude"] == "2.3522"
    assert search_route.calls[0].request.url.params["latitude"] == "48.8566"
    assert search_route.calls[0].request.url.params["radius"] == "30"


@respx.mock
def test_search_treats_france_as_nationwide():
    search_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"jobs": []}))

    client = LaBonneAlternanceClient(api_key="key123")
    client.search(SearchCriteria(keywords="alternance", location="France"))

    assert "latitude" not in search_route.calls[0].request.url.params


@respx.mock
def test_search_drops_location_filter_when_city_not_found():
    respx.get(COMMUNES_URL).mock(return_value=httpx.Response(200, json=[]))
    search_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"jobs": []}))

    client = LaBonneAlternanceClient(api_key="key123")
    client.search(SearchCriteria(keywords="alternance", location="Dakar"))

    assert "latitude" not in search_route.calls[0].request.url.params


@respx.mock
def test_search_drops_location_filter_when_geocoding_service_unreachable():
    respx.get(COMMUNES_URL).mock(return_value=httpx.Response(500))
    search_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"jobs": []}))

    client = LaBonneAlternanceClient(api_key="key123")
    client.search(SearchCriteria(keywords="alternance", location="Paris"))

    assert "latitude" not in search_route.calls[0].request.url.params


@respx.mock
def test_search_raises_on_http_error():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(500))

    client = LaBonneAlternanceClient(api_key="key123")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="alternance"))


@respx.mock
def test_search_raises_on_invalid_json():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text="not json"))

    client = LaBonneAlternanceClient(api_key="key123")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="alternance"))


@respx.mock
def test_search_raises_on_response_wrong_field_type():
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200, json={"jobs": [{"offer": {"title": "Développeur"}, "workplace": "not an object"}]}
        )
    )

    client = LaBonneAlternanceClient(api_key="key123")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="Développeur"))
