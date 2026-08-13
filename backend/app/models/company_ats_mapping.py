from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompanyAtsMapping(Base):
    """Cache of which Greenhouse/Lever board (if any) a company uses, keyed
    by normalized company name (app.job_search.discovery.normalize_company_name).
    Populated automatically by app.job_search.background_discovery — never
    written to by the user. Entries are never expired or re-checked: see
    docs/superpowers/specs/2026-08-11-decouverte-entreprises-design.md."""

    __tablename__ = "company_ats_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    slug: Mapped[str | None] = mapped_column(String, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
