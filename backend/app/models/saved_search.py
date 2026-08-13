from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utcnow


class SavedSearch(Base):
    """Une recherche sauvegardée par utilisateur (relation un-à-un), traitée
    quotidiennement par app.job_search.daily_search.run_daily_search."""

    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    keywords: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remote: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    exclude_keywords: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Europe/Paris"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
