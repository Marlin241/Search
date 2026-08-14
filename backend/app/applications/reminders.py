import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.application import (
    APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
    APPLICATION_STATUS_EN_COURS,
    APPLICATION_STATUS_SOUMISE_AUTO,
    APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE,
    Application,
)
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.notifications.resend_client import (
    EmailSendError,
    send_application_reminders_email,
)

logger = logging.getLogger(__name__)

NOTIFICATION_HOUR = 8
REMINDER_THRESHOLD_DAYS = 7


def _user_timezone(db: Session, user_id: int) -> str:
    saved_search = db.query(SavedSearch).filter(SavedSearch.user_id == user_id).first()
    if saved_search is not None:
        return saved_search.timezone
    return "UTC"


def _is_notification_time(timezone: str, now: datetime) -> bool:
    return now.astimezone(ZoneInfo(timezone)).hour == NOTIFICATION_HOUR


def _process_user(db: Session, user_id: int, now: datetime) -> None:
    cutoff = now.replace(tzinfo=None) - timedelta(days=REMINDER_THRESHOLD_DAYS)

    to_relance = (
        db.query(Application)
        .filter(
            Application.user_id == user_id,
            Application.status.in_(
                [
                    APPLICATION_STATUS_SOUMISE_AUTO,
                    APPLICATION_STATUS_SOUMISE_MANUELLE_CONFIRMEE,
                ]
            ),
            Application.submitted_at <= cutoff,
            Application.reminder_sent_at.is_(None),
        )
        .all()
    )
    to_finalize = (
        db.query(Application)
        .filter(
            Application.user_id == user_id,
            Application.status.in_(
                [
                    APPLICATION_STATUS_A_SOUMETTRE_MANUELLEMENT,
                    APPLICATION_STATUS_EN_COURS,
                ]
            ),
            Application.created_at <= cutoff,
            Application.reminder_sent_at.is_(None),
        )
        .all()
    )

    if not to_relance and not to_finalize:
        return

    user = db.get(User, user_id)
    if user is None:
        return

    try:
        send_application_reminders_email(user.email, to_relance, to_finalize)
    except EmailSendError:
        logger.error(
            "Échec de l'envoi de l'email de rappel de candidatures pour "
            "l'utilisateur %s",
            user_id,
        )
        return

    reminded_at = now.replace(tzinfo=None)
    for application in to_relance + to_finalize:
        application.reminder_sent_at = reminded_at
    db.commit()


def run_application_reminders(db_session_factory: Callable[[], Session]) -> None:
    db = db_session_factory()
    try:
        now = datetime.now(UTC)
        user_ids = [row[0] for row in db.query(Application.user_id).distinct().all()]
        for user_id in user_ids:
            timezone = _user_timezone(db, user_id)
            if not _is_notification_time(timezone, now):
                continue
            try:
                _process_user(db, user_id, now)
            except Exception:
                # Isolation volontairement large, même convention que
                # app.job_search.daily_search.run_daily_search : une panne
                # inattendue pour un utilisateur ne doit jamais empêcher le
                # traitement des autres utilisateurs de ce passage horaire.
                logger.exception(
                    "Échec du traitement des rappels de candidatures pour "
                    "l'utilisateur %s",
                    user_id,
                )
    finally:
        db.close()
