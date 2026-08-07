from app.job_search.schemas import JobListing, SearchCriteria


def test_search_criteria_defaults():
    criteria = SearchCriteria(keywords="développeur python")
    assert criteria.location is None
    assert criteria.exclude_keywords == []
    assert criteria.followed_companies == []


def test_job_listing_requires_core_fields():
    listing = JobListing(
        title="Développeur Python",
        company="Acme",
        location="Paris",
        snippet="Nous cherchons...",
        url="https://example.com/job/1",
        source="adzuna",
        ats_type=None,
    )
    assert listing.ats_type is None
    assert listing.source == "adzuna"
