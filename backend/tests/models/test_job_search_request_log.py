from app.models.job_search_request_log import JobSearchRequestLog
from app.models.user import User


def test_create_job_search_request_log_linked_to_user(db_session):
    user = User(email="jane@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()

    db_session.add(JobSearchRequestLog(user_id=user.id))
    db_session.commit()

    fetched = db_session.query(JobSearchRequestLog).filter(JobSearchRequestLog.user_id == user.id).first()
    assert fetched.created_at is not None
