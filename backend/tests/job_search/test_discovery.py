import httpx
import respx

from app.job_search.discovery import (
    detect_company_ats,
    extract_unique_companies,
    generate_slug_candidates,
    normalize_company_name,
)
from app.job_search.schemas import JobListing


def _listing(company: str, url: str = "https://example.com/1") -> JobListing:
    return JobListing(
        title="Développeur",
        company=company,
        location=None,
        snippet="",
        url=url,
        source="france_travail",
        ats_type=None,
    )


def test_normalize_company_name_strips_accents_and_apostrophes():
    assert normalize_company_name("L'Oréal") == "loreal"


def test_normalize_company_name_lowercases_and_trims():
    assert normalize_company_name("  Acme Corp  ") == "acme corp"


def test_generate_slug_candidates_single_word():
    assert generate_slug_candidates("loreal") == ["loreal"]


def test_generate_slug_candidates_multi_word():
    assert generate_slug_candidates("la poste") == ["laposte", "la-poste"]


def test_generate_slug_candidates_empty_string_returns_no_candidates():
    assert generate_slug_candidates("") == []


@respx.mock
def test_detect_company_ats_finds_greenhouse_on_first_candidate():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(200, json={})
    )

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is True
    assert result.source == "greenhouse"
    assert result.slug == "acme"


@respx.mock
def test_detect_company_ats_falls_back_to_lever_when_greenhouse_404s():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is True
    assert result.source == "lever"
    assert result.slug == "acme"


@respx.mock
def test_detect_company_ats_confirmed_not_found_when_all_candidates_404():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(404)
    )

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is True
    assert result.source is None
    assert result.slug is None


@respx.mock
def test_detect_company_ats_not_confirmed_on_network_error():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        side_effect=httpx.ConnectError("down")
    )
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(404)
    )

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is False


@respx.mock
def test_detect_company_ats_not_confirmed_on_server_error():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(500)
    )
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(404)
    )

    result = detect_company_ats("Acme", httpx.Client())

    assert result.confirmed is False


def test_extract_unique_companies_dedupes_case_insensitively_preserving_first_seen_casing():
    listings = [
        _listing("Acme", "https://example.com/1"),
        _listing("ACME", "https://example.com/2"),
        _listing("Globex", "https://example.com/3"),
    ]

    assert extract_unique_companies(listings) == ["Acme", "Globex"]


def test_extract_unique_companies_skips_blank_company_names():
    listings = [
        _listing("", "https://example.com/1"),
        _listing("Acme", "https://example.com/2"),
    ]

    assert extract_unique_companies(listings) == ["Acme"]
