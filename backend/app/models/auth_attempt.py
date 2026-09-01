from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuthAttempt(Base):
    """Append-only log of auth attempts, used only by
    app.rate_limit.auth_throttle to rate-limit /auth/*."""

    __tablename__ = "auth_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    identifier: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )
