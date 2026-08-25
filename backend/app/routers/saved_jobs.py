import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import database
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.application import Application
from app.models.candidate_profile import CandidateProfile
from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
from app.models.saved_job import SavedJob
from app.models.user import User
from app.offer_ingestion.scraper import ScrapingError, scrape_offer
from app.personalization.pdf_templates import render_cv
from app.schemas.diagnostic import DiagnosticReport
from app.schemas.personalization import PersonalizedDocumentOut
from app.schemas.saved_job import CvRenderPreviewIn, SavedJobIn, SavedJobOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saved-jobs", tags=["saved_jobs"])


def _backfill_full_offer_text(
    saved_job_id: int, offer_url: str, db_session_factory
) -> None:
    try:
        text = scrape_offer(offer_url)
    except ScrapingError:
        return
    db = db_session_factory()
    try:
        saved_job = db.query(SavedJob).filter(SavedJob.id == saved_job_id).first()
        if saved_job is not None:
            saved_job.full_offer_text = text
            db.commit()
    finally:
        db.close()


def _to_summary_out(saved_job: SavedJob) -> SavedJobOut:
    return SavedJobOut(
        id=saved_job.id,
        offer_url=saved_job.offer_url,
        title=saved_job.title,
        company=saved_job.company,
        location=saved_job.location,
        snippet=saved_job.snippet,
        source=saved_job.source,
        ats_type=saved_job.ats_type,
        salary=saved_job.salary,
        has_full_offer_text=saved_job.full_offer_text is not None,
        created_at=saved_job.created_at,
        updated_at=saved_job.updated_at,
    )


@router.post("", response_model=SavedJobOut)
def open_saved_job(
    payload: SavedJobIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedJobOut:
    saved_job = (
        db.query(SavedJob)
        .filter(
            SavedJob.user_id == current_user.id,
            SavedJob.offer_url == payload.offer_url,
        )
        .first()
    )
    if saved_job is None:
        saved_job = SavedJob(user_id=current_user.id, offer_url=payload.offer_url)
        db.add(saved_job)

    saved_job.title = payload.title
    saved_job.company = payload.company
    saved_job.location = payload.location
    saved_job.snippet = payload.snippet
    saved_job.source = payload.source
    saved_job.ats_type = payload.ats_type
    saved_job.salary = payload.salary
    db.commit()
    db.refresh(saved_job)

    if saved_job.full_offer_text is None:
        background_tasks.add_task(
            _backfill_full_offer_text,
            saved_job.id,
            saved_job.offer_url,
            database.SessionLocal,
        )

    return _to_summary_out(saved_job)


@router.get("", response_model=list[SavedJobOut])
def list_saved_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SavedJobOut]:
    saved_jobs = (
        db.query(SavedJob)
        .filter(SavedJob.user_id == current_user.id)
        .order_by(SavedJob.updated_at.desc())
        .all()
    )
    return [_to_summary_out(saved_job) for saved_job in saved_jobs]


@router.get("/{saved_job_id}", response_model=SavedJobOut)
def get_saved_job(
    saved_job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedJobOut:
    saved_job = (
        db.query(SavedJob)
        .filter(SavedJob.id == saved_job_id, SavedJob.user_id == current_user.id)
        .first()
    )
    if saved_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre sauvegardée introuvable.",
        )

    out = _to_summary_out(saved_job)

    latest_diagnostic = (
        db.query(Diagnostic)
        .filter(Diagnostic.saved_job_id == saved_job.id)
        .order_by(Diagnostic.created_at.desc())
        .first()
    )
    if latest_diagnostic is not None:
        out.latest_diagnostic = DiagnosticReport(
            id=latest_diagnostic.id,
            created_at=latest_diagnostic.created_at,
            overall_score=latest_diagnostic.overall_score,
            structural_score=latest_diagnostic.structural_score,
            structural_issues=latest_diagnostic.structural_issues,
            semantic_score=latest_diagnostic.semantic_score,
            missing_keywords=latest_diagnostic.missing_keywords,
            recommendations=latest_diagnostic.recommendations,
        )
        out.documents = [
            PersonalizedDocumentOut(
                kind=document.kind,
                needs_review=document.needs_review,
                created_at=document.created_at,
                updated_at=document.updated_at,
                ats_score_before=document.ats_score_before,
                ats_score_after=document.ats_score_after,
                content_json=document.content_json,
            )
            for document in db.query(PersonalizedDocument)
            .filter(PersonalizedDocument.diagnostic_id == latest_diagnostic.id)
            .all()
        ]

    application = (
        db.query(Application)
        .filter(
            Application.user_id == current_user.id,
            Application.offer_url == saved_job.offer_url,
        )
        .first()
    )
    out.application_status = application.status if application is not None else None

    return out


@router.post("/{saved_job_id}/cv/render-preview")
def render_cv_preview(
    saved_job_id: int,
    payload: CvRenderPreviewIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Pure re-render from an already-generated (possibly user-edited)
    CvRenderPreviewIn.content - no LLM call. Powers the CV editor's live
    preview: fast and a true fpdf2 render, not a CSS approximation."""
    saved_job = (
        db.query(SavedJob)
        .filter(SavedJob.id == saved_job_id, SavedJob.user_id == current_user.id)
        .first()
    )
    if saved_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre sauvegardée introuvable.",
        )

    profile = (
        db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == current_user.id)
        .first()
    )
    pdf_bytes, _ = render_cv(payload.template, payload.content, profile, payload.style)
    return Response(content=pdf_bytes, media_type="application/pdf")
