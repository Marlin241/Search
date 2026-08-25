from datetime import datetime
from typing import Literal

from pydantic import BaseModel

InterviewType = Literal["rh", "manager", "direction", "jury", "autre"]


class InterviewIn(BaseModel):
    scheduled_at: datetime
    interview_type: InterviewType
    location_or_link: str | None = None
    notes: str | None = None


class InterviewUpdateIn(BaseModel):
    scheduled_at: datetime | None = None
    interview_type: InterviewType | None = None
    location_or_link: str | None = None
    notes: str | None = None


class InterviewOut(BaseModel):
    id: int
    application_id: int
    scheduled_at: datetime
    interview_type: str
    location_or_link: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class InterviewCalendarEntryOut(BaseModel):
    id: int
    application_id: int
    scheduled_at: datetime
    interview_type: str
    location_or_link: str | None
    notes: str | None
    company_name: str
    job_title: str
