from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompanyResearchCache(Base):
    """Cache of web-search-derived company facts/recent news, keyed by
    normalized company name (app.job_search.discovery.normalize_company_name).
    Populated by app.interview_prep.jobs.run_interview_prep_job whenever a
    user opts into web search for a company not yet cached (or whose cache
    entry is stale). Unlike CompanyAtsMapping, entries here DO expire - see
    app.interview_prep.jobs's ~7 day TTL check - since company news/facts
    go stale in a way an ATS board slug does not."""

    __tablename__ = "company_research_caches"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    facts_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
