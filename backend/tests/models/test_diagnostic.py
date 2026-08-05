from app.models.user import User
from app.models.diagnostic import Diagnostic


def test_create_diagnostic_linked_to_user(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    diagnostic = Diagnostic(
        user_id=user.id,
        cv_text="cv text",
        offer_text="offer text",
        overall_score=80,
        structural_score=90,
        structural_issues=["issue 1"],
        semantic_score=70,
        missing_keywords=["Python"],
        recommendations=["Add Python to your skills section"],
    )
    db_session.add(diagnostic)
    db_session.commit()

    fetched = db_session.query(Diagnostic).filter(Diagnostic.user_id == user.id).first()
    assert fetched.overall_score == 80
    assert fetched.structural_issues == ["issue 1"]
    assert fetched.missing_keywords == ["Python"]

    refreshed_user = db_session.query(User).filter(User.id == user.id).first()
    assert len(refreshed_user.diagnostics) == 1


def test_deleting_user_cascades_diagnostics(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    db_session.add(
        Diagnostic(
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
    )
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(Diagnostic).count() == 0
