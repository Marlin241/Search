from app.auth.account_deletion import delete_account
from app.models.application import Application
from app.models.candidate_profile import CandidateProfile
from app.models.compatibility_request_log import CompatibilityRequestLog
from app.models.diagnostic import Diagnostic
from app.models.interview import Interview
from app.models.interview_prep_dossier import InterviewPrepDossier
from app.models.invite_code import InviteCode
from app.models.llm_call_log import LlmCallLog
from app.models.personalized_document import PersonalizedDocument
from app.models.saved_job import SavedJob
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.utils.time import utcnow


class _FakeStorage:
    def __init__(self):
        self.deleted_prefixes: list[str] = []

    def delete_prefix(self, prefix: str) -> int:
        self.deleted_prefixes.append(prefix)
        return 0


def _diag(user_id: int) -> Diagnostic:
    return Diagnostic(
        user_id=user_id,
        cv_text="c",
        offer_text="o",
        overall_score=1,
        structural_score=1,
        structural_issues=[],
        semantic_score=1,
        missing_keywords=[],
        recommendations=[],
    )


def _seed_full_user(db) -> User:
    u = User(email="u@e.com", hashed_password="x")
    db.add(u)
    db.flush()
    d = _diag(u.id)
    sj = SavedJob(
        user_id=u.id,
        offer_url="http://x",
        title="t",
        company="Acme",
        snippet="s",
        source="adzuna",
    )
    db.add_all([d, sj])
    db.flush()
    app_ = Application(
        user_id=u.id,
        diagnostic_id=d.id,
        offer_url="http://x",
        source="adzuna",
        company_name="Acme",
        job_title="Dev",
    )
    db.add(app_)
    db.flush()
    db.add_all(
        [
            PersonalizedDocument(diagnostic_id=d.id, kind="cv", storage_key="k"),
            Interview(
                application_id=app_.id,
                scheduled_at=utcnow(),
                interview_type="visio",
            ),
            InterviewPrepDossier(
                saved_job_id=sj.id,
                persona="coach",
                web_search_used=False,
                dossier_json={},
            ),
            CandidateProfile(user_id=u.id),
            SavedSearch(user_id=u.id, keywords="python"),
            CompatibilityRequestLog(user_id=u.id),
            LlmCallLog(user_id=u.id, feature="cv"),
            InviteCode(code="c1", used_by_user_id=u.id),
        ]
    )
    db.commit()
    return u


def test_delete_account_removes_everything(db_session):
    u = _seed_full_user(db_session)
    uid = u.id
    storage = _FakeStorage()

    delete_account(db_session, u, storage)

    assert db_session.get(User, uid) is None
    for model in (
        Diagnostic,
        SavedJob,
        Application,
        CandidateProfile,
        SavedSearch,
        CompatibilityRequestLog,
        LlmCallLog,
        PersonalizedDocument,
        InterviewPrepDossier,
        Interview,
    ):
        assert db_session.query(model).count() == 0, model
    code = db_session.query(InviteCode).one()
    assert code.used_by_user_id is None  # unlinked, not deleted
    assert storage.deleted_prefixes == [f"users/{uid}/"]


def test_delete_account_leaves_other_users_untouched(db_session):
    keep = User(email="keep@e.com", hashed_password="x")
    db_session.add(keep)
    db_session.commit()
    db_session.add(_diag(keep.id))
    db_session.commit()

    victim = _seed_full_user(db_session)
    delete_account(db_session, victim, _FakeStorage())

    assert db_session.get(User, keep.id) is not None
    assert db_session.query(Diagnostic).count() == 1
