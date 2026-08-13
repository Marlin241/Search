from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utcnow


class NotifiedListing(Base):
    """Trace qu'une offre (offer_url) a déjà été envoyée à un utilisateur
    par email — empêche de renvoyer deux fois la même offre. Volontairement
    jamais purgée (voir spec, section "Hors scope")."""

    __tablename__ = "notified_listings"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "offer_url", name="uq_notified_listing_user_offer_url"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    offer_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    notified_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
