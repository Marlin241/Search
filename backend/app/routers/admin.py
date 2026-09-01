import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.config import get_settings
from app.database import get_db
from app.llm.switch import llm_features_enabled, set_llm_features_enabled
from app.models.access_request import (
    STATUS_APPROVED,
    STATUS_DISMISSED,
    STATUS_PENDING,
    AccessRequest,
)
from app.models.feedback import Feedback
from app.models.invite_code import InviteCode
from app.models.llm_call_log import LlmCallLog
from app.models.user import User
from app.notifications.resend_client import EmailSendError, send_access_granted_email
from app.rate_limit.llm_quota import FEATURES, usage_summary
from app.schemas.access_request import AdminAccessRequestOut
from app.schemas.admin import (
    ActivePatchIn,
    AdminFeedbackOut,
    AdminInviteOut,
    AdminUserOut,
    InviteCreateIn,
    InviteCreateOut,
    LlmToggleIn,
    LlmToggleOut,
    QuotaPatchIn,
)
from app.utils.time import utcnow
from scripts.invites import generate_codes, revoke_code

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)]
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _month_start() -> datetime:
    return utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _to_admin_user_out(db: Session, user: User) -> AdminUserOut:
    invite = db.scalar(select(InviteCode).where(InviteCode.used_by_user_id == user.id))
    last_activity = db.scalar(
        select(func.max(LlmCallLog.created_at)).where(LlmCallLog.user_id == user.id)
    )
    return AdminUserOut(
        id=user.id,
        email=user.email,
        created_at=_iso(user.created_at) or "",
        is_admin=user.is_admin,
        is_active=user.is_active,
        invite_note=invite.note if invite is not None else None,
        consent_version=user.consent_version,
        consent_accepted_at=_iso(user.consent_accepted_at),
        last_activity_at=_iso(last_activity),
        quota_overrides=user.quota_overrides,
        usage=usage_summary(db, user),  # type: ignore[arg-type]
    )


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )
    return user


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    since_month = _month_start()
    active_since = utcnow() - timedelta(days=7)

    calls_by_feature: dict[str, int] = {
        feature: count
        for feature, count in db.execute(
            select(LlmCallLog.feature, func.count())
            .where(LlmCallLog.created_at >= since_month)
            .group_by(LlmCallLog.feature)
        ).all()
    }
    tokens = db.execute(
        select(
            func.coalesce(func.sum(LlmCallLog.input_tokens), 0),
            func.coalesce(func.sum(LlmCallLog.output_tokens), 0),
        ).where(LlmCallLog.created_at >= since_month)
    ).one()
    active_7d = db.scalar(
        select(func.count(func.distinct(LlmCallLog.user_id))).where(
            LlmCallLog.created_at >= active_since
        )
    )

    return {
        "users_total": db.scalar(select(func.count()).select_from(User)) or 0,
        "users_active_7d": active_7d or 0,
        "llm_calls_this_month": {f: calls_by_feature.get(f, 0) for f in FEATURES},
        "tokens_this_month": {"input": tokens[0], "output": tokens[1]},
        "llm_features_enabled": llm_features_enabled(db),
    }


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db)) -> list[AdminUserOut]:
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [_to_admin_user_out(db, u) for u in users]


@router.get("/users/{user_id}", response_model=AdminUserOut)
def get_user(user_id: int, db: Session = Depends(get_db)) -> AdminUserOut:
    return _to_admin_user_out(db, _get_user(db, user_id))


@router.patch("/users/{user_id}/quota", response_model=AdminUserOut)
def patch_quota(
    user_id: int, payload: QuotaPatchIn, db: Session = Depends(get_db)
) -> AdminUserOut:
    if payload.feature not in FEATURES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fonctionnalité inconnue.",
        )
    user = _get_user(db, user_id)
    overrides = dict(user.quota_overrides or {})
    if payload.limit is None:
        overrides.pop(payload.feature, None)
    else:
        overrides[payload.feature] = payload.limit
    user.quota_overrides = overrides or None
    db.commit()
    db.refresh(user)
    return _to_admin_user_out(db, user)


@router.patch("/users/{user_id}/active", response_model=AdminUserOut)
def patch_active(
    user_id: int,
    payload: ActivePatchIn,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> AdminUserOut:
    if user_id == current_admin.id and not payload.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu ne peux pas désactiver ton propre compte.",
        )
    user = _get_user(db, user_id)
    user.is_active = payload.active
    db.commit()
    db.refresh(user)
    return _to_admin_user_out(db, user)


