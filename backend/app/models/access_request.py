from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utcnow


class AccessRequest(Base):
    """Demande d'accès à la beta déposée depuis la landing publique.
    Non rattachée à un utilisateur : la beta est sur invitation, l'admin
    traite les demandes à la main (génère un code, contacte la personne)."""

    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, index=True, nullable=False
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
