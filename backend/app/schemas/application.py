from datetime import datetime

from pydantic import BaseModel

from app.ats_adapters.schemas import FormField
from app.schemas.diagnostic import DiagnosticReport


class ApplicationCreateIn(BaseModel):
    offer_url: str
    offer_text: str | None = None
    source: str
    company_name: str
    job_title: str
    ats_type: str | None = None


class ApplicationOut(BaseModel):
    id: int
    diagnostic_id: int
    offer_url: str
    source: str
    company_name: str
    job_title: str
    ats_type: str | None
    status: str
    error_message: str | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    diagnostic: DiagnosticReport


class PrefilledFormOut(BaseModel):
    fields: list[FormField]


class ConfirmApplicationIn(BaseModel):
    fields: list[FormField] | None = None
