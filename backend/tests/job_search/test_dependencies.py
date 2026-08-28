from app.job_search.dependencies import get_job_search_clients


def test_all_expected_sources_are_registered():
    get_job_search_clients.cache_clear()
    clients = get_job_search_clients()
    for key in (
        "france_travail",
        "adzuna",
        "la_bonne_alternance",
        "greenhouse",
        "lever",
        "reliefweb",
        "jobicy",
        "weworkremotely",
        "remoteok",
        "ngojobs",
    ):
        assert key in clients, key
