import pytest
from sqlalchemy.exc import IntegrityError

from app.models.candidate_profile import CandidateProfile
from app.models.user import User


def _make_user(db_session) -> User:
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    return user


def test_create_candidate_profile_with_contact_fields(db_session):
    user = _make_user(db_session)

    profile = CandidateProfile(
        user_id=user.id,
        full_name="Jane Doe",
        phone="0612345678",
        work_authorization="Autorisée à travailler en France/UE",
    )
    db_session.add(profile)
    db_session.commit()

    fetched = db_session.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    assert fetched.full_name == "Jane Doe"
    assert fetched.address is None
    assert fetched.cv_text is None
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


def test_cv_fields_store_parsed_reference_cv(db_session):
    user = _make_user(db_session)

    profile = CandidateProfile(
        user_id=user.id,
        full_name="Jane Doe",
        phone="0612345678",
        work_authorization="Autorisée à travailler en France/UE",
        cv_text="Jane Doe\nExpérience...",
        cv_filename="cv.pdf",
        cv_has_tables=False,
        cv_has_multi_column=False,
        cv_has_images=False,
        cv_detected_sections=["experience", "education", "skills"],
    )
    db_session.add(profile)
    db_session.commit()

    fetched = db_session.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    assert fetched.cv_text.startswith("Jane Doe")
    assert fetched.cv_detected_sections == ["experience", "education", "skills"]


def test_unique_constraint_on_user_id(db_session):
    user = _make_user(db_session)
    db_session.add(
        CandidateProfile(user_id=user.id, full_name="Jane", phone="0600000000", work_authorization="FR/UE")
    )
    db_session.commit()

    db_session.add(
        CandidateProfile(user_id=user.id, full_name="Jane 2", phone="0611111111", work_authorization="FR/UE")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
