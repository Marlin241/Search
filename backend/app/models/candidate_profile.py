from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    work_authorization: Mapped[str] = mapped_column(
        String(255), nullable=False, default=""
    )
    salary_expectation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cv_has_tables: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cv_has_multi_column: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cv_has_images: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cv_detected_sections: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    desired_job_titles: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    desired_locations: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    remote_preference: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    contract_types: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(nullable=True)
    salary_max: Mapped[int | None] = mapped_column(nullable=True)
    weekly_application_goal: Mapped[int | None] = mapped_column(nullable=True)
    profile_photo_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship()

    @property
    def full_name(self) -> str:
        """Derived, not stored - kept for the several read sites (PDF header,
        ATS form prefill) that only need a single display string, so they
        don't need to change now that first/last name are captured
        separately."""
        return f"{self.first_name} {self.last_name}".strip()
