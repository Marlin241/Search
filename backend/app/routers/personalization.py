from fastapi import APIRouter, Depends, HTTPException, Response, status
from fpdf.errors import FPDFException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.diagnostic import Diagnostic
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.personalized_document import PersonalizedDocument
from app.models.user import User
from app.personalization.analyzer import (
    CoverLetterGenerator,
    CvRewriter,
    PersonalizationError,
)
from app.personalization.dependencies import get_cover_letter_generator, get_cv_rewriter
from app.personalization.pdf_generator import render_cover_letter_pdf, render_cv_pdf
from app.personalization.verification import cv_needs_review
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_personalization_rate_limit,
    lock_user_for_rate_limit,
)
from app.schemas.personalization import PersonalizedDocumentOut
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage

router = APIRouter(prefix="/diagnostics", tags=["personalization"])


def _get_owned_diagnostic(db: Session, diagnostic_id: int, user_id: int) -> Diagnostic:
    diagnostic = (
        db.query(Diagnostic)
        .filter(Diagnostic.id == diagnostic_id, Diagnostic.user_id == user_id)
        .first()
    )
    if diagnostic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic introuvable."
        )
    return diagnostic


def _storage_key(user_id: int, diagnostic_id: int, kind: str) -> str:
    return f"users/{user_id}/diagnostics/{diagnostic_id}/{kind}.pdf"


def _get_document(
    db: Session, diagnostic_id: int, kind: str
) -> PersonalizedDocument | None:
    return (
        db.query(PersonalizedDocument)
        .filter(
            PersonalizedDocument.diagnostic_id == diagnostic_id,
            PersonalizedDocument.kind == kind,
        )
        .first()
    )


def _upsert_document(
    db: Session, diagnostic_id: int, kind: str, storage_key: str, needs_review: bool
) -> PersonalizedDocument:
    document = _get_document(db, diagnostic_id, kind)
    if document is None:
        document = PersonalizedDocument(
            diagnostic_id=diagnostic_id,
            kind=kind,
            storage_key=storage_key,
            needs_review=needs_review,
        )
        db.add(document)
    else:
        document.storage_key = storage_key
        document.needs_review = needs_review
    return document


@router.post(
    "/{diagnostic_id}/cv",
    response_model=PersonalizedDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_cv(
    diagnostic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rewriter: CvRewriter = Depends(get_cv_rewriter),
    storage: ObjectStorage = Depends(get_object_storage),
) -> PersonalizedDocumentOut:
    # Same lock-then-check pattern as diagnostics.create_diagnostic (see
    # app/rate_limit/limiter.py): take the row lock BEFORE checking the
    # rate limit so concurrent requests from the same user serialize on it,
    # closing the TOCTOU race where multiple in-flight requests could all
    # pass the count check before any of their PersonalizationRequestLog
    # rows exist.
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_personalization_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc

    diagnostic = _get_owned_diagnostic(db, diagnostic_id, current_user.id)

    try:
        rewritten = rewriter.rewrite(
            diagnostic.cv_text,
            diagnostic.offer_text,
            diagnostic.missing_keywords,
            diagnostic.recommendations,
        )
    except PersonalizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    needs_review = cv_needs_review(diagnostic.cv_text, rewritten)
    try:
        pdf_bytes = render_cv_pdf(rewritten)
    except FPDFException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La génération du PDF a échoué.",
        ) from exc
    key = _storage_key(current_user.id, diagnostic.id, "cv")

    try:
        storage.upload(key, pdf_bytes)
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le stockage du document a échoué.",
        ) from exc

    # The PersonalizationRequestLog row (which the rate limit counts) is
    # only added here, after the rewrite and the upload have both
    # succeeded - not earlier. If either step fails, we raise before
    # reaching this line and nothing is added to the session, so a failed
    # (503) generation - which delivered nothing to the user - never
    # consumes a slot of the user's hourly personalization quota.
    document = _upsert_document(db, diagnostic.id, "cv", key, needs_review)
    db.add(PersonalizationRequestLog(user_id=current_user.id))
    db.commit()
    db.refresh(document)

    return PersonalizedDocumentOut(
        kind=document.kind,
        needs_review=document.needs_review,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post(
    "/{diagnostic_id}/lettre",
    response_model=PersonalizedDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_lettre(
    diagnostic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    generator: CoverLetterGenerator = Depends(get_cover_letter_generator),
    storage: ObjectStorage = Depends(get_object_storage),
) -> PersonalizedDocumentOut:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_personalization_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc

    diagnostic = _get_owned_diagnostic(db, diagnostic_id, current_user.id)

    try:
        letter = generator.generate(
            diagnostic.cv_text,
            diagnostic.offer_text,
            diagnostic.missing_keywords,
            diagnostic.recommendations,
        )
    except PersonalizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    try:
        pdf_bytes = render_cover_letter_pdf(letter)
    except FPDFException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La génération du PDF a échoué.",
        ) from exc
    key = _storage_key(current_user.id, diagnostic.id, "lettre")

    try:
        storage.upload(key, pdf_bytes)
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le stockage du document a échoué.",
        ) from exc

    document = _upsert_document(db, diagnostic.id, "lettre", key, needs_review=False)
    db.add(PersonalizationRequestLog(user_id=current_user.id))
    db.commit()
    db.refresh(document)

    return PersonalizedDocumentOut(
        kind=document.kind,
        needs_review=document.needs_review,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _download(
    diagnostic_id: int,
    kind: str,
    filename: str,
    db: Session,
    current_user: User,
    storage: ObjectStorage,
) -> Response:
    diagnostic = _get_owned_diagnostic(db, diagnostic_id, current_user.id)
    document = _get_document(db, diagnostic.id, kind)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucun document '{kind}' n'a encore été généré pour ce diagnostic.",
        )
    try:
        pdf_bytes = storage.download(document.storage_key)
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le téléchargement du document a échoué.",
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{diagnostic_id}/cv")
def download_cv(
    diagnostic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    return _download(diagnostic_id, "cv", "cv_optimise.pdf", db, current_user, storage)


@router.get("/{diagnostic_id}/lettre")
def download_lettre(
    diagnostic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    return _download(
        diagnostic_id, "lettre", "lettre_motivation.pdf", db, current_user, storage
    )
