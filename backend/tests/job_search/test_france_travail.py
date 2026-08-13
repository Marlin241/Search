import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.france_travail import (
    COMMUNES_URL,
    SEARCH_URL,
    TOKEN_URL,
    FranceTravailClient,
)
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok123", "expires_in": 1499}
        )
    )
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "resultats": [
                    {
                        "intitule": "Développeur Python",
                        "entreprise": {"nom": "Acme"},
                        "lieuTravail": {"libelle": "Paris"},
                        "description": "Nous recherchons un développeur Python expérimenté.",
                        "origineOffre": {
                            "urlOrigine": "https://candidat.francetravail.fr/offres/123"
                        },
                    }
                ]
            },
        )
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    listings = client.search(SearchCriteria(keywords="python"))

    assert len(listings) == 1
    assert listings[0].title == "Développeur Python"
    assert listings[0].company == "Acme"
    assert listings[0].source == "france_travail"
    assert listings[0].ats_type is None


@respx.mock
def test_search_uppercases_contract_type():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    search_route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"resultats": []})
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    client.search(SearchCriteria(keywords="python", contract_type="cdi"))

    assert search_route.calls[0].request.url.params["typeContrat"] == "CDI"


@respx.mock
def test_search_raises_on_auth_failure():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(401, json={"error": "invalid_client"})
    )

    client = FranceTravailClient(client_id="bad", client_secret="bad")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_search_failure():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(500))

    client = FranceTravailClient(client_id="id", client_secret="secret")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_invalid_json():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text="not json"))

    client = FranceTravailClient(client_id="id", client_secret="secret")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_token_response_wrong_shape():
    # Token response is valid JSON but is an array instead of an object
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json=["not", "an", "object"])
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_search_response_not_object():
    # Search response is valid JSON but is an array instead of an object
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json=[{"title": "job"}])
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_resolves_city_name_to_commune_code():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    geocode_route = respx.get(COMMUNES_URL).mock(
        return_value=httpx.Response(200, json=[{"code": "75056"}])
    )
    search_route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"resultats": []})
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    client.search(SearchCriteria(keywords="python", location="Paris"))

    assert geocode_route.calls[0].request.url.params["nom"] == "Paris"
    assert search_route.calls[0].request.url.params["commune"] == "75056"


@respx.mock
def test_search_treats_france_as_nationwide():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    search_route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"resultats": []})
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    client.search(SearchCriteria(keywords="python", location="France"))

    assert "commune" not in search_route.calls[0].request.url.params


@respx.mock
def test_search_accepts_insee_code_directly():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    geocode_route = respx.get(COMMUNES_URL).mock(
        return_value=httpx.Response(200, json=[])
    )
    search_route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"resultats": []})
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    client.search(SearchCriteria(keywords="python", location="75056"))

    assert not geocode_route.calls
    assert search_route.calls[0].request.url.params["commune"] == "75056"


@respx.mock
def test_search_drops_location_filter_when_city_not_found():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    respx.get(COMMUNES_URL).mock(return_value=httpx.Response(200, json=[]))
    search_route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"resultats": []})
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    client.search(SearchCriteria(keywords="python", location="Villequinexistepas"))

    assert "commune" not in search_route.calls[0].request.url.params


@respx.mock
def test_search_drops_location_filter_when_geocoding_service_unreachable():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    respx.get(COMMUNES_URL).mock(return_value=httpx.Response(500))
    search_route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"resultats": []})
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    client.search(SearchCriteria(keywords="python", location="Paris"))

    assert "commune" not in search_route.calls[0].request.url.params


@respx.mock
def test_search_raises_on_search_response_wrong_field_type():
    # Search response has entreprise as string instead of object
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123"})
    )
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "resultats": [
                    {
                        "intitule": "Développeur",
                        "entreprise": "not an object",  # Wrong type: should be {"nom": "..."}
                        "lieuTravail": {"libelle": "Paris"},
                    }
                ]
            },
        )
    )

    client = FranceTravailClient(client_id="id", client_secret="secret")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))
