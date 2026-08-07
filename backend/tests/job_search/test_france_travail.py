import httpx
import pytest
import respx

from app.job_search.errors import JobSearchSourceError
from app.job_search.france_travail import TOKEN_URL, SEARCH_URL, FranceTravailClient
from app.job_search.schemas import SearchCriteria


@respx.mock
def test_search_returns_normalized_listings():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 1499}))
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
                        "origineOffre": {"urlOrigine": "https://candidat.francetravail.fr/offres/123"},
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
def test_search_raises_on_auth_failure():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))

    client = FranceTravailClient(client_id="bad", client_secret="bad")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_search_failure():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok123"}))
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(500))

    client = FranceTravailClient(client_id="id", client_secret="secret")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))


@respx.mock
def test_search_raises_on_invalid_json():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok123"}))
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text="not json"))

    client = FranceTravailClient(client_id="id", client_secret="secret")
    with pytest.raises(JobSearchSourceError):
        client.search(SearchCriteria(keywords="python"))
