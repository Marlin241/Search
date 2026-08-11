from app.job_search.schemas import JobListing
from app.schemas.job_search import JobSearchDiscoveryResponse, JobSearchResponse


def test_job_search_response_includes_discovery_fields():
    response = JobSearchResponse(
        listings=[], unavailable_sources=[], search_id="abc123", discovery_pending=True
    )
    assert response.search_id == "abc123"
    assert response.discovery_pending is True


def test_job_search_discovery_response_shape():
    listing = JobListing(
        title="Développeur",
        company="Acme",
        location=None,
        snippet="",
        url="https://example.com/1",
        source="greenhouse",
        ats_type="greenhouse",
    )
    response = JobSearchDiscoveryResponse(done=True, new_listings=[listing])
    assert response.done is True
    assert response.new_listings[0].company == "Acme"
