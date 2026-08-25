import logging
from collections.abc import Callable
from typing import Literal

from fpdf.errors import FPDFException
from sqlalchemy.orm import Session

from app.aggregator.aggregator import build_diagnostic_report
from app.cv_parser.models import CVParseResult
from app.generation_jobs import state
from app.llm_analyzer.analyzer import SemanticAnalyzer
from app.models.candidate_profile import CandidateProfile
from app.models.diagnostic import Diagnostic
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.personalized_document import PersonalizedDocument
from app.personalization.analyzer import (
    CoverLetterGenerator,
    CvRewriter,
    PersonalizationError,
)
from app.personalization.pdf_generator import render_cover_letter_pdf
from app.personalization.pdf_templates import CvStyleOptions, render_cv
from app.personalization.schemas import RewrittenCv
from app.personalization.verification import cv_needs_review
from app.rules_engine.rules import evaluate_structure
from app.storage.client import ObjectStorage, ObjectStorageError

logger = logging.getLogger(__name__)


def _storage_key(user_id: int, diagnostic_id: int, kind: str) -> str:
    return f"users/{user_id}/diagnostics/{diagnostic_id}/{kind}.pdf"


def _flatten_cv_text(rewritten: RewrittenCv) -> str:
    parts = [rewritten.summary]
    for entry in rewritten.experience:
        parts.append(f"{entry.title} {entry.company} {entry.dates}")
        parts.extend(entry.bullets)
    parts.extend(rewritten.education)
    parts.extend(rewritten.skills)
    return "\n".join(parts)


def _score_rewritten_cv(
    rewritten: RewrittenCv, offer_text: str, analyzer: SemanticAnalyzer
) -> int:
    """Re-run the same scoring the original CV went through (rules_engine +
    SemanticAnalyzer), no new formula. The rewrite always has all three
    required sections and no tables/columns/images by construction (it's
    LLM-authored plain structured text, not a parsed file), so the
    synthetic CVParseResult only needs to encode that."""
    flattened = _flatten_cv_text(rewritten)
    structural = evaluate_structure(
        CVParseResult(
            text=flattened,
            has_tables=False,
            has_multi_column=False,
            has_images=False,
            detected_sections={"experience", "education", "skills"},
        )
    )
    semantic = analyzer.analyze(flattened, offer_text)
    return build_diagnostic_report(structural, semantic).overall_score


