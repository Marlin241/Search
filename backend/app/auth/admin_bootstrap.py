"""Promotion des comptes admin listés dans le réglage ``ADMIN_EMAILS``.

Promotion seule : un email retiré de ``ADMIN_EMAILS`` n'est jamais
rétrogradé automatiquement (une faute de frappe dans l'env ne doit pas
verrouiller le fondateur dehors). Pour retirer les droits admin :
``UPDATE users SET is_admin = false WHERE email = '...';``
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


def promote_configured_admins(db: Session, emails: set[str]) -> list[str]:
    """Passe ``is_admin`` à vrai pour tout compte existant dont l'email
    figure dans ``emails``. Renvoie la liste des emails effectivement
    promus (vide si rien à faire). Ne crée aucun compte."""
    if not emails:
        return []
    rows = db.scalars(
        select(User).where(func.lower(User.email).in_(emails), User.is_admin.is_(False))
    ).all()
    if not rows:
        return []
    for row in rows:
        row.is_admin = True
    db.commit()
    promoted = [row.email for row in rows]
    logger.info("promoted %d configured admin(s): %s", len(promoted), promoted)
    return promoted
