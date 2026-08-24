from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompatibilityRequestLog(Base):
    """Append-only log of compatibility-detail LLM calls, used only to
    enforce app.rate_limit.limiter.check_compatibility_detail_rate_limit."""

    __tablename__ = "compatibility_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
