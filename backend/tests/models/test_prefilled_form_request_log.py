from app.models.prefilled_form_request_log import PrefilledFormRequestLog
from app.models.user import User


def test_create_prefilled_form_request_log_linked_to_user(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(PrefilledFormRequestLog(user_id=user.id))
    db_session.commit()

    fetched = (
        db_session.query(PrefilledFormRequestLog)
        .filter(PrefilledFormRequestLog.user_id == user.id)
        .first()
    )
    assert fetched.created_at is not None
