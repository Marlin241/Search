import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.application import APPLICATION_STATUS_EN_COURS, Application
from app.models.diagnostic import Diagnostic
from app.models.user import User


def _make_diagnostic(db_session) -> Diagnostic:
    user = User(email=f"jane-{uuid.uuid4()}@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    diagnostic = Diagnostic(
        user_id=user.id,
        cv_text="cv",
        offer_text="offer",
        overall_score=1,
        structural_score=1,
        structural_issues=[],
        semantic_score=1,
        missing_keywords=[],
        recommendations=[],
    )
    db_session.add(diagnostic)
    db_session.commit()
    return diagnostic


def test_create_application_linked_to_diagnostic(db_session):
    diagnostic = _make_diagnostic(db_session)

    application = Application(
        user_id=diagnostic.user_id,
        diagnostic_id=diagnostic.id,
        offer_url="https://boards.greenhouse.io/acme/jobs/123",
        source="greenhouse",
        company_name="Acme",
        job_title="Développeuse Full Stack",
        ats_type="greenhouse",
        status=APPLICATION_STATUS_EN_COURS,
    )
    db_session.add(application)
    db_session.commit()

    fetched = db_session.query(Application).filter(Application.diagnostic_id == diagnostic.id).first()
    assert fetched.status == APPLICATION_STATUS_EN_COURS
    assert fetched.submitted_at is None
    assert fetched.error_message is None


def test_unique_constraint_on_user_id_and_offer_url(db_session):
    diagnostic = _make_diagnostic(db_session)
    db_session.add(
        Application(
            user_id=diagnostic.user_id,
            diagnostic_id=diagnostic.id,
            offer_url="https://example.com/job/1",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            status=APPLICATION_STATUS_EN_COURS,
        )
    )
    db_session.commit()

    diagnostic_2 = _make_diagnostic(db_session)
    db_session.add(
        Application(
            user_id=diagnostic.user_id,
            diagnostic_id=diagnostic_2.id,
            offer_url="https://example.com/job/1",
            source="manual",
            company_name="Acme",
            job_title="Dev",
            ats_type=None,
            status=APPLICATION_STATUS_EN_COURS,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_diagnostic_cascades_to_application(db_session):
    diagnostic = _make_diagnostic(db_session)
    application = Application(
        user_id=diagnostic.user_id,
        diagnostic_id=diagnostic.id,
        offer_url="https://example.com/job/2",
        source="manual",
        company_name="Acme",
        job_title="Dev",
        ats_type=None,
        status=APPLICATION_STATUS_EN_COURS,
    )
    db_session.add(application)
    db_session.commit()
    application_id = application.id

    db_session.delete(diagnostic)
    db_session.commit()

    assert db_session.query(Application).filter(Application.id == application_id).first() is None
