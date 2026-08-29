from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import database
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.generation_jobs import state as generation_jobs_state
from app.interview_prep.analyzer import InterviewPrepAnalyzer
from app.interview_prep.dependencies import get_interview_prep_analyzer
from app.interview_prep.jobs import run_interview_prep_job
from app.llm.dependencies import require_llm_enabled
from app.models.diagnostic import Diagnostic
from app.models.interview_prep_dossier import InterviewPrepDossier
from app.models.saved_job import SavedJob
from app.models.user import User
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_interview_prep_rate_limit,
    lock_user_for_rate_limit,
)
from app.rate_limit.llm_quota import QuotaExceeded, enforce_monthly_quota
from app.schemas.generation_job import GenerationJobStarted
from app.schemas.interview_prep import InterviewPrepDossierOut, InterviewPrepRequestIn

router = APIRouter(tags=["interview_prep"])


def _get_owned_saved_job(db: Session, saved_job_id: int, user_id: int) -> SavedJob:
    saved_job = (
        db.query(SavedJob)
        .filter(SavedJob.id == saved_job_id, SavedJob.user_id == user_id)
        .first()
    )
    if saved_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre sauvegardée introuvable.",
        )
    return saved_job


@router.post(
    "/saved-jobs/{saved_job_id}/interview-prep",
    response_model=GenerationJobStarted,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_interview_prep(
    saved_job_id: int,
    payload: InterviewPrepRequestIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analyzer: InterviewPrepAnalyzer = Depends(get_interview_prep_analyzer),
    _llm: None = Depends(require_llm_enabled),
) -> GenerationJobStarted:
    saved_job = _get_owned_saved_job(db, saved_job_id, current_user.id)

    has_diagnostic = (
        db.query(Diagnostic.id).filter(Diagnostic.saved_job_id == saved_job.id).first()
        is not None
    )
    if not has_diagnostic:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lancez d'abord un diagnostic pour cette offre depuis l'onglet Offre.",
        )

    # Same lock-then-check-then-commit-before-background-task pattern as
    # generate_cv/generate_lettre (app/routers/personalization.py): the
    # background job's own session later needs a lock on this same user row
    # to write its request-log row, so the lock taken above must be
    # released via commit before handing off, or the two sessions deadlock
    # against each other (see that module's comment for the full story).
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_interview_prep_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc

    try:
        enforce_monthly_quota(db, current_user, "interview_prep")
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.as_dict()
        ) from exc
    db.commit()

    total_steps = 4 if payload.use_web_search else 3
    job_id = generation_jobs_state.create_job(current_user.id, total_steps)
    background_tasks.add_task(
        run_interview_prep_job,
        job_id,
        saved_job.id,
        current_user.id,
        payload.persona,
        payload.extra_context,
        payload.use_web_search,
        analyzer,
        database.SessionLocal,
    )
    return GenerationJobStarted(job_id=job_id)


@router.get(
    "/saved-jobs/{saved_job_id}/interview-prep", response_model=InterviewPrepDossierOut
)
def get_interview_prep(
    saved_job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewPrepDossierOut:
    saved_job = _get_owned_saved_job(db, saved_job_id, current_user.id)

    dossier = (
        db.query(InterviewPrepDossier)
        .filter(InterviewPrepDossier.saved_job_id == saved_job.id)
        .first()
    )
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun dossier de préparation d'entretien pour cette offre.",
        )

    return InterviewPrepDossierOut(
        saved_job_id=dossier.saved_job_id,
        persona=dossier.persona,
        extra_context=dossier.extra_context,
        web_search_used=dossier.web_search_used,
        dossier=dossier.dossier_json,
        sources=dossier.sources_json,
        created_at=dossier.created_at,
        updated_at=dossier.updated_at,
    )
