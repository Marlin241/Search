from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class SavedJob(Base):
    """A snapshot of a job listing the user opened into the workspace, taken
    at open time (title/company/location/snippet/source/salary) so it stays
    stable even if the upstream listing later disappears from search
    results. Anchors the 4-tab workspace and (later, Phase 7) the Kanban's
    "Sauvegardées" column."""

    __tablename__ = "saved_jobs"
    __table_args__ = (UniqueConstraint("user_id", "offer_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    offer_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    ats_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Backfilled by a background task after creation (app.routers.saved_jobs)
    # via app.offer_ingestion.scraper.scrape_offer - best effort, stays None
    # if the source page can't be scraped.
    full_offer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship()
