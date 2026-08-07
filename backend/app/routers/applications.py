from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.applications.service import (
    ApplicationCreationError,
    DuplicateApplicationError,
    MissingReferenceCvError,
    create_application,
)
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.llm_analyzer.analyzer import SemanticAnalyzer
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.models.application import Application
from app.models.user import User
from app.rate_limit.limiter import RateLimitExceeded, check_rate_limit, lock_user_for_rate_limit
from app.schemas.application import ApplicationCreateIn, ApplicationOut
from app.schemas.diagnostic import DiagnosticReport

router = APIRouter(prefix="/applications", tags=["applications"])


def _to_out(application: Application) -> ApplicationOut:
    diagnostic = application.diagnostic  # lazy-loaded via the ORM relationship (Task 2)
    return ApplicationOut(
        id=application.id,
        diagnostic_id=application.diagnostic_id,
        offer_url=application.offer_url,
        source=application.source,
        company_name=application.company_name,
        job_title=application.job_title,
        ats_type=application.ats_type,
        status=application.status,
        error_message=application.error_message,
        submitted_at=application.submitted_at,
        created_at=application.created_at,
        updated_at=application.updated_at,
        diagnostic=DiagnosticReport(
            id=diagnostic.id,
            created_at=diagnostic.created_at,
            overall_score=diagnostic.overall_score,
            structural_score=diagnostic.structural_score,
            structural_issues=diagnostic.structural_issues,
            semantic_score=diagnostic.semantic_score,
            missing_keywords=diagnostic.missing_keywords,
            recommendations=diagnostic.recommendations,
        ),
    )


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create(
    payload: ApplicationCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analyzer: SemanticAnalyzer = Depends(get_semantic_analyzer),
) -> ApplicationOut:
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    try:
        application = create_application(
            db,
            user_id=current_user.id,
            offer_url=payload.offer_url,
            offer_text_override=payload.offer_text,
            source=payload.source,
            company_name=payload.company_name,
            job_title=payload.job_title,
            ats_type=payload.ats_type,
            analyzer=analyzer,
        )
    except MissingReferenceCvError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except DuplicateApplicationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ApplicationCreationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return _to_out(application)


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ApplicationOut]:
    applications = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return [_to_out(a) for a in applications]


def get_owned_application(db: Session, application_id: int, user_id: int) -> Application:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == user_id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature introuvable.")
    return application


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationOut:
    return _to_out(get_owned_application(db, application_id, current_user.id))
