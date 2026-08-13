import hashlib
import hmac
from datetime import timedelta

import jwt

from app.config import get_settings
from app.utils.time import utcnow

_UNSUBSCRIBE_TOKEN_PURPOSE = "unsubscribe"
_UNSUBSCRIBE_TOKEN_EXPIRE_DAYS = 365


class InvalidUnsubscribeTokenError(Exception):
    pass


def _unsubscribe_signing_key(jwt_secret: str) -> str:
    """A distinct key, derived from (never equal to) the login JWT secret.

    Unsubscribe tokens are long-lived (365 days) and travel over email - a
    much leakier channel than a login flow (forwarding, link-scanning
    gateways, inbox compromise). If they were signed with the same secret
    as login tokens, a leaked unsubscribe token would decode successfully
    against `auth.security.decode_access_token` (which never checks a
    `purpose` claim) and grant a full, long-lived session - not just the
    "disable this saved search" action it was meant for. Signing with a
    derived key makes that confusion cryptographically impossible: a
    token signed here will never verify against the raw jwt_secret used
    for login tokens, and vice versa, regardless of any purpose-claim
    check either side does or forgets to do."""
    return hmac.new(jwt_secret.encode(), b"unsubscribe", hashlib.sha256).hexdigest()


def create_unsubscribe_token(user_id: int) -> str:
    """A token frais est généré à chaque envoi d'email (jamais réutilisé/
    stocké) - l'expiration longue (365 jours, plutôt que les quelques
    heures d'un token de connexion) n'est donc jamais perceptible en
    pratique tant que les emails continuent d'arriver; un email peut être
    lu des semaines après réception."""
    settings = get_settings()
    expire = utcnow() + timedelta(days=_UNSUBSCRIBE_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "purpose": _UNSUBSCRIBE_TOKEN_PURPOSE,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        _unsubscribe_signing_key(settings.jwt_secret),
        algorithm=settings.jwt_algorithm,
    )


def verify_unsubscribe_token(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            _unsubscribe_signing_key(settings.jwt_secret),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidUnsubscribeTokenError("Token invalide ou expiré.") from exc
    if payload.get("purpose") != _UNSUBSCRIBE_TOKEN_PURPOSE:
        raise InvalidUnsubscribeTokenError("Token invalide pour cet usage.")
    return int(payload["sub"])