def run_cv_generation_job(
    job_id: str,
    diagnostic_id: int,
    user_id: int,
    template: Literal["classic", "modern", "minimal"],
    target_language: str,
    rewriter: CvRewriter,
    analyzer: SemanticAnalyzer,
    storage: ObjectStorage,
    db_session_factory: Callable[[], Session],
) -> None:
    db = db_session_factory()
    try:
        state.advance(job_id, 1, "Analyse du CV")
        diagnostic = (
            db.query(Diagnostic)
            .filter(Diagnostic.id == diagnostic_id, Diagnostic.user_id == user_id)
            .first()
        )
        if diagnostic is None:
            state.fail(job_id, "Diagnostic introuvable.")
            return
        profile = (
            db.query(CandidateProfile)
            .filter(CandidateProfile.user_id == user_id)
            .first()
        )

        state.advance(job_id, 2, "Génération du contenu")
        style = CvStyleOptions()
        try:
            rewritten = rewriter.rewrite(
                diagnostic.cv_text,
                diagnostic.offer_text,
                diagnostic.missing_keywords,
                diagnostic.recommendations,
                template=template,
                target_language=target_language,
            )
            pdf_bytes, page_count = render_cv(template, rewritten, profile, style)
            # The rewrite prompt already asks the model to fit a single A4
            # page, but that's not guaranteed - retry once with a stricter
            # prompt if it still overflows. Best-effort: if the retry itself
            # fails, keep the first (over-length) result.
            if page_count > 1:
                try:
                    retried = rewriter.rewrite(
                        diagnostic.cv_text,
                        diagnostic.offer_text,
                        diagnostic.missing_keywords,
                        diagnostic.recommendations,
                        stricter_length=True,
                        template=template,
                        target_language=target_language,
                    )
                    retried_bytes, retried_count = render_cv(
                        template, retried, profile, style
                    )
                    rewritten, pdf_bytes, page_count = (
                        retried,
                        retried_bytes,
                        retried_count,
                    )
                except (PersonalizationError, FPDFException):
                    pass
        except PersonalizationError as exc:
            state.fail(job_id, str(exc))
            return
        except FPDFException:
            state.fail(job_id, "La génération du PDF a échoué.")
            return

        state.advance(job_id, 3, "Vérification anti-hallucination")
        needs_review = cv_needs_review(diagnostic.cv_text, rewritten)

        state.advance(job_id, 4, "Mise en page PDF")
        key = _storage_key(user_id, diagnostic.id, "cv")
        try:
            storage.upload(key, pdf_bytes)
        except ObjectStorageError as exc:
            state.fail(job_id, str(exc))
            return

        state.advance(job_id, 5, "Calcul du score ATS")
        ats_score_before = diagnostic.overall_score
        ats_score_after = _score_rewritten_cv(
            rewritten, diagnostic.offer_text, analyzer
        )

        document = (
            db.query(PersonalizedDocument)
            .filter(
                PersonalizedDocument.diagnostic_id == diagnostic.id,
                PersonalizedDocument.kind == "cv",
            )
            .first()
        )
        if document is None:
            document = PersonalizedDocument(
                diagnostic_id=diagnostic.id, kind="cv", storage_key=key
            )
            db.add(document)
        document.storage_key = key
        document.needs_review = needs_review
        document.content_json = rewritten.model_dump()
        document.ats_score_before = ats_score_before
        document.ats_score_after = ats_score_after

        # Only counted against the user's hourly quota on genuine success -
        # a failed generation above returns before this point and consumes
        # no PersonalizationRequestLog row.
        db.add(PersonalizationRequestLog(user_id=user_id))
        db.commit()
        db.refresh(document)

        state.complete(
            job_id,
            result={
                "kind": document.kind,
                "needs_review": document.needs_review,
                "ats_score_before": ats_score_before,
                "ats_score_after": ats_score_after,
                "content": rewritten.model_dump(),
                "template": template,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
            },
        )
    except Exception as exc:
        # Last-resort guard: FastAPI BackgroundTasks logs an unhandled
        # exception but otherwise swallows it, which would leave the job
        # stuck at status="running" forever with no way for the client to
        # know it died.
        logger.exception("CV generation job %s failed unexpectedly", job_id)
        state.fail(job_id, str(exc))
    finally:
        db.close()


def run_letter_generation_job(
    job_id: str,
    diagnostic_id: int,
    user_id: int,
    tone: Literal["sobre", "chaleureux", "direct", "formel"],
    generator: CoverLetterGenerator,
    storage: ObjectStorage,
    db_session_factory: Callable[[], Session],
) -> None:
    db = db_session_factory()
    try:
        state.advance(job_id, 1, "Analyse de l'offre")
        diagnostic = (
            db.query(Diagnostic)
            .filter(Diagnostic.id == diagnostic_id, Diagnostic.user_id == user_id)
            .first()
        )
        if diagnostic is None:
            state.fail(job_id, "Diagnostic introuvable.")
            return

        state.advance(job_id, 2, "Rédaction de la lettre")
        try:
            letter = generator.generate(
                diagnostic.cv_text,
                diagnostic.offer_text,
                diagnostic.missing_keywords,
                diagnostic.recommendations,
                tone=tone,
            )
        except PersonalizationError as exc:
            state.fail(job_id, str(exc))
            return

        state.advance(job_id, 3, "Mise en page PDF")
        try:
            pdf_bytes = render_cover_letter_pdf(letter)
        except FPDFException:
            state.fail(job_id, "La génération du PDF a échoué.")
            return

        key = _storage_key(user_id, diagnostic.id, "lettre")
        try:
            storage.upload(key, pdf_bytes)
        except ObjectStorageError as exc:
            state.fail(job_id, str(exc))
            return

        document = (
            db.query(PersonalizedDocument)
            .filter(
                PersonalizedDocument.diagnostic_id == diagnostic.id,
                PersonalizedDocument.kind == "lettre",
            )
            .first()
        )
        if document is None:
            document = PersonalizedDocument(
                diagnostic_id=diagnostic.id, kind="lettre", storage_key=key
            )
            db.add(document)
        document.storage_key = key
        document.needs_review = False

        db.add(PersonalizationRequestLog(user_id=user_id))
        db.commit()
        db.refresh(document)

        state.complete(
            job_id,
            result={
                "kind": document.kind,
                "needs_review": document.needs_review,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
            },
        )
    except Exception as exc:
        logger.exception("Letter generation job %s failed unexpectedly", job_id)
        state.fail(job_id, str(exc))
    finally:
        db.close()
