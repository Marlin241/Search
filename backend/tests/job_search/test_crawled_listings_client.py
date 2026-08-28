from datetime import datetime

from app.job_search.crawled_listings import CrawledListingClient
from app.job_search.schemas import SearchCriteria
from app.models.crawled_listing import CrawledListing


def _seed(db_session):
    rows = [
        CrawledListing(
            url="https://x/1",
            source="emploi_dakar",
            title="Développeur Python",
            snippet="Django, API REST",
            location="Dakar, Sénégal",
            contract_type="CDI",
            is_remote=False,
            first_seen_at=datetime(2026, 8, 1),
            last_seen_at=datetime(2026, 8, 1),
            posted_at=datetime(2026, 8, 1),
            is_active=True,
        ),
        CrawledListing(
            url="https://x/2",
            source="emploi_dakar",
            title="Comptable",
            snippet="Sage, fiscalité",
            location="Thiès",
            contract_type="CDD",
            is_remote=False,
            first_seen_at=datetime(2026, 8, 2),
            last_seen_at=datetime(2026, 8, 2),
            posted_at=datetime(2026, 8, 2),
            is_active=True,
        ),
        CrawledListing(
            url="https://x/3",
            source="emploi_dakar",
            title="Développeur backend (télétravail)",
            snippet="Node",
            location="Remote",
            contract_type="CDI",
            is_remote=True,
            first_seen_at=datetime(2026, 8, 3),
            last_seen_at=datetime(2026, 8, 3),
            posted_at=datetime(2026, 8, 3),
            is_active=True,
        ),
        CrawledListing(
            url="https://x/old",
            source="emploi_dakar",
            title="Développeur retiré",
            snippet="x",
            location="Dakar",
            is_remote=False,
            first_seen_at=datetime(2026, 7, 1),
            last_seen_at=datetime(2026, 7, 1),
            is_active=False,
        ),
    ]
    for row in rows:
        db_session.add(row)
    db_session.commit()


def test_search_matches_keyword_in_title_or_snippet(db_session):
    _seed(db_session)
    client = CrawledListingClient(session_factory=lambda: db_session)
    results = client.search(SearchCriteria(keywords="développeur"))
    assert {r.url for r in results} == {"https://x/1", "https://x/3"}
    assert all(r.source == "emploi_dakar" for r in results)


def test_search_filters_by_location_accent_insensitive(db_session):
    _seed(db_session)
    client = CrawledListingClient(session_factory=lambda: db_session)
    results = client.search(SearchCriteria(keywords="développeur", location="senegal"))
    assert {r.url for r in results} == {"https://x/1"}


def test_search_remote_flag_restricts_to_remote_rows(db_session):
    _seed(db_session)
    client = CrawledListingClient(session_factory=lambda: db_session)
    results = client.search(SearchCriteria(keywords="développeur", remote=True))
    assert {r.url for r in results} == {"https://x/3"}


def test_search_contract_type_filter(db_session):
    _seed(db_session)
    client = CrawledListingClient(session_factory=lambda: db_session)
    results = client.search(SearchCriteria(keywords="comptable", contract_type="CDD"))
    assert {r.url for r in results} == {"https://x/2"}


def test_search_orders_by_recency_desc(db_session):
    _seed(db_session)
    client = CrawledListingClient(session_factory=lambda: db_session)
    results = client.search(SearchCriteria(keywords="développeur"))
    assert [r.url for r in results] == ["https://x/3", "https://x/1"]
