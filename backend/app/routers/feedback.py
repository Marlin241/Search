import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.feedback import Feedback
from app.models.user import User
from app.notifications.resend_client import EmailSendError, send_feedback_notification
from app.schemas.feedback import FeedbackIn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def submit_feedback(
    payload: FeedbackIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    db.add(
        Feedback(user_id=current_user.id, page=payload.page, message=payload.message)
    )
    db.commit()
    try:
        send_feedback_notification(
            get_settings().admin_notify_email,
            current_user.email,
            payload.page,
            payload.message,
        )
    except EmailSendError:
        logger.exception("feedback notification email failed")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
