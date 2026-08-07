import pytest

from app.applications.service import (
    ApplicationCreationError,
    DuplicateApplicationError,
    MissingReferenceCvError,
    create_application,
)
from app.llm_analyzer.analyzer import LLMAnalysisError, SemanticReport
from app.models.application import Application
from app.models.candidate_profile import CandidateProfile
from app.models.diagnostic import Diagnostic
from app.models.user import User


class FakeAnalyzer:
    def __init__(self, report=None, error=None):
        self._report = report or SemanticReport(score=70, missing_keywords=["Docker"], recommendations=["Add Docker"])
        self._error = error
        self.calls = 0

    def analyze(self, cv_text, offer_text):
        self.calls += 1
        if self._error:
            raise self._error
        return self._report


def _make_user_with_profile(db_session, cv_text: str = "Jane Doe\nExpérience\nDéveloppeuse") -> User:
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    profile = CandidateProfile(
        user_id=user.id,
        full_name="Jane Doe",
        phone="0600000000",
        work_authorization="FR/UE",
        cv_text=cv_text,
        cv_has_tables=False,
        cv_has_multi_column=False,
        cv_has_images=False,
        cv_detected_sections=["experience"],
    )
    db_session.add(profile)
    db_session.commit()
    return user


def test_create_application_success(db_session):
    user = _make_user_with_profile(db_session)
    analyzer = FakeAnalyzer()

    application = create_application(
        db_session,
        user_id=user.id,
        offer_url="https://example.com/job/1",
        offer_text_override="Nous recherchons un développeur Python avec Docker.",
        source="manual",
        company_name="Acme",
        job_title="Développeur Python",
        ats_type=None,
        analyzer=analyzer,
    )

    assert application.status == "en_cours"
    assert application.offer_url == "https://example.com/job/1"
    diagnostic = db_session.query(Diagnostic).filter(Diagnostic.id == application.diagnostic_id).first()
    assert diagnostic is not None
    assert diagnostic.cv_text.startswith("Jane Doe")
    assert diagnostic.missing_keywords == ["Docker"]
    assert analyzer.calls == 1


def test_create_application_raises_without_reference_cv(db_session):
    user = User(email="noprofile@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    analyzer = FakeAnalyzer()

    with pytest.raises(MissingReferenceCvError):
        create_application(
            db_session,
            user_id=user.id,
            offer_url="https://example.com/job/1",
            offer_text_override="Offre.",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            analyzer=analyzer,
        )
    assert analyzer.calls == 0  # missing-profile check never reaches the LLM


def test_create_application_raises_on_duplicate_offer_url(db_session):
    user = _make_user_with_profile(db_session)
    analyzer = FakeAnalyzer()
    create_application(
        db_session,
        user_id=user.id,
        offer_url="https://example.com/job/1",
        offer_text_override="Offre.",
        source="manual",
        company_name="Acme",
        job_title="Dev",
        ats_type=None,
        analyzer=analyzer,
    )

    with pytest.raises(DuplicateApplicationError):
        create_application(
            db_session,
            user_id=user.id,
            offer_url="https://example.com/job/1",
            offer_text_override="Offre.",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            analyzer=analyzer,
        )
    assert analyzer.calls == 1  # second attempt never reached the LLM call


def test_create_application_wraps_llm_analysis_error_and_does_not_persist(db_session):
    user = _make_user_with_profile(db_session)
    analyzer = FakeAnalyzer(error=LLMAnalysisError("boom"))

    with pytest.raises(ApplicationCreationError):
        create_application(
            db_session,
            user_id=user.id,
            offer_url="https://example.com/job/1",
            offer_text_override="Offre.",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            analyzer=analyzer,
        )
    assert db_session.query(Application).count() == 0
    assert db_session.query(Diagnostic).count() == 0


def test_create_application_wraps_offer_ingestion_error(db_session):
    user = _make_user_with_profile(db_session)

    with pytest.raises(ApplicationCreationError):
        create_application(
            db_session,
            user_id=user.id,
            offer_url="file:///etc/passwd",  # rejected by scrape_offer's URL validation, no network call
            offer_text_override=None,
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            analyzer=FakeAnalyzer(),
        )


def test_create_application_wraps_commit_time_duplicate_race(db_session):
    """Simulates the TOCTOU race between the dedup pre-check and the final
    commit: a competing Application row for the same (user_id, offer_url) is
    added on the session but deliberately left uncommitted before calling
    create_application. The db_session fixture is configured with
    autoflush=False (see conftest.py), so the pre-check's SELECT does not see
    the pending row -- exactly like a concurrent request's in-flight,
    uncommitted transaction would be invisible to this session. The pending
    row still gets flushed to the database alongside create_application's own
    writes (via its explicit db.flush() before building Application), so the
    `uq_application_user_offer_url` unique constraint fires at
    create_application's own db.commit(). That commit-time IntegrityError
    must be translated into DuplicateApplicationError, not escape raw.
    """
    user = _make_user_with_profile(db_session)
    analyzer = FakeAnalyzer()
    offer_url = "https://example.com/job/race"

    competing_diagnostic = Diagnostic(
        user_id=user.id,
        cv_text="CV",
        offer_text="Offer",
        overall_score=50,
        structural_score=50,
        structural_issues=[],
        semantic_score=50,
        missing_keywords=[],
        recommendations=[],
    )
    db_session.add(competing_diagnostic)
    db_session.flush()  # only to assign competing_diagnostic.id; still uncommitted

    competing_application = Application(
        user_id=user.id,
        diagnostic_id=competing_diagnostic.id,
        offer_url=offer_url,
        source="manual",
        company_name="Acme",
        job_title="Dev",
        status="en_cours",
    )
    db_session.add(competing_application)
    # Deliberately not committed: stands in for a concurrent request's
    # in-flight transaction that create_application's pre-check cannot see.

    with pytest.raises(DuplicateApplicationError):
        create_application(
            db_session,
            user_id=user.id,
            offer_url=offer_url,
            offer_text_override="Offre.",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            analyzer=analyzer,
        )
