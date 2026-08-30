from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.candidate_profile import CandidateProfile
from app.models.diagnostic import Diagnostic
from app.models.interview_prep_dossier import InterviewPrepDossier
from app.models.personalized_document import PersonalizedDocument
from app.models.saved_job import SavedJob
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.rate_limit.llm_quota import usage_summary


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _row_to_dict(obj) -> dict:
    out: dict = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.name)
        out[col.name] = _iso(value) if isinstance(value, datetime) else value
    return out


def build_account_export(db: Session, user: User) -> dict:
    """Everything we hold on `user`, as plain JSON-serialisable data
    (RGPD portability). Datetimes are ISO strings."""
    profile = db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    diagnostics = list(
        db.scalars(select(Diagnostic).where(Diagnostic.user_id == user.id))
    )
    diag_ids = [d.id for d in diagnostics]
    documents = (
        list(
            db.scalars(
                select(PersonalizedDocument).where(
                    PersonalizedDocument.diagnostic_id.in_(diag_ids)
                )
            )
        )
        if diag_ids
        else []
    )
    saved_jobs = list(db.scalars(select(SavedJob).where(SavedJob.user_id == user.id)))
    sj_ids = [s.id for s in saved_jobs]
    dossiers = (
        list(
            db.scalars(
                select(InterviewPrepDossier).where(
                    InterviewPrepDossier.saved_job_id.in_(sj_ids)
                )
            )
        )
        if sj_ids
        else []
    )

    return {
        "account": {
            "email": user.email,
            "created_at": _iso(user.created_at),
            "consent_version": user.consent_version,
            "consent_accepted_at": _iso(user.consent_accepted_at),
        },
        "profile": _row_to_dict(profile) if profile is not None else None,
        "diagnostics": [_row_to_dict(d) for d in diagnostics],
        "documents": [_row_to_dict(doc) for doc in documents],
        "applications": [
            _row_to_dict(a)
            for a in db.scalars(
                select(Application).where(Application.user_id == user.id)
            )
        ],
        "saved_jobs": [_row_to_dict(s) for s in saved_jobs],
        "saved_searches": [
            _row_to_dict(s)
            for s in db.scalars(
                select(SavedSearch).where(SavedSearch.user_id == user.id)
            )
        ],
        "interview_prep": [_row_to_dict(d) for d in dossiers],
        "usage": usage_summary(db, user),
    }
