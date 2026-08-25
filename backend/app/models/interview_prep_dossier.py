from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.saved_job import SavedJob


class InterviewPrepDossier(Base):
    __tablename__ = "interview_prep_dossiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    saved_job_id: Mapped[int] = mapped_column(
        ForeignKey("saved_jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    persona: Mapped[str] = mapped_column(String(50), nullable=False)
    extra_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    web_search_used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dossier_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # Citations captured during Phase A (web search) - null when
    # web_search_used is False, since there is nothing to cite.
    sources_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    saved_job: Mapped["SavedJob"] = relationship()
