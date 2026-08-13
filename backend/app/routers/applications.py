import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.service import (
    ApplicationCreationError,
    DuplicateApplicationError,
    MissingReferenceCvError,
    create_application,
    missing_required_profile_fields,
)
from app.ats_adapters.custom_fields import CustomFieldAnsweringError
from app.ats_adapters.dependencies import get_custom_field_answerer
from app.ats_adapters.errors import ATSAdapterError
from app.ats_adapters.registry import get_ats_adapter
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.llm_analyzer.analyzer import SemanticAnalyzer
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.models.application import (
    APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
    APPLICATION_STATUS_ECHEC_SOUMISSION,
    APPLICATION_STATUS_EN_COURS,
    APPLICATION_STATUS_SOUMISE_AUTO,
    APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE,
    Application,
)
from app.models.candidate_profile import CandidateProfile
from app.models.personalized_document import PersonalizedDocument
from app.models.prefilled_form_request_log import PrefilledFormRequestLog
from app.models.user import User
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_prefilled_form_rate_limit,
    check_rate_limit,
    lock_user_for_rate_limit,
)
from app.schemas.application import ApplicationCreateIn, ApplicationOut, ConfirmApplicationIn, PrefilledFormOut
from app.schemas.diagnostic import DiagnosticReport
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage

logger = logging.getLogger(__name__)

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


@router.get("/{application_id}/prefilled-form", response_model=PrefilledFormOut)
def get_prefilled_form(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    custom_field_answerer=Depends(get_custom_field_answerer),
) -> PrefilledFormOut:
    # Same lock-then-check ordering as every other rate-limited endpoint
    # (see app/rate_limit/limiter.py): the lock serializes concurrent
    # requests from this user so they can't all pass the count check before
    # any of their PrefilledFormRequestLog rows exist. Checked up front,
    # before any of the expensive work (page fetch + CustomFieldAnswerer
    # LLM call) below.
    lock_user_for_rate_limit(db, current_user.id)
    try:
        check_prefilled_form_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    application = get_owned_application(db, application_id, current_user.id)
    # get_ats_adapter returns None both when ats_type is None and when it's a
    # non-None value with no registered adapter (e.g. an ats_type set by a
    # future ingestion path that isn't in the registry yet) - both cases mean
    # "nothing we can auto-submit through", so both are handled identically.
    adapter = get_ats_adapter(application.ats_type)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette offre n'est pas éligible à la soumission automatique.",
        )

    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    missing = missing_required_profile_fields(profile)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Complétez votre profil avant de continuer: {', '.join(missing)}",
        )
    assert profile is not None  # missing_required_profile_fields(None) always returns non-empty

    try:
        form = adapter.discover_form(application.offer_url, profile, current_user.email)
    except ATSAdapterError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    diagnostic = application.diagnostic
    custom_fields = [f for f in form.fields if f.is_custom]
    try:
        answers = custom_field_answerer.answer(custom_fields, diagnostic.cv_text, diagnostic.offer_text)
    except CustomFieldAnsweringError:
        # Non-fatal: the preview is still returned, with custom fields left
        # blank for the user to fill in manually during review.
        answers = {}

    filled_fields = [f.model_copy(update={"value": answers.get(f.name, f.value)}) for f in form.fields]

    # Logged only once the preview is actually about to be returned, so a
    # request that failed earlier (409/422/503) - and therefore never ran
    # the LLM - doesn't consume a slot of the user's hourly quota. Same
    # convention as the personalization endpoints.
    db.add(PrefilledFormRequestLog(user_id=current_user.id))
    db.commit()

    return PrefilledFormOut(fields=filled_fields)


def _lock_application_for_update(db: Session, application_id: int) -> None:
    """Take a row lock on the Application for the rest of the request.

    Mirrors `lock_user_for_rate_limit` (app/rate_limit/limiter.py): without
    this, the `status != en_cours` check below is a plain read with no lock,
    and status is only written *after* the network submit call - so two
    concurrent `POST .../confirm` requests for the same application could
    both observe `en_cours`, both call `adapter.submit(...)`, and both post a
    real application to the employer's ATS. That would silently violate the
    "never resubmit" constraint this endpoint is built around.

    PostgreSQL supports `SELECT ... FOR UPDATE` row-level locking; SQLite
    (used in this project's test suite) does not support meaningful
    row-level locking, so on SQLite this is a no-op. That's safe because the
    test suite never issues concurrent requests against the same SQLite
    connection/session, and production runs on PostgreSQL, where the lock
    genuinely applies.
    """
    query = select(Application.id).where(Application.id == application_id)
    if db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    db.execute(query)


def _get_ready_personalized_documents(db: Session, diagnostic_id: int) -> tuple[PersonalizedDocument, PersonalizedDocument] | None:
    cv_document = (
        db.query(PersonalizedDocument)
        .filter(PersonalizedDocument.diagnostic_id == diagnostic_id, PersonalizedDocument.kind == "cv")
        .first()
    )
    lettre_document = (
        db.query(PersonalizedDocument)
        .filter(PersonalizedDocument.diagnostic_id == diagnostic_id, PersonalizedDocument.kind == "lettre")
        .first()
    )
    if cv_document is None or lettre_document is None:
        return None
    return cv_document, lettre_document


