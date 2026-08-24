import mimetypes
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.cv_parser.image_extractor import ImageExtractionError, extract_embedded_images
from app.cv_parser.parser import MAX_CV_SIZE_BYTES, CVParsingError, parse_cv
from app.database import get_db
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.schemas.candidate_profile import (
    CandidateProfileIn,
    CandidateProfileOut,
    ExtractedPhotoOut,
    OnboardingProfileIn,
)
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage

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
        desired_job_titles=profile.desired_job_titles,
        seniority_level=profile.seniority_level,
        desired_locations=profile.desired_locations,
        remote_preference=profile.remote_preference,
        contract_types=profile.contract_types,
        salary_min=profile.salary_min,
        salary_max=profile.salary_max,
        weekly_application_goal=profile.weekly_application_goal,
        has_profile_photo=profile.profile_photo_key is not None,
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


def _user_photo_prefix(user_id: int) -> str:
    return f"users/{user_id}/onboarding/photos/"


def _photo_preview_url(user_id: int, key: str) -> str:
    # The key already carries the users/{id}/onboarding/photos/ prefix -
    # strip it back off for the URL since the route only needs the suffix,
    # and re-validates the full key server-side against the caller's own id
    # anyway (see get_photo below).
    suffix = key.removeprefix(_user_photo_prefix(user_id))
    return f"/profile/photo/{suffix}"


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


@router.put("/onboarding", response_model=CandidateProfileOut)
def submit_onboarding(
    payload: OnboardingProfileIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateProfileOut:
    profile = _get_or_create_profile(db, current_user.id)
    profile.desired_job_titles = payload.desired_job_titles
    profile.seniority_level = payload.seniority_level
    profile.desired_locations = payload.desired_locations
    profile.remote_preference = payload.remote_preference
    profile.contract_types = payload.contract_types
    profile.salary_min = payload.salary_min
    profile.salary_max = payload.salary_max
    profile.weekly_application_goal = payload.weekly_application_goal
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


@router.post("/cv/extract-photos", response_model=list[ExtractedPhotoOut])
def extract_cv_photos(
    cv_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> list[ExtractedPhotoOut]:
    """Best-effort: pull embedded photos out of the uploaded CV and offer
    them as profile-picture candidates. Never blocks the onboarding flow -
    an unsupported/unreadable file just yields no candidates rather than a
    422, since photo suggestion is a nice-to-have on top of the CV upload,
    not a requirement of it."""
    if cv_file.size is not None and cv_file.size > MAX_CV_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier dépasse la taille maximale autorisée (5 Mo).",
        )

    cv_bytes = cv_file.file.read()
    try:
        images = extract_embedded_images(cv_bytes, cv_file.filename or "")
    except ImageExtractionError:
        return []

    results: list[ExtractedPhotoOut] = []
    for index, image in enumerate(images):
        ext = mimetypes.guess_extension(image.content_type) or ".jpg"
        key = f"{_user_photo_prefix(current_user.id)}{index}{ext}"
        try:
            storage.upload(key, image.content, content_type=image.content_type)
        except ObjectStorageError:
            continue
        results.append(
            ExtractedPhotoOut(
                key=key, preview_url=_photo_preview_url(current_user.id, key)
            )
        )
    return results


MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024


@router.post("/photo/upload", response_model=ExtractedPhotoOut)
def upload_manual_photo(
    photo_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> ExtractedPhotoOut:
    """Lets a user pick their own image instead of one extracted from the
    CV ("Importer une autre image" in the onboarding photo step)."""
    if photo_file.size is not None and photo_file.size > MAX_PHOTO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="L'image dépasse la taille maximale autorisée (5 Mo).",
        )
    content_type = photo_file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier doit être une image.",
        )

    ext = mimetypes.guess_extension(content_type) or ".jpg"
    key = f"{_user_photo_prefix(current_user.id)}manual-{uuid.uuid4().hex}{ext}"
    content = photo_file.file.read()
    try:
        storage.upload(key, content, content_type=content_type)
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le stockage de l'image a échoué.",
        ) from exc

    return ExtractedPhotoOut(
        key=key, preview_url=_photo_preview_url(current_user.id, key)
    )


class SetProfilePhotoIn(BaseModel):
    photo_key: str | None = None


@router.put("/photo", response_model=CandidateProfileOut)
def set_profile_photo(
    payload: SetProfilePhotoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateProfileOut:
    """Sets (or clears, if photo_key is None) the chosen profile photo.
    The key must be one this user's own extract-photos call produced - the
    prefix check stops a user pointing their profile at another user's
    uploaded image by guessing/enumerating keys."""
    if payload.photo_key is not None and not payload.photo_key.startswith(
        _user_photo_prefix(current_user.id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette photo ne vous appartient pas.",
        )

    profile = _get_or_create_profile(db, current_user.id)
    profile.profile_photo_key = payload.photo_key
    db.commit()
    db.refresh(profile)
    return _to_out(profile)


@router.get("/photo/{suffix}")
def get_photo(
    suffix: str,
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    key = f"{_user_photo_prefix(current_user.id)}{suffix}"
    try:
        content = storage.download(key)
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Photo introuvable."
        ) from exc

    content_type = mimetypes.guess_type(suffix)[0] or "image/jpeg"
    return Response(content=content, media_type=content_type)
