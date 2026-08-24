from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.diagnostic import Diagnostic


class PersonalizedDocument(Base):
    __tablename__ = "personalized_documents"
    __table_args__ = (
        UniqueConstraint(
            "diagnostic_id", "kind", name="uq_personalized_document_diagnostic_kind"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostics.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Structured content behind the rendered PDF (currently: a CV's
    # RewrittenCv.model_dump()) so the Phase 4 CV editor can re-render via
    # POST /saved-jobs/{id}/cv/render-preview without a new LLM call.
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ats_score_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ats_score_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    diagnostic: Mapped["Diagnostic"] = relationship()
