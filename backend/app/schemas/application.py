from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.ats_adapters.schemas import FormField
from app.schemas.diagnostic import DiagnosticReport

FunnelStage = Literal["postule", "entretien_programme", "proposition", "refusee"]


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
    funnel_stage: str
    error_message: str | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    diagnostic: DiagnosticReport


class FunnelStageIn(BaseModel):
    funnel_stage: FunnelStage


class PrefilledFormOut(BaseModel):
    fields: list[FormField]


class ConfirmApplicationIn(BaseModel):
    fields: list[FormField] | None = None
    override_needs_review: bool | None = Field(
        default=False,
        description=(
            "Explicit opt-in to auto-submit a CV flagged needs_review "
            "(the anti-hallucination check). Omit or leave false/null to "
            "keep the default block; has no effect when needs_review is "
            "already false."
        ),
    )
