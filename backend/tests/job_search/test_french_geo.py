import httpx
import pytest
import respx

from app.job_search.french_geo import (
    COMMUNES_URL,
    GeoLookupUnavailable,
    lookup_commune,
)


@respx.mock
def test_returns_commune_when_the_name_matches():
    respx.get(COMMUNES_URL).mock(
        return_value=httpx.Response(200, json=[{"nom": "Paris", "code": "75056"}])
    )
    with httpx.Client() as c:
        commune = lookup_commune("Paris", c, fields="code")
    assert commune == {"nom": "Paris", "code": "75056"}


@respx.mock
def test_rejects_a_fuzzy_name_mismatch():
    # geo.api.gouv.fr answers "Thiès" (Senegal) with "Thiescourt" (Oise).
    respx.get(COMMUNES_URL).mock(
        return_value=httpx.Response(200, json=[{"nom": "Thiescourt", "code": "60632"}])
    )
    with httpx.Client() as c:
        assert lookup_commune("Thiès", c, fields="code") is None


@respx.mock
def test_accent_and_case_insensitive_name_match():
    respx.get(COMMUNES_URL).mock(
        return_value=httpx.Response(200, json=[{"nom": "Nîmes", "code": "30189"}])
    )
    with httpx.Client() as c:
        assert lookup_commune("nimes", c, fields="code") is not None


@respx.mock
def test_returns_none_on_empty_registry_response():
    respx.get(COMMUNES_URL).mock(return_value=httpx.Response(200, json=[]))
    with httpx.Client() as c:
        assert lookup_commune("Dakar", c, fields="code") is None


@respx.mock
def test_raises_on_transport_error():
    respx.get(COMMUNES_URL).mock(return_value=httpx.Response(503))
    with httpx.Client() as c, pytest.raises(GeoLookupUnavailable):
        lookup_commune("Paris", c, fields="code")
