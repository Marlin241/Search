from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InterviewPrepRequestLog(Base):
    """Append-only log of successful interview-prep dossier generations.

    Kept separate from PersonalizationRequestLog: interview prep gets its
    own low cap (5/h) given the cost/latency of the two-phase pipeline
    (optional web search + structured extraction), independent of the
    CV/lettre combined cap.
    """

    __tablename__ = "interview_prep_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
