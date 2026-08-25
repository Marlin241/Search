from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.application import Application
from app.models.interview import Interview
from app.models.user import User
from app.routers.applications import get_owned_application
from app.schemas.interview import InterviewIn, InterviewOut, InterviewUpdateIn

router = APIRouter(tags=["interviews"])


def _to_out(interview: Interview) -> InterviewOut:
    return InterviewOut(
        id=interview.id,
        application_id=interview.application_id,
        scheduled_at=interview.scheduled_at,
        interview_type=interview.interview_type,
        location_or_link=interview.location_or_link,
        notes=interview.notes,
        created_at=interview.created_at,
        updated_at=interview.updated_at,
    )


def _get_owned_interview(db: Session, interview_id: int, user_id: int) -> Interview:
    interview = (
        db.query(Interview)
        .join(Application, Application.id == Interview.application_id)
        .filter(Interview.id == interview_id, Application.user_id == user_id)
        .first()
    )
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entretien introuvable."
        )
    return interview


@router.post(
    "/applications/{application_id}/interviews",
    response_model=InterviewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_interview(
    application_id: int,
    payload: InterviewIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewOut:
    get_owned_application(db, application_id, current_user.id)
    interview = Interview(application_id=application_id, **payload.model_dump())
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return _to_out(interview)


@router.get(
    "/applications/{application_id}/interviews", response_model=list[InterviewOut]
)
def list_interviews(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InterviewOut]:
    get_owned_application(db, application_id, current_user.id)
    interviews = (
        db.query(Interview)
        .filter(Interview.application_id == application_id)
        .order_by(Interview.scheduled_at.asc())
        .all()
    )
    return [_to_out(i) for i in interviews]


@router.patch("/interviews/{interview_id}", response_model=InterviewOut)
def update_interview(
    interview_id: int,
    payload: InterviewUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewOut:
    interview = _get_owned_interview(db, interview_id, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(interview, field, value)
    db.commit()
    db.refresh(interview)
    return _to_out(interview)


@router.delete("/interviews/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    interview = _get_owned_interview(db, interview_id, current_user.id)
    db.delete(interview)
    db.commit()
