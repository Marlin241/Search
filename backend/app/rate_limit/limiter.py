from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.diagnostic import Diagnostic
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.user import User
from app.utils.time import utcnow

MAX_DIAGNOSTICS_PER_HOUR = 10
MAX_PERSONALIZATIONS_PER_HOUR = 10


class RateLimitExceeded(Exception):
    pass


def lock_user_for_rate_limit(db: Session, user_id: int) -> None:
    """Take a row lock on the user's own User row for the rest of the request.

    This serializes diagnostic creation per-user so the rate-limit check and
    the resulting insert are effectively atomic with respect to other
    concurrent requests from the same user, closing a TOCTOU race where N
    concurrent requests could all pass `check_rate_limit` before any of
    their Diagnostic rows exist.

    PostgreSQL supports `SELECT ... FOR UPDATE` row-level locking; SQLite
    (used in this project's test suite) does not support meaningful
    row-level locking, so on SQLite this is a no-op. That's safe because the
    test suite never issues concurrent requests against the same SQLite
    connection/session, and production runs on PostgreSQL, where the lock
    genuinely applies.
    """
    query = select(User.id).where(User.id == user_id)
    if db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    db.execute(query)


def check_rate_limit(db: Session, user_id: int) -> None:
    one_hour_ago = utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count())
        .select_from(Diagnostic)
        .where(
            Diagnostic.user_id == user_id,
            Diagnostic.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_DIAGNOSTICS_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_DIAGNOSTICS_PER_HOUR} diagnostics par heure atteinte. Réessaie plus tard."
        )


def check_personalization_rate_limit(db: Session, user_id: int) -> None:
    """Counts CV and lettre generations combined, over the last hour.

    Backed by PersonalizationRequestLog rather than PersonalizedDocument
    because the latter is upserted (one row per diagnostic+kind, overwritten
    on regeneration) and would not reflect how many generations actually
    happened - repeated regenerations of the same document would only ever
    count as one row.
    """
    one_hour_ago = utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count())
        .select_from(PersonalizationRequestLog)
        .where(
            PersonalizationRequestLog.user_id == user_id,
            PersonalizationRequestLog.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_PERSONALIZATIONS_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_PERSONALIZATIONS_PER_HOUR} générations par heure atteinte. Réessaie plus tard."
        )


from app.models.job_search_request_log import JobSearchRequestLog

MAX_SEARCHES_PER_HOUR = 20


def check_job_search_rate_limit(db: Session, user_id: int) -> None:
    one_hour_ago = utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count())
        .select_from(JobSearchRequestLog)
        .where(
            JobSearchRequestLog.user_id == user_id,
            JobSearchRequestLog.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_SEARCHES_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_SEARCHES_PER_HOUR} recherches par heure atteinte. Réessaie plus tard."
        )


from app.models.compatibility_request_log import CompatibilityRequestLog

MAX_COMPATIBILITY_DETAILS_PER_HOUR = 30


def check_compatibility_detail_rate_limit(db: Session, user_id: int) -> None:
    """Higher than the other LLM-cost limits (10/h) because this call uses
    haiku (cheaper) and multiple clicks per search session are expected."""
    one_hour_ago = utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count())
        .select_from(CompatibilityRequestLog)
        .where(
            CompatibilityRequestLog.user_id == user_id,
            CompatibilityRequestLog.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_COMPATIBILITY_DETAILS_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_COMPATIBILITY_DETAILS_PER_HOUR} détails de compatibilité "
            "par heure atteinte. Réessaie plus tard."
        )


from app.models.interview_prep_request_log import InterviewPrepRequestLog

MAX_INTERVIEW_PREP_PER_HOUR = 5


def check_interview_prep_rate_limit(db: Session, user_id: int) -> None:
    """Low cap relative to the other LLM-cost limits (10/h, 30/h) because
    this pipeline can chain a web-search call (2-5 min) plus a structured
    extraction call - the most expensive/slow generation this app offers."""
    one_hour_ago = utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count())
        .select_from(InterviewPrepRequestLog)
        .where(
            InterviewPrepRequestLog.user_id == user_id,
            InterviewPrepRequestLog.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_INTERVIEW_PREP_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_INTERVIEW_PREP_PER_HOUR} préparations d'entretien "
            "par heure atteinte. Réessaie plus tard."
        )


from app.models.prefilled_form_request_log import PrefilledFormRequestLog

MAX_PREFILLED_FORM_PREVIEWS_PER_HOUR = 10


def check_prefilled_form_rate_limit(db: Session, user_id: int) -> None:
    """Caps GET /applications/{id}/prefilled-form, which runs the
    CustomFieldAnswerer LLM on every call. Set to the same 10/h as the
    diagnostic and personalization limits (rather than job search's 20/h)
    because it is an LLM-cost limit, not a third-party free-tier quota."""
    one_hour_ago = utcnow() - timedelta(hours=1)
    count = db.scalar(
        select(func.count())
        .select_from(PrefilledFormRequestLog)
        .where(
            PrefilledFormRequestLog.user_id == user_id,
            PrefilledFormRequestLog.created_at >= one_hour_ago,
        )
    )
    if count is not None and count >= MAX_PREFILLED_FORM_PREVIEWS_PER_HOUR:
        raise RateLimitExceeded(
            f"Limite de {MAX_PREFILLED_FORM_PREVIEWS_PER_HOUR} prévisualisations de formulaire "
            "par heure atteinte. Réessaie plus tard."
        )
