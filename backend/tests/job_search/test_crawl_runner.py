from datetime import datetime

from app.job_search.crawl_runner import _apply
from app.job_search.crawlers.base import CrawledListingData
from app.models.crawled_listing import CrawledListing


def _data(url: str, title: str = "Dev") -> CrawledListingData:
    return CrawledListingData(
        url=url,
        title=title,
        company="Acme",
        location="Dakar",
        snippet="...",
        salary=None,
        contract_type="CDI",
        is_remote=False,
        posted_at=None,
    )


def test_apply_inserts_new_listings(db_session):
    counts = _apply(
        db_session,
        "emploi_dakar",
        [_data("https://x/1"), _data("https://x/2")],
        deactivate_after=3,
        suspicious_empty_threshold=5,
    )
    assert counts["inserted"] == 2
    rows = db_session.query(CrawledListing).all()
    assert {r.url for r in rows} == {"https://x/1", "https://x/2"}
    assert all(r.first_seen_at == r.last_seen_at for r in rows)


def test_apply_updates_and_resets_missed_crawls_on_reseen(db_session):
    old = datetime(2026, 1, 1)
    db_session.add(
        CrawledListing(
            url="https://x/1",
            source="emploi_dakar",
            title="Old",
            first_seen_at=old,
            last_seen_at=old,
            missed_crawls=2,
        )
    )
    db_session.commit()

    _apply(
        db_session,
        "emploi_dakar",
        [_data("https://x/1", title="New")],
        deactivate_after=3,
        suspicious_empty_threshold=5,
    )

    row = db_session.query(CrawledListing).one()
    assert row.title == "New"
    assert row.missed_crawls == 0
    assert row.is_active is True
    assert row.last_seen_at > old
    assert row.first_seen_at == old


def test_apply_deactivates_after_threshold_absences(db_session):
    now = datetime(2026, 8, 1)
    db_session.add(
        CrawledListing(
            url="https://x/gone",
            source="emploi_dakar",
            title="Gone",
            first_seen_at=now,
            last_seen_at=now,
            missed_crawls=2,
            is_active=True,
        )
    )
    db_session.commit()

    _apply(
        db_session,
        "emploi_dakar",
        [_data("https://x/other")],
        deactivate_after=3,
        suspicious_empty_threshold=0,
    )

    gone = db_session.query(CrawledListing).filter_by(url="https://x/gone").one()
    assert gone.missed_crawls == 3
    assert gone.is_active is False


def test_apply_skips_deactivation_when_crawl_suspiciously_empty(db_session):
    now = datetime(2026, 8, 1)
    for i in range(10):
        db_session.add(
            CrawledListing(
                url=f"https://x/{i}",
                source="emploi_dakar",
                title="t",
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
            )
        )
    db_session.commit()

    counts = _apply(
        db_session,
        "emploi_dakar",
        [],
        deactivate_after=3,
        suspicious_empty_threshold=5,
    )

    assert counts["skipped_deactivation"] == 1
    assert db_session.query(CrawledListing).filter_by(is_active=True).count() == 10
