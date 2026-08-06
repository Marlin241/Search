import pytest
from sqlalchemy.exc import IntegrityError

from app.models.diagnostic import Diagnostic
from app.models.personalized_document import PersonalizedDocument
from app.models.user import User


def _make_diagnostic(db_session) -> Diagnostic:
    user = User(email="jane@example.com", hashed_password="hashed")
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


def test_create_personalized_document_linked_to_diagnostic(db_session):
    diagnostic = _make_diagnostic(db_session)

    document = PersonalizedDocument(
        diagnostic_id=diagnostic.id,
        kind="cv",
        storage_key="users/1/diagnostics/1/cv.pdf",
        needs_review=False,
    )
    db_session.add(document)
    db_session.commit()

    fetched = db_session.query(PersonalizedDocument).filter(PersonalizedDocument.diagnostic_id == diagnostic.id).first()
    assert fetched.kind == "cv"
    assert fetched.storage_key == "users/1/diagnostics/1/cv.pdf"
    assert fetched.needs_review is False
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


def test_unique_constraint_on_diagnostic_id_and_kind(db_session):
    diagnostic = _make_diagnostic(db_session)
    db_session.add(PersonalizedDocument(diagnostic_id=diagnostic.id, kind="cv", storage_key="key-1", needs_review=False))
    db_session.commit()

    db_session.add(PersonalizedDocument(diagnostic_id=diagnostic.id, kind="cv", storage_key="key-2", needs_review=False))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_same_diagnostic_can_have_one_cv_and_one_lettre(db_session):
    diagnostic = _make_diagnostic(db_session)
    db_session.add(PersonalizedDocument(diagnostic_id=diagnostic.id, kind="cv", storage_key="key-cv", needs_review=False))
    db_session.add(PersonalizedDocument(diagnostic_id=diagnostic.id, kind="lettre", storage_key="key-lettre", needs_review=False))
    db_session.commit()  # should not raise

    assert db_session.query(PersonalizedDocument).filter(PersonalizedDocument.diagnostic_id == diagnostic.id).count() == 2
