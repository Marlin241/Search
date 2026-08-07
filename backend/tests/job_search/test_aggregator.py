import pytest

from app.job_search.aggregator import search_jobs
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria

_LISTING = JobListing(
    title="Développeur Python",
    company="Acme",
    location="Paris",
    snippet="...",
    url="https://example.com/1",
    source="fake",
    ats_type=None,
)


class WorkingClient:
    def search(self, criteria):
        return [_LISTING]


class FailingClient:
    def search(self, criteria):
        raise JobSearchSourceError("boom")


def test_search_jobs_merges_results_from_all_sources():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python"), {"source_a": WorkingClient(), "source_b": WorkingClient()}
    )
    assert len(listings) == 2
    assert unavailable == []


def test_search_jobs_omits_failing_source_without_failing_the_whole_search():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python"), {"source_a": WorkingClient(), "source_b": FailingClient()}
    )
    assert len(listings) == 1
    assert unavailable == ["source_b"]


def test_search_jobs_with_all_sources_failing_returns_empty_listings():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python"), {"source_a": FailingClient(), "source_b": FailingClient()}
    )
    assert listings == []
    assert set(unavailable) == {"source_a", "source_b"}
