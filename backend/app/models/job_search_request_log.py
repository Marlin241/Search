from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobSearchRequestLog(Base):
    """Append-only log of job searches, used only to enforce the search
    rate limit (app.rate_limit.limiter.check_job_search_rate_limit) — this
    protects France Travail/Adzuna's free-tier quotas, independently of the
    diagnostic/personalization LLM-cost rate limits."""

    __tablename__ = "job_search_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
