from datetime import timedelta

import jwt

from app.config import get_settings
from app.utils.time import utcnow

_UNSUBSCRIBE_TOKEN_PURPOSE = "unsubscribe"
_UNSUBSCRIBE_TOKEN_EXPIRE_DAYS = 365


class InvalidUnsubscribeTokenError(Exception):
    pass


def create_unsubscribe_token(user_id: int) -> str:
    """Signé avec le même secret que les tokens de connexion, mais avec une
    claim `purpose` distincte et une expiration longue (365 jours plutôt que
    les quelques heures d'un token de connexion) - un email peut être lu des
    semaines après réception. Un token frais est généré à chaque envoi
    d'email, jamais réutilisé/stocké."""
    settings = get_settings()
    expire = utcnow() + timedelta(days=_UNSUBSCRIBE_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "purpose": _UNSUBSCRIBE_TOKEN_PURPOSE,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_unsubscribe_token(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidUnsubscribeTokenError("Token invalide ou expiré.") from exc
    if payload.get("purpose") != _UNSUBSCRIBE_TOKEN_PURPOSE:
        raise InvalidUnsubscribeTokenError("Token invalide pour cet usage.")
    return int(payload["sub"])
