from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.aggregator.aggregator import build_diagnostic_report
from app.cv_parser.models import CVParseResult
from app.llm_analyzer.analyzer import LLMAnalysisError, SemanticAnalyzer
from app.models.application import APPLICATION_STATUS_EN_COURS, Application
from app.models.candidate_profile import CandidateProfile
from app.models.diagnostic import Diagnostic
from app.offer_ingestion.ingestion import OfferIngestionError, get_offer_text
from app.rules_engine.rules import evaluate_structure


class ApplicationCreationError(Exception):
    pass


class DuplicateApplicationError(ApplicationCreationError):
    pass


class MissingReferenceCvError(ApplicationCreationError):
    pass


def create_application(
    db: Session,
    user_id: int,
    offer_url: str,
    offer_text_override: str | None,
    source: str,
    company_name: str,
    job_title: str,
    ats_type: str | None,
    analyzer: SemanticAnalyzer,
) -> Application:
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if profile is None or not profile.cv_text:
        raise MissingReferenceCvError(
            "Merci d'uploader votre CV de référence sur votre profil avant de lancer une candidature."
        )

    existing = (
        db.query(Application)
        .filter(Application.user_id == user_id, Application.offer_url == offer_url)
        .first()
    )
    if existing is not None:
        raise DuplicateApplicationError("Vous avez déjà une candidature enregistrée pour cette offre.")

    try:
        offer_text = get_offer_text(offer_text_override, offer_url)
    except OfferIngestionError as exc:
        raise ApplicationCreationError(str(exc)) from exc

    parse_result = CVParseResult(
        text=profile.cv_text,
        has_tables=bool(profile.cv_has_tables),
        has_multi_column=bool(profile.cv_has_multi_column),
        has_images=bool(profile.cv_has_images),
        detected_sections=set(profile.cv_detected_sections or []),
    )
    structural = evaluate_structure(parse_result)

    try:
        semantic = analyzer.analyze(profile.cv_text, offer_text)
    except LLMAnalysisError as exc:
        raise ApplicationCreationError(str(exc)) from exc

    report = build_diagnostic_report(structural, semantic)

    diagnostic = Diagnostic(
        user_id=user_id,
        cv_text=profile.cv_text,
        offer_text=offer_text,
        overall_score=report.overall_score,
        structural_score=report.structural_score,
        structural_issues=report.structural_issues,
        semantic_score=report.semantic_score,
        missing_keywords=report.missing_keywords,
        recommendations=report.recommendations,
    )
    db.add(diagnostic)
    db.flush()  # assigns diagnostic.id without committing, so Application can reference it

    application = Application(
        user_id=user_id,
        diagnostic_id=diagnostic.id,
        offer_url=offer_url,
        source=source,
        company_name=company_name,
        job_title=job_title,
        ats_type=ats_type,
        status=APPLICATION_STATUS_EN_COURS,
    )
    db.add(application)
    try:
        db.commit()
    except IntegrityError as exc:
        # The pre-check above is a fast-path only: it can't see a competing
        # request's row that was inserted concurrently between that SELECT
        # and this commit. The `uq_application_user_offer_url` unique
        # constraint is the actual source of truth for dedup, so a
        # constraint violation at commit time is translated into the same
        # DuplicateApplicationError the pre-check raises, rather than
        # letting a raw IntegrityError escape to callers that don't know
        # how to handle it.
        db.rollback()
        raise DuplicateApplicationError(
            "Vous avez déjà une candidature enregistrée pour cette offre."
        ) from exc
    db.refresh(application)
    return application
