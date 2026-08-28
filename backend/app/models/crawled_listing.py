from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CrawledListing(Base):
    """A job offer discovered on a crawled local job board (no search API of
    its own). Populated by app.job_search.crawl_runner.run_crawl on a
    schedule and read back at search time by
    app.job_search.crawled_listings.CrawledListingClient. Keyed by `url`;
    `is_active` goes False once `missed_crawls` reaches
    settings.crawl_deactivate_after consecutive absences from a crawl."""

    __tablename__ = "crawled_listing"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(
        String(2048), unique=True, nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snippet: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    salary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_remote: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    missed_crawls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
