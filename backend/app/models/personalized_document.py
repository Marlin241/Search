from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PersonalizedDocument(Base):
    __tablename__ = "personalized_documents"
    __table_args__ = (
        UniqueConstraint("diagnostic_id", "kind", name="uq_personalized_document_diagnostic_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostics.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    diagnostic: Mapped["Diagnostic"] = relationship()
