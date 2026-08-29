from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.consent import CURRENT_TERMS_VERSION
from app.auth.dependencies import get_current_user
from app.auth.http import client_ip
from app.auth.invites import InviteCodeError, redeem_invite_code
from app.auth.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.rate_limit.auth_throttle import (
    AuthThrottleExceeded,
    check_auth_throttle,
    clear_auth_attempts,
    record_auth_attempt,
)
from app.schemas.auth import Token, UserCreate, UserOut
from app.utils.time import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate, request: Request, db: Session = Depends(get_db)
) -> User:
    ip = client_ip(request)
    try:
        check_auth_throttle(db, action="register", identifier=ip)
    except AuthThrottleExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc

    # Validate the invite code BEFORE probing whether the email exists, so a
    # caller without a valid unused code can never distinguish "email taken"
    # (409) from "bad code" (400) - closing the user-enumeration channel for
    # everyone except a holder of a valid single-use code (who would burn it).
    try:
        code_row = redeem_invite_code(db, payload.invite_code)
    except InviteCodeError as exc:
        record_auth_attempt(db, action="register", identifier=ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        record_auth_attempt(db, action="register", identifier=ip)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cet email est déjà utilisé."
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        consent_accepted_at=utcnow(),
        consent_version=CURRENT_TERMS_VERSION,
    )
    db.add(user)
    db.flush()
    code_row.used_by_user_id = user.id
    code_row.used_at = utcnow()
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    identifier = f"{form_data.username.lower()}|{client_ip(request)}"
    try:
        check_auth_throttle(db, action="login", identifier=identifier)
    except AuthThrottleExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc

    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        record_auth_attempt(db, action="login", identifier=identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    clear_auth_attempts(db, action="login", identifier=identifier)
    token = create_access_token(subject=user.email)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
