from app.job_search.dependencies import get_job_search_clients


def test_crawled_source_is_registered():
    get_job_search_clients.cache_clear()
    assert "crawled" in get_job_search_clients()
