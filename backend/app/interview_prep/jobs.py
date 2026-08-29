import logging
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session

from app.generation_jobs import state
from app.interview_prep.analyzer import InterviewPrepAnalyzer, InterviewPrepError
from app.job_search.discovery import normalize_company_name
from app.llm.usage import capture_usage, collected
from app.models.candidate_profile import CandidateProfile
from app.models.company_research_cache import CompanyResearchCache
from app.models.diagnostic import Diagnostic
from app.models.interview_prep_dossier import InterviewPrepDossier
from app.models.interview_prep_request_log import InterviewPrepRequestLog
from app.models.llm_call_log import LlmCallLog
from app.models.saved_job import SavedJob
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

_COMPANY_RESEARCH_TTL = timedelta(days=7)


def _get_cached_research(db: Session, company_name: str) -> dict | None:
    normalized = normalize_company_name(company_name)
    cached = (
        db.query(CompanyResearchCache)
        .filter(CompanyResearchCache.company_name == normalized)
        .first()
    )
    if cached is None:
        return None
    if cached.checked_at < utcnow() - _COMPANY_RESEARCH_TTL:
        return None
    return cached.facts_json


def _save_research_cache(db: Session, company_name: str, facts: dict) -> None:
    normalized = normalize_company_name(company_name)
    cached = (
        db.query(CompanyResearchCache)
        .filter(CompanyResearchCache.company_name == normalized)
        .first()
    )
    if cached is None:
        cached = CompanyResearchCache(company_name=normalized, facts_json=facts)
        db.add(cached)
    else:
        cached.facts_json = facts
        cached.checked_at = utcnow()


def run_interview_prep_job(
    job_id: str,
    saved_job_id: int,
    user_id: int,
    persona: str,
    extra_context: str | None,
    use_web_search: bool,
    analyzer: InterviewPrepAnalyzer,
    db_session_factory: Callable[[], Session],
) -> None:
    db = db_session_factory()
    usage_ctx = capture_usage()
    usage_ctx.__enter__()
    try:
        state.advance(job_id, 1, "Analyse du profil et de l'offre")
        saved_job = (
            db.query(SavedJob)
            .filter(SavedJob.id == saved_job_id, SavedJob.user_id == user_id)
            .first()
        )
        if saved_job is None:
            state.fail(job_id, "Offre sauvegardée introuvable.")
            return

        diagnostic = (
            db.query(Diagnostic)
            .filter(Diagnostic.saved_job_id == saved_job.id)
            .order_by(Diagnostic.created_at.desc())
            .first()
        )
        if diagnostic is None:
            state.fail(
                job_id,
                "Aucun diagnostic n'existe pour cette offre. Lancez d'abord un "
                "diagnostic depuis l'onglet Offre.",
            )
            return

        # Fetched for parity with the CV/lettre jobs (candidate context),
        # even though the dossier prompt itself only needs cv_text/offer_text
        # already stored on the diagnostic.
        db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()

        company_research: tuple[str, list[dict]] | None = None
        sources: list[dict] | None = None
        if use_web_search:
            state.advance(job_id, 2, "Recherche des actualités")
            cached_facts = _get_cached_research(db, saved_job.company)
            if cached_facts is not None:
                company_research = (
                    cached_facts.get("synthesis", ""),
                    cached_facts.get("sources", []),
                )
                sources = cached_facts.get("sources", [])
            else:
                synthesis, found_sources = analyzer.research_company(
                    saved_job.company, saved_job.title
                )
                company_research = (synthesis, found_sources)
                sources = found_sources
                if synthesis:
                    _save_research_cache(
                        db,
                        saved_job.company,
                        {"synthesis": synthesis, "sources": found_sources},
                    )

        step_index = 3 if use_web_search else 2
        state.advance(job_id, step_index, "Rédaction du dossier")
        try:
            dossier_content = analyzer.draft_dossier(
                diagnostic.cv_text,
                diagnostic.offer_text,
                diagnostic.missing_keywords,
                diagnostic.recommendations,
                persona,
                extra_context,
                company_research,
            )
        except InterviewPrepError as exc:
            state.fail(job_id, str(exc))
            return

        state.advance(job_id, step_index + 1, "Finalisation")
        dossier = (
            db.query(InterviewPrepDossier)
            .filter(InterviewPrepDossier.saved_job_id == saved_job.id)
            .first()
        )
        if dossier is None:
            dossier = InterviewPrepDossier(saved_job_id=saved_job.id)
            db.add(dossier)
        dossier.persona = persona
        dossier.extra_context = extra_context
        dossier.web_search_used = use_web_search
        dossier.dossier_json = dossier_content.model_dump()
        dossier.sources_json = sources

        # Only counted against the user's hourly quota on genuine success -
        # a failed generation above returns before this point.
        db.add(InterviewPrepRequestLog(user_id=user_id))
        _model, _itok, _otok = collected()
        db.add(
            LlmCallLog(
                user_id=user_id,
                feature="interview_prep",
                model=_model,
                input_tokens=_itok,
                output_tokens=_otok,
            )
        )
        db.commit()
        db.refresh(dossier)

        state.complete(
            job_id,
            result={
                "saved_job_id": saved_job.id,
                "persona": dossier.persona,
                "web_search_used": dossier.web_search_used,
                "dossier": dossier.dossier_json,
                "sources": dossier.sources_json,
                "created_at": dossier.created_at.isoformat(),
                "updated_at": dossier.updated_at.isoformat(),
            },
        )
    except Exception as exc:
        # Last-resort guard: FastAPI BackgroundTasks logs an unhandled
        # exception but otherwise swallows it, which would leave the job
        # stuck at status="running" forever with no way for the client to
        # know it died.
        logger.exception("Interview prep job %s failed unexpectedly", job_id)
        state.fail(job_id, str(exc))
    finally:
        usage_ctx.__exit__(None, None, None)
        db.close()
