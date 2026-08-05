from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.diagnostic import Diagnostic
from app.cv_parser.parser import parse_cv, CVParsingError
from app.offer_ingestion.ingestion import get_offer_text, OfferIngestionError
from app.rules_engine.rules import evaluate_structure
from app.llm_analyzer.analyzer import SemanticAnalyzer, LLMAnalysisError
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.aggregator.aggregator import build_diagnostic_report
from app.schemas.diagnostic import DiagnosticReport
from app.rate_limit.limiter import check_rate_limit, lock_user_for_rate_limit, RateLimitExceeded

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.post("", response_model=DiagnosticReport, status_code=status.HTTP_201_CREATED)
def create_diagnostic(
    cv_file: UploadFile = File(...),
    offer_text: str | None = Form(None),
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
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    try:
        cv_bytes = cv_file.file.read()
        parsed_cv = parse_cv(cv_bytes, cv_file.filename or "")
    except CVParsingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        offer = get_offer_text(offer_text, offer_url)
    except OfferIngestionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    structural = evaluate_structure(parsed_cv)

    try:
        semantic = analyzer.analyze(parsed_cv.text, offer)
    except LLMAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    report = build_diagnostic_report(structural, semantic)

    db.add(
        Diagnostic(
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
    )
    db.commit()

    return report


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
) -> None:
    db.query(Diagnostic).filter(Diagnostic.user_id == current_user.id).delete()
    db.commit()
