from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.cv_parser.parser import MAX_CV_SIZE_BYTES, CVParsingError, parse_cv
from app.database import get_db
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.schemas.candidate_profile import CandidateProfileIn, CandidateProfileOut

router = APIRouter(prefix="/profile", tags=["candidate_profile"])


def _to_out(profile: CandidateProfile) -> CandidateProfileOut:
    return CandidateProfileOut(
        full_name=profile.full_name,
        phone=profile.phone,
        address=profile.address,
        linkedin_url=profile.linkedin_url,
        portfolio_url=profile.portfolio_url,
        work_authorization=profile.work_authorization,
        salary_expectation=profile.salary_expectation,
        cv_filename=profile.cv_filename,
        has_cv=profile.cv_text is not None,
        updated_at=profile.updated_at,
    )


def _get_profile(db: Session, user_id: int) -> CandidateProfile | None:
    return (
        db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    )


def _get_or_create_profile(db: Session, user_id: int) -> CandidateProfile:
    profile = _get_profile(db, user_id)
    if profile is None:
        profile = CandidateProfile(
            user_id=user_id, full_name="", phone="", work_authorization=""
        )
        db.add(profile)
    return profile


@router.get("", response_model=CandidateProfileOut)
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateProfileOut:
    profile = _get_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profil non renseigné."
        )
    return _to_out(profile)


@router.put("", response_model=CandidateProfileOut)
def upsert_profile(
    payload: CandidateProfileIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateProfileOut:
    profile = _get_or_create_profile(db, current_user.id)
    profile.full_name = payload.full_name
    profile.phone = payload.phone
    profile.address = payload.address
    profile.linkedin_url = payload.linkedin_url
    profile.portfolio_url = payload.portfolio_url
    profile.work_authorization = payload.work_authorization
    profile.salary_expectation = payload.salary_expectation
    db.commit()
    db.refresh(profile)
    return _to_out(profile)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """RGPD purge of the candidate profile - the most personal data the app
    holds (full reference CV text, phone, address).

    Deliberately a separate action from `DELETE /diagnostics`, which purges
    diagnostics/documents/applications and never touches the profile: a user
    may well want to clear their diagnostic history while keeping the
    profile for future searches, or the reverse. Idempotent (204 even with
    no profile stored) so a client retrying the purge never sees a spurious
    404 - "no profile stored" is the outcome the caller asked for.
    """
    profile = _get_profile(db, current_user.id)
    if profile is not None:
        db.delete(profile)
        db.commit()


@router.post("/cv", response_model=CandidateProfileOut)
def upload_reference_cv(
    cv_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateProfileOut:
    if cv_file.size is not None and cv_file.size > MAX_CV_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier dépasse la taille maximale autorisée (5 Mo).",
        )

    try:
        cv_bytes = cv_file.file.read()
        parsed = parse_cv(cv_bytes, cv_file.filename or "")
    except CVParsingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    profile = _get_or_create_profile(db, current_user.id)
    profile.cv_text = parsed.text
    profile.cv_filename = cv_file.filename
    profile.cv_has_tables = parsed.has_tables
    profile.cv_has_multi_column = parsed.has_multi_column
    profile.cv_has_images = parsed.has_images
    profile.cv_detected_sections = sorted(parsed.detected_sections)
    db.commit()
    db.refresh(profile)
    return _to_out(profile)
