from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PersonalizationRequestLog(Base):
    """Append-only log of successful CV/lettre generations.

    Used only to enforce the personalization rate limit
    (app.rate_limit.limiter.check_personalization_rate_limit). Kept separate
    from PersonalizedDocument, which stores at most one row per
    (diagnostic, kind) and is overwritten on regeneration - a row count on
    that table would not reflect how many generations actually happened.
    """

    __tablename__ = "personalization_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
