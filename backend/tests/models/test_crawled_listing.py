from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.crawled_listing import CrawledListing


def test_crawled_listing_persists_with_defaults(db_session):
    now = datetime(2026, 8, 28, tzinfo=UTC).replace(tzinfo=None)
    row = CrawledListing(
        url="https://www.emploidakar.com/offre-demploi/x/",
        source="emploi_dakar",
        title="Développeur",
        first_seen_at=now,
        last_seen_at=now,
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(CrawledListing).one()
    assert fetched.is_active is True
    assert fetched.is_remote is False
    assert fetched.missed_crawls == 0
    assert fetched.snippet == ""


def test_crawled_listing_url_is_unique(db_session):
    now = datetime(2026, 8, 28, tzinfo=UTC).replace(tzinfo=None)
    for _ in range(2):
        db_session.add(
            CrawledListing(
                url="https://dup/",
                source="s",
                title="t",
                first_seen_at=now,
                last_seen_at=now,
            )
        )
    with pytest.raises(IntegrityError):
        db_session.commit()
