"""Créer (ou promouvoir) le compte admin de démarrage, sans code d'invitation.

    docker compose exec backend python -m scripts.seed_admin
    docker compose -f docker-compose.prod.yml exec backend \\
        python -m scripts.seed_admin --email vous@example.com

L'email par défaut est la première entrée d'ADMIN_EMAILS. Le mot de passe
est demandé de façon interactive (jamais stocké) ; --password permet de le
scripter. Ré-exécutable à volonté : promeut un compte existant et ne
change le mot de passe que si on en fournit un.
"""

import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from app.auth.consent import CURRENT_TERMS_VERSION
from app.auth.security import hash_password
from app.config import get_settings
from app.database import SessionLocal
from app.models.user import User
from app.utils.time import utcnow

MIN_PASSWORD_LEN = 8


def upsert_admin(db: Session, email: str, password: str | None) -> str:
    """Crée le compte s'il manque (mot de passe requis, 8 caractères mini),
    sinon le promeut admin et ne remplace le mot de passe que si `password`
    est fourni. Renvoie une ligne de statut lisible."""
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).one_or_none()

    if user is None:
        if not password or len(password) < MIN_PASSWORD_LEN:
            raise ValueError(
                f"un mot de passe de {MIN_PASSWORD_LEN}+ caractères est requis "
                "pour créer le compte"
            )
        db.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                consent_accepted_at=utcnow(),
                consent_version=CURRENT_TERMS_VERSION,
                is_admin=True,
            )
        )
        db.commit()
        return f"compte admin créé : {email}"

    changes: list[str] = []
    if not user.is_admin:
        user.is_admin = True
        changes.append("promu admin")
    if password:
        user.hashed_password = hash_password(password)
        changes.append("mot de passe mis à jour")
    db.commit()
    return f"{email} : {', '.join(changes)}" if changes else f"{email} : déjà admin"


def _main() -> None:
    parser = argparse.ArgumentParser(prog="scripts.seed_admin")
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    configured = sorted(get_settings().admin_email_set)
    email = (args.email or (configured[0] if configured else "")).strip().lower()
    if not email:
        sys.exit("aucun --email fourni et ADMIN_EMAILS est vide")
    if email not in get_settings().admin_email_set:
        print(
            f"attention : {email} n'est pas dans ADMIN_EMAILS — la promotion "
            "ne survivra pas à un reset de la base",
            file=sys.stderr,
        )

    db = SessionLocal()
    try:
        password = args.password
        # Un mot de passe n'est demandé que pour une création (compte absent).
        if db.query(User).filter(User.email == email).one_or_none() is None:
            password = password or getpass.getpass(f"mot de passe pour {email} : ")
        try:
            print(upsert_admin(db, email, password))
        except ValueError as exc:
            sys.exit(str(exc))
    finally:
        db.close()


if __name__ == "__main__":
    _main()
