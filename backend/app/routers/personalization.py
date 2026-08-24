from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Response,
    status,
)
from fpdf.errors import FPDFException
from sqlalchemy.orm import Session

from app import database
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.generation_jobs import state as generation_jobs_state
from app.llm_analyzer.analyzer import SemanticAnalyzer
from app.llm_analyzer.dependencies import get_semantic_analyzer
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
from app.personalization.jobs import run_cv_generation_job
from app.personalization.pdf_generator import render_cover_letter_pdf
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_personalization_rate_limit,
    lock_user_for_rate_limit,
)
from app.schemas.generation_job import GenerationJobStarted
from app.schemas.personalization import PersonalizedDocumentOut
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage

router = APIRouter(prefix="/diagnostics", tags=["personalization"])

_CV_GENERATION_STEPS = 5


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
    response_model=GenerationJobStarted,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_cv(
    diagnostic_id: int,
    background_tasks: BackgroundTasks,
    template: Literal["classic", "modern", "minimal"] = Form("classic"),
    target_language: str = Form("fr"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rewriter: CvRewriter = Depends(get_cv_rewriter),
    analyzer: SemanticAnalyzer = Depends(get_semantic_analyzer),
    storage: ObjectStorage = Depends(get_object_storage),
) -> GenerationJobStarted:
    # Same lock-then-check pattern as diagnostics.create_diagnostic (see
    # app/rate_limit/limiter.py): take the row lock BEFORE checking the
    # rate limit so concurrent requests from the same user serialize on it,
    # closing the TOCTOU race where multiple in-flight requests could all
    # pass the count check before any of their PersonalizationRequestLog
    # rows exist. The actual generation now runs in a background job (see
    # app.personalization.jobs.run_cv_generation_job) - this endpoint only
    # launches it and returns a job_id to poll via
    # GET /generation-jobs/{job_id}, so the rate-limit gate must still be
    # enforced synchronously here, before any job is created.
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_personalization_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc

    diagnostic = _get_owned_diagnostic(db, diagnostic_id, current_user.id)

    job_id = generation_jobs_state.create_job(current_user.id, _CV_GENERATION_STEPS)
    background_tasks.add_task(
        run_cv_generation_job,
        job_id,
        diagnostic.id,
        current_user.id,
        template,
        target_language,
        rewriter,
        analyzer,
        storage,
        database.SessionLocal,
    )
    return GenerationJobStarted(job_id=job_id)


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