@router.get("/invites", response_model=list[AdminInviteOut])
def list_invites(db: Session = Depends(get_db)) -> list[AdminInviteOut]:
    rows = db.execute(
        select(InviteCode, User.email)
        .outerjoin(User, InviteCode.used_by_user_id == User.id)
        .order_by(InviteCode.created_at.desc())
    ).all()
    return [
        AdminInviteOut(
            code=code.code,
            note=code.note,
            created_at=_iso(code.created_at) or "",
            expires_at=_iso(code.expires_at),
            used_by_email=email,
            used_at=_iso(code.used_at),
        )
        for code, email in rows
    ]


@router.post("/invites", response_model=InviteCreateOut)
def create_invites(
    payload: InviteCreateIn, db: Session = Depends(get_db)
) -> InviteCreateOut:
    if not 1 <= payload.count <= 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Entre 1 et 50 codes à la fois.",
        )
    return InviteCreateOut(codes=generate_codes(db, payload.count, payload.note))


@router.delete("/invites/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invite(code: str, db: Session = Depends(get_db)) -> Response:
    if not revoke_code(db, code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Code inconnu ou déjà utilisé.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/llm-toggle", response_model=LlmToggleOut)
def llm_toggle(payload: LlmToggleIn, db: Session = Depends(get_db)) -> LlmToggleOut:
    set_llm_features_enabled(db, payload.enabled)
    return LlmToggleOut(enabled=llm_features_enabled(db))


@router.get("/feedback", response_model=list[AdminFeedbackOut])
def list_feedback(db: Session = Depends(get_db)) -> list[AdminFeedbackOut]:
    rows = db.execute(
        select(Feedback, User.email)
        .outerjoin(User, Feedback.user_id == User.id)
        .order_by(Feedback.created_at.desc())
    ).all()
    return [
        AdminFeedbackOut(
            id=fb.id,
            user_email=email,
            page=fb.page,
            message=fb.message,
            created_at=_iso(fb.created_at) or "",
            handled_at=_iso(fb.handled_at),
        )
        for fb, email in rows
    ]


@router.post("/feedback/{feedback_id}/handled", status_code=status.HTTP_204_NO_CONTENT)
def mark_feedback_handled(feedback_id: int, db: Session = Depends(get_db)) -> Response:
    fb = db.get(Feedback, feedback_id)
    if fb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Retour introuvable."
        )
    fb.handled_at = utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _access_request_out(row: AccessRequest) -> AdminAccessRequestOut:
    return AdminAccessRequestOut(
        id=row.id,
        email=row.email,
        note=row.note,
        status=row.status,
        created_at=_iso(row.created_at) or "",
        handled_at=_iso(row.handled_at),
        invite_code=row.invite_code,
    )


@router.get("/access-requests", response_model=list[AdminAccessRequestOut])
def list_access_requests(
    pending: bool = False, db: Session = Depends(get_db)
) -> list[AdminAccessRequestOut]:
    stmt = select(AccessRequest).order_by(AccessRequest.created_at.desc())
    if pending:
        stmt = stmt.where(AccessRequest.status == STATUS_PENDING)
    return [_access_request_out(r) for r in db.scalars(stmt)]


def _get_access_request(db: Session, request_id: int) -> AccessRequest:
    row = db.get(AccessRequest, request_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Demande introuvable."
        )
    return row


@router.post(
    "/access-requests/{request_id}/approve", response_model=AdminAccessRequestOut
)
def approve_access_request(
    request_id: int, db: Session = Depends(get_db)
) -> AdminAccessRequestOut:
    """Génère un code d'invitation à usage unique, l'envoie par email au
    demandeur, et marque la demande approuvée. Idempotent : ne régénère
    pas de code si la demande est déjà traitée."""
    row = _get_access_request(db, request_id)
    if row.status == STATUS_PENDING:
        (code,) = generate_codes(
            db, count=1, note=f"demande d'accès #{row.id} · {row.email}"
        )
        row.status = STATUS_APPROVED
        row.handled_at = utcnow()
        row.invite_code = code
        db.commit()
        db.refresh(row)

        login_url = f"{get_settings().frontend_base_url.rstrip('/')}/login"
        try:
            send_access_granted_email(row.email, code, login_url)
        except EmailSendError:
            logger.exception("access granted email failed for request %s", row.id)
    return _access_request_out(row)


@router.post(
    "/access-requests/{request_id}/dismiss", response_model=AdminAccessRequestOut
)
def dismiss_access_request(
    request_id: int, db: Session = Depends(get_db)
) -> AdminAccessRequestOut:
    """Écarte la demande sans envoyer d'email. Idempotent."""
    row = _get_access_request(db, request_id)
    if row.status == STATUS_PENDING:
        row.status = STATUS_DISMISSED
        row.handled_at = utcnow()
        db.commit()
        db.refresh(row)
    return _access_request_out(row)