@router.post("/{application_id}/confirm", response_model=ApplicationOut)
def confirm_application(
    application_id: int,
    payload: ConfirmApplicationIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> ApplicationOut:
    application = get_owned_application(db, application_id, current_user.id)
    # Lock the row, then refresh from the DB so the status check below sees
    # the latest committed value even if a concurrent confirm request for
    # the same application just released the lock by committing (Postgres).
    _lock_application_for_update(db, application.id)
    db.refresh(application)
    # `echec_soumission` is a valid starting state alongside `en_cours`: a
    # failed submission (e.g. a transient network blip) would otherwise be a
    # permanent dead end, since mark-sent requires
    # `a_soumettre_manuellement`, there is no delete endpoint, and the
    # (user_id, offer_url) unique constraint blocks re-creating the
    # candidature. This does not weaken the "no automatic retry"
    # constraint - the retry is explicitly user-initiated, never silent.
    # The three remaining statuses stay rejected: `a_soumettre_manuellement`
    # is mark-sent's business, and the two `soumise_*` statuses are terminal.
    if application.status not in (APPLICATION_STATUS_EN_COURS, APPLICATION_STATUS_ECHEC_SOUMISSION):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette candidature a déjà été traitée.")

    # get_ats_adapter returns None both when ats_type is None and when it's a
    # non-None value with no registered adapter - both cases mean "nothing we
    # can auto-submit through", so both fall into the manual-submission path.
    adapter = get_ats_adapter(application.ats_type)
    if adapter is None:
        application.status = APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT
        db.commit()
        db.refresh(application)
        return _to_out(application)

    if payload.fields is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Les champs du formulaire pré-rempli sont requis pour la soumission automatique.",
        )

    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    missing = missing_required_profile_fields(profile)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Complétez votre profil avant de continuer: {', '.join(missing)}",
        )
    assert profile is not None  # missing_required_profile_fields(None) always returns non-empty

    documents = _get_ready_personalized_documents(db, application.diagnostic_id)
    if documents is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Générez le CV et la lettre de motivation avant de confirmer la candidature.",
        )
    cv_document, lettre_document = documents

    # `needs_review` is the anti-hallucination flag set at generation time by
    # personalization.verification.cv_needs_review: it means the rewritten CV
    # mentions employers, schools, or dates absent from the reference CV.
    # Auto-submission posts that CV straight to a real employer, so a flagged
    # CV is blocked here until the user reviews or regenerates it. Only
    # reached on the ats_type-eligible path (the adapter-is-None branch has
    # already returned above): in assisted mode the user submits manually
    # after seeing the "à vérifier" badge, so no backend block is warranted.
    # `override_needs_review` is an explicit opt-in for an informed user who
    # has read the flagged CV and judges it fine - it only lifts this block,
    # nothing else, and is a no-op when needs_review is already False.
    if cv_document.needs_review and not payload.override_needs_review:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Ce CV contient des éléments à vérifier avant l'envoi automatique — "
                "relisez-le ou régénérez-le depuis le diagnostic."
            ),
        )

    if cv_document.needs_review and payload.override_needs_review:
        logger.info(
            "Application %s auto-submitted with needs_review override by user %s",
            application.id,
            current_user.id,
        )

    try:
        # Re-discovered rather than reusing the GET .../prefilled-form
        # result: the hidden CSRF/session token there may no longer be
        # valid by the time the user finishes reviewing the form.
        discovered = adapter.discover_form(application.offer_url, profile, current_user.email)
        edited_values = {f.name: f.value for f in payload.fields}
        filled_fields = [
            f.model_copy(update={"value": edited_values.get(f.name, f.value)}) for f in discovered.fields
        ]
        filled_form = discovered.model_copy(update={"fields": filled_fields})

        cv_pdf = storage.download(cv_document.storage_key)
        lettre_pdf = storage.download(lettre_document.storage_key)
        adapter.submit(filled_form, cv_pdf, lettre_pdf)
    except (ATSAdapterError, ObjectStorageError) as exc:
        # No retry: a failed submission is surfaced to the user, never
        # silently resubmitted (which could result in a duplicate
        # application if the first attempt actually went through upstream).
        application.status = APPLICATION_STATUS_ECHEC_SOUMISSION
        application.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    application.status = APPLICATION_STATUS_SOUMISE_AUTO
    # Cleared so a successful retry after an `echec_soumission` doesn't leave
    # the previous attempt's error text hanging off a submitted candidature.
    application.error_message = None
    application.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(application)
    return _to_out(application)


@router.post("/{application_id}/mark-sent", response_model=ApplicationOut)
def mark_sent_manually(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationOut:
    application = get_owned_application(db, application_id, current_user.id)
    if application.status != APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cette candidature n'est pas en attente d'envoi manuel."
        )
    application.status = APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE
    db.commit()
    db.refresh(application)
    return _to_out(application)
