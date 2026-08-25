import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.application import (
    FUNNEL_STAGE_ENTRETIEN_PROGRAMME,
    FUNNEL_STAGE_POSTULE,
    FUNNEL_STAGE_PROPOSITION,
    FUNNEL_STAGE_REFUSEE,
    Application,
)
from app.models.interview import Interview
from app.models.saved_job import SavedJob
from app.models.user import User
from app.routers.applications import to_application_out
from app.schemas.dashboard import KanbanBoardOut, KanbanSavedJobOut
from app.schemas.interview import InterviewCalendarEntryOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@router.get("/kanban", response_model=KanbanBoardOut)
def get_kanban_board(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KanbanBoardOut:
    applications = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    applied_offer_urls = {a.offer_url for a in applications}

    saved_jobs = (
        db.query(SavedJob)
        .filter(SavedJob.user_id == current_user.id)
        .order_by(SavedJob.created_at.desc())
        .all()
    )
    sauvegardees = [
        KanbanSavedJobOut(
            id=sj.id,
            title=sj.title,
            company=sj.company,
            offer_url=sj.offer_url,
            created_at=sj.created_at,
        )
        for sj in saved_jobs
        if sj.offer_url not in applied_offer_urls
    ]

    by_stage: dict[str, list[Application]] = {
        FUNNEL_STAGE_POSTULE: [],
        FUNNEL_STAGE_ENTRETIEN_PROGRAMME: [],
        FUNNEL_STAGE_PROPOSITION: [],
        FUNNEL_STAGE_REFUSEE: [],
    }
    for application in applications:
        by_stage.setdefault(application.funnel_stage, []).append(application)

    return KanbanBoardOut(
        sauvegardees=sauvegardees,
        postule=[to_application_out(a) for a in by_stage[FUNNEL_STAGE_POSTULE]],
        entretien_programme=[
            to_application_out(a) for a in by_stage[FUNNEL_STAGE_ENTRETIEN_PROGRAMME]
        ],
        proposition=[to_application_out(a) for a in by_stage[FUNNEL_STAGE_PROPOSITION]],
        refusee=[to_application_out(a) for a in by_stage[FUNNEL_STAGE_REFUSEE]],
    )


@router.get("/calendar", response_model=list[InterviewCalendarEntryOut])
def get_calendar(
    month: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InterviewCalendarEntryOut]:
    if not _MONTH_PATTERN.match(month):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le paramètre 'month' doit être au format YYYY-MM.",
        )
    # Naive datetimes deliberately - Interview.scheduled_at is a naive
    # DateTime column (same convention as every other timestamp column in
    # this codebase, e.g. Application.created_at), so these bounds must be
    # naive too to compare correctly.
    year, month_num = (int(part) for part in month.split("-"))
    range_start = datetime(year, month_num, 1)  # noqa: DTZ001
    range_end = (
        datetime(year + 1, 1, 1)  # noqa: DTZ001
        if month_num == 12
        else datetime(year, month_num + 1, 1)  # noqa: DTZ001
    )

    interviews = (
        db.query(Interview)
        .join(Application, Application.id == Interview.application_id)
        .filter(
            Application.user_id == current_user.id,
            Interview.scheduled_at >= range_start,
            Interview.scheduled_at < range_end,
        )
        .order_by(Interview.scheduled_at.asc())
        .all()
    )
    return [
        InterviewCalendarEntryOut(
            id=interview.id,
            application_id=interview.application_id,
            scheduled_at=interview.scheduled_at,
            interview_type=interview.interview_type,
            location_or_link=interview.location_or_link,
            notes=interview.notes,
            company_name=interview.application.company_name,
            job_title=interview.application.job_title,
        )
        for interview in interviews
    ]
