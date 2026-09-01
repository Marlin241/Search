from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utcnow

#: valeurs possibles de ``AccessRequest.status``
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DISMISSED = "dismissed"


class AccessRequest(Base):
    """Demande d'accès à la beta déposée depuis la landing publique.
    Non rattachée à un utilisateur : la beta est sur invitation. L'admin
    approuve (un code d'invitation est généré et envoyé par email au
    demandeur) ou écarte la demande."""

    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_PENDING,
        server_default=STATUS_PENDING,
        index=True,
    )
    #: horodatage de la décision (approbation ou écartement)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: code d'invitation généré à l'approbation (pour référence / renvoi)
    invite_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
