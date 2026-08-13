from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PrefilledFormRequestLog(Base):
    """Append-only log of prefilled-form previews, used only to enforce the
    preview rate limit (app.rate_limit.limiter.check_prefilled_form_rate_limit).

    GET /applications/{id}/prefilled-form calls the CustomFieldAnswerer LLM
    on every request, so it needs an LLM-cost rate limit of its own like
    every other LLM-calling endpoint. It can't reuse an existing counter:
    the endpoint creates no Diagnostic and no PersonalizedDocument row, so
    there is nothing else per-request to count."""

    __tablename__ = "prefilled_form_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
