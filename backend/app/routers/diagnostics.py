import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.aggregator.aggregator import build_diagnostic_report
from app.auth.dependencies import get_current_user
from app.cv_parser.parser import MAX_CV_SIZE_BYTES, CVParsingError, parse_cv
from app.database import get_db
from app.llm_analyzer.analyzer import LLMAnalysisError, SemanticAnalyzer
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.models.application import Application
from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
from app.models.user import User
from app.offer_ingestion.ingestion import OfferIngestionError, get_offer_text
from app.rate_limit.limiter import (
    RateLimitExceeded,
    check_rate_limit,
    lock_user_for_rate_limit,
)
from app.rules_engine.rules import evaluate_structure
from app.schemas.diagnostic import DiagnosticReport
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.post("", response_model=DiagnosticReport, status_code=status.HTTP_201_CREATED)
def create_diagnostic(
    cv_file: UploadFile = File(...),
    offer_text: str | None = Form(None, max_length=50000),
    offer_url: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analyzer: SemanticAnalyzer = Depends(get_semantic_analyzer),
) -> DiagnosticReport:
    # Lock the user's row for the duration of this request BEFORE checking
    # the rate limit. This serializes diagnostic creation per-user: a second
    # concurrent request for the same user blocks here until the first
    # request's entire pipeline (parse -> offer -> LLM -> insert -> commit)
    # finishes and releases the lock at db.commit(). That guarantees the
    # rate-limit count below always reflects any in-flight sibling request,
    # closing the TOCTOU bypass. See app/rate_limit/limiter.py for details.
    lock_user_for_rate_limit(db, current_user.id)

    try:
        check_rate_limit(db, current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc

    # Check the declared upload size (from Content-Length, via Starlette's
    # UploadFile.size) before reading the body into memory, so an oversized
    # upload doesn't get fully buffered just to be rejected afterwards. Some
    # clients don't send a size (cv_file.size is None); in that case we fall
    # back to the existing post-read check inside parse_cv.
    if cv_file.size is not None and cv_file.size > MAX_CV_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier dépasse la taille maximale autorisée (5 Mo).",
        )

    try:
        cv_bytes = cv_file.file.read()
        parsed_cv = parse_cv(cv_bytes, cv_file.filename or "")
    except CVParsingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    try:
        offer = get_offer_text(offer_text, offer_url)
    except OfferIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    structural = evaluate_structure(parsed_cv)

    try:
        semantic = analyzer.analyze(parsed_cv.text, offer)
    except LLMAnalysisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    report = build_diagnostic_report(structural, semantic)

    diagnostic = Diagnostic(
        user_id=current_user.id,
        cv_text=parsed_cv.text,
        offer_text=offer,
        overall_score=report.overall_score,
        structural_score=report.structural_score,
        structural_issues=report.structural_issues,
        semantic_score=report.semantic_score,
        missing_keywords=report.missing_keywords,
        recommendations=report.recommendations,
    )
    db.add(diagnostic)
    db.commit()
    db.refresh(diagnostic)

    return report.model_copy(
        update={"id": diagnostic.id, "created_at": diagnostic.created_at}
    )


@router.get("", response_model=list[DiagnosticReport])
def list_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DiagnosticReport]:
    diagnostics = (
        db.query(Diagnostic)
        .filter(Diagnostic.user_id == current_user.id)
        .order_by(Diagnostic.created_at.desc())
        .all()
    )
    return [
        DiagnosticReport(
            id=d.id,
            created_at=d.created_at,
            overall_score=d.overall_score,
            structural_score=d.structural_score,
            structural_issues=d.structural_issues,
            semantic_score=d.semantic_score,
            missing_keywords=d.missing_keywords,
            recommendations=d.recommendations,
        )
        for d in diagnostics
    ]


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> None:
    diagnostic_ids = [
        row[0]
        for row in db.query(Diagnostic.id)
        .filter(Diagnostic.user_id == current_user.id)
        .all()
    ]

    # Collected before deletion, and PersonalizedDocument rows are deleted
    # explicitly below rather than relying on the FK's ondelete="CASCADE":
    # this is a bulk `.delete()` query (not per-instance `db.delete(...)`),
    # which bypasses SQLAlchemy ORM-level relationship cascades, and SQLite
    # (used in the test suite) doesn't enforce FK-level cascade unless
    # `PRAGMA foreign_keys=ON` is explicitly set. Explicit deletion works
    # correctly on both SQLite and production PostgreSQL.
    documents = (
        db.query(PersonalizedDocument)
        .filter(PersonalizedDocument.diagnostic_id.in_(diagnostic_ids))
        .all()
    )
    storage_keys = [document.storage_key for document in documents]

    # Application rows need the same explicit bulk deletion as
    # PersonalizedDocument above, and for the same reason: this endpoint
    # uses bulk `.delete()` queries, which bypass SQLAlchemy ORM-level
    # relationship cascades, and SQLite (used in the test suite) doesn't
    # enforce FK-level ondelete="CASCADE" unless PRAGMA foreign_keys=ON is
    # explicitly set. Deleted before PersonalizedDocument/Diagnostic so no
    # FK is ever left dangling mid-purge on backends that do enforce it.
    db.query(Application).filter(Application.diagnostic_id.in_(diagnostic_ids)).delete(
        synchronize_session=False
    )

    db.query(PersonalizedDocument).filter(
        PersonalizedDocument.diagnostic_id.in_(diagnostic_ids)
    ).delete(synchronize_session=False)
    db.query(Diagnostic).filter(Diagnostic.user_id == current_user.id).delete()
    db.commit()

    for key in storage_keys:
        try:
            storage.delete(key)
        except ObjectStorageError:
            # The DB rows (source of truth for the RGPD purge) are already
            # gone at this point; a MinIO object left behind by a transient
            # storage failure is logged for manual follow-up rather than
            # failing the whole purge request.
            logger.warning("Failed to delete MinIO object %s during RGPD purge", key)
