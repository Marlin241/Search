import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.http import client_ip
from app.config import get_settings
from app.database import get_db
from app.models.access_request import AccessRequest
from app.notifications.resend_client import (
    EmailSendError,
    send_access_request_confirmation,
    send_access_request_notification,
)
from app.rate_limit.auth_throttle import (
    AuthThrottleExceeded,
    check_auth_throttle,
    record_auth_attempt,
)
from app.schemas.access_request import AccessRequestIn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/access-requests", tags=["access-requests"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def create_access_request(
    payload: AccessRequestIn,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    # Honeypot rempli → on fait comme si de rien n'était (pas d'indice au bot).
    if payload.company.strip():
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    email = str(payload.email).strip().lower()

    ip = client_ip(request)
    try:
        check_auth_throttle(db, action="access_request", identifier=ip)
    except AuthThrottleExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": "Trop de demandes. Réessaie plus tard.",
            },
        ) from exc
    record_auth_attempt(db, action="access_request", identifier=ip)

    db.add(
        AccessRequest(
            email=email,
            note=payload.note.strip()[:1000],
            source_ip=ip,
        )
    )
    db.commit()

    # Accusé de réception au demandeur (non bloquant).
    try:
        send_access_request_confirmation(email)
    except EmailSendError:
        logger.exception("access request confirmation email failed")

    # Notification à l'admin (no-op si ADMIN_NOTIFY_EMAIL vide, non bloquant).
    try:
        send_access_request_notification(
            get_settings().admin_notify_email, email, payload.note
        )
    except EmailSendError:
        logger.exception("access request notification email failed")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
