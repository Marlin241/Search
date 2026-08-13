import httpx
import respx

from app.job_search.background_discovery import (
    create_pending_search,
    get_discovery_result,
    run_discovery,
)
from app.job_search.errors import JobSearchSourceError
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.lever import LeverJobBoardClient
from app.job_search.schemas import SearchCriteria
from app.models.company_ats_mapping import CompanyAtsMapping


def test_create_pending_search_with_no_unknown_companies_is_immediately_done():
    search_id = create_pending_search(user_id=1, has_unknown_companies=False)

    done, new_listings = get_discovery_result(search_id, user_id=1)

    assert done is True
    assert new_listings == []


def test_create_pending_search_with_unknown_companies_is_not_done_yet():
    search_id = create_pending_search(user_id=1, has_unknown_companies=True)

    done, _ = get_discovery_result(search_id, user_id=1)

    assert done is False


def test_get_discovery_result_for_unknown_search_id_returns_done_true_empty():
    done, new_listings = get_discovery_result("does-not-exist", user_id=1)

    assert done is True
    assert new_listings == []


def test_get_discovery_result_for_wrong_user_returns_done_true_empty():
    search_id = create_pending_search(user_id=1, has_unknown_companies=True)

    done, new_listings = get_discovery_result(search_id, user_id=2)

    assert done is True
    assert new_listings == []


@respx.mock
def test_run_discovery_saves_confirmed_mapping_and_delivers_listings(db_session):
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Ingénieur backend",
                        "location": {"name": "Paris"},
                        "content": "<p>Poste chez Acme.</p>",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    }
                ]
            },
        )
    )

    search_id = create_pending_search(user_id=1, has_unknown_companies=True)
    run_discovery(
        search_id,
        lambda: db_session,
        ["Acme"],
        SearchCriteria(keywords="backend"),
        GreenhouseJobBoardClient(),
        LeverJobBoardClient(),
    )

    done, new_listings = get_discovery_result(search_id, user_id=1)
    assert done is True
    assert len(new_listings) == 1
    assert new_listings[0].title == "Ingénieur backend"

    mapping = (
        db_session.query(CompanyAtsMapping)
        .filter(CompanyAtsMapping.company_name == "acme")
        .first()
    )
    assert mapping.source == "greenhouse"


@respx.mock
def test_run_discovery_does_not_cache_indeterminate_detection(db_session):
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        side_effect=httpx.ConnectError("down")
    )
    respx.get("https://api.lever.co/v0/postings/acme").mock(
        return_value=httpx.Response(404)
    )

    search_id = create_pending_search(user_id=1, has_unknown_companies=True)
    run_discovery(
        search_id,
        lambda: db_session,
        ["Acme"],
        SearchCriteria(keywords="backend"),
        GreenhouseJobBoardClient(),
        LeverJobBoardClient(),
    )

    done, new_listings = get_discovery_result(search_id, user_id=1)
    assert done is True
    assert new_listings == []
    assert (
        db_session.query(CompanyAtsMapping)
        .filter(CompanyAtsMapping.company_name == "acme")
        .first()
        is None
    )


@respx.mock
def test_run_discovery_continues_after_a_listings_fetch_failure(
    db_session, monkeypatch
):
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(200, json={})
    )
    respx.get("https://boards-api.greenhouse.io/v1/boards/globex/jobs").mock(
        return_value=httpx.Response(200, json={})
    )

    greenhouse_client = GreenhouseJobBoardClient()

    original_search = greenhouse_client.search

    def flaky_search(criteria, company_slugs):
        if company_slugs == ["acme"]:
            raise JobSearchSourceError("boom")
        return original_search(criteria, company_slugs)

    monkeypatch.setattr(greenhouse_client, "search", flaky_search)

    search_id = create_pending_search(user_id=1, has_unknown_companies=True)
    run_discovery(
        search_id,
        lambda: db_session,
        ["Acme", "Globex"],
        SearchCriteria(keywords=""),
        greenhouse_client,
        LeverJobBoardClient(),
    )

    done, _ = get_discovery_result(search_id, user_id=1)
    assert done is True
    # Both companies still get their mapping saved despite Acme's listings fetch failing
    names = {row.company_name for row in db_session.query(CompanyAtsMapping).all()}
    assert names == {"acme", "globex"}
