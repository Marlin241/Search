from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.diagnostic import Diagnostic

APPLICATION_STATUS_EN_COURS = "en_cours"
APPLICATION_STATUS_SOUMISE_AUTO = "soumise_auto"
APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT = "a_soumettre_manuellement"
APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE = "soumise_manuelle_confirmee"
APPLICATION_STATUS_ECHEC_SOUMISSION = "echec_soumission"

# Kanban funnel stage - orthogonal to `status` above (submission mechanics).
# `status` tracks whether the ATS submission itself succeeded; funnel_stage
# tracks where the candidate is in the human recruiting process afterward,
# and is only ever changed by the user dragging a card on the dashboard
# (see routers/applications.py::update_funnel_stage). The Kanban's
# "Sauvegardées" (pre-application) column is not a funnel_stage value - it's
# derived from SavedJob rows with no matching Application (see
# routers/dashboard.py).
FUNNEL_STAGE_POSTULE = "postule"
FUNNEL_STAGE_ENTRETIEN_PROGRAMME = "entretien_programme"
FUNNEL_STAGE_PROPOSITION = "proposition"
FUNNEL_STAGE_REFUSEE = "refusee"


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "offer_url", name="uq_application_user_offer_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    diagnostic_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostics.id", ondelete="CASCADE"), nullable=False
    )
    offer_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    ats_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=APPLICATION_STATUS_EN_COURS
    )
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    funnel_stage: Mapped[str] = mapped_column(
        String(30), nullable=False, default=FUNNEL_STAGE_POSTULE
    )

    diagnostic: Mapped["Diagnostic"] = relationship()
