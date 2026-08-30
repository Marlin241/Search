import logging

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.auth_attempt import AuthAttempt
from app.models.candidate_profile import CandidateProfile
from app.models.compatibility_request_log import CompatibilityRequestLog
from app.models.diagnostic import Diagnostic
from app.models.interview import Interview
from app.models.interview_prep_dossier import InterviewPrepDossier
from app.models.interview_prep_request_log import InterviewPrepRequestLog
from app.models.invite_code import InviteCode
from app.models.job_search_request_log import JobSearchRequestLog
from app.models.llm_call_log import LlmCallLog
from app.models.notified_listing import NotifiedListing
from app.models.password_reset_token import PasswordResetToken
from app.models.personalization_request_log import PersonalizationRequestLog
from app.models.personalized_document import PersonalizedDocument
from app.models.prefilled_form_request_log import PrefilledFormRequestLog
from app.models.saved_job import SavedJob
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.storage.client import ObjectStorage, ObjectStorageError

logger = logging.getLogger(__name__)

# Models with a plain user_id column, deleted directly.
_USER_SCOPED = (
    Application,
    Diagnostic,
    SavedJob,
    SavedSearch,
    CandidateProfile,
    NotifiedListing,
    JobSearchRequestLog,
    PersonalizationRequestLog,
    CompatibilityRequestLog,
    InterviewPrepRequestLog,
    PrefilledFormRequestLog,
    LlmCallLog,
    PasswordResetToken,
)


def delete_account(db: Session, user: User, storage: ObjectStorage) -> None:
    """Purge every row tied to `user` (directly or via diagnostics / saved
    jobs / applications), un-link their invite code, wipe their MinIO
    objects, then delete the user row. Done explicitly (not via ON DELETE
    CASCADE) so it is exercised by the SQLite test suite too."""
    uid = user.id
    email = user.email.lower()

    diag_ids = select(Diagnostic.id).where(Diagnostic.user_id == uid)
    sj_ids = select(SavedJob.id).where(SavedJob.user_id == uid)
    app_ids = select(Application.id).where(Application.user_id == uid)

    db.execute(delete(Interview).where(Interview.application_id.in_(app_ids)))
    db.execute(
        delete(PersonalizedDocument).where(
            PersonalizedDocument.diagnostic_id.in_(diag_ids)
        )
    )
    db.execute(
        delete(InterviewPrepDossier).where(
            InterviewPrepDossier.saved_job_id.in_(sj_ids)
        )
    )

    for model in _USER_SCOPED:
        db.execute(delete(model).where(model.user_id == uid))

    db.execute(
        update(InviteCode)
        .where(InviteCode.used_by_user_id == uid)
        .values(used_by_user_id=None)
    )
    db.execute(delete(AuthAttempt).where(AuthAttempt.identifier.like(f"{email}|%")))

    try:
        storage.delete_prefix(f"users/{uid}/")
    except ObjectStorageError:
        logger.exception("Object purge failed for user %s (DB rows still deleted)", uid)

    db.execute(delete(User).where(User.id == uid))
    db.commit()
