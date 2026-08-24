from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.personalization.pdf_templates.base import CvStyleOptions
from app.personalization.schemas import RewrittenCv
from app.schemas.diagnostic import DiagnosticReport
from app.schemas.personalization import PersonalizedDocumentOut


class CvRenderPreviewIn(BaseModel):
    content: RewrittenCv
    template: Literal["classic", "modern", "minimal"] = "classic"
    style: CvStyleOptions = CvStyleOptions()


class SavedJobIn(BaseModel):
    offer_url: str
    title: str
    company: str
    location: str | None = None
    snippet: str
    source: str
    ats_type: str | None = None
    salary: str | None = None


class SavedJobOut(BaseModel):
    id: int
    offer_url: str
    title: str
    company: str
    location: str | None
    snippet: str
    source: str
    ats_type: str | None
    salary: str | None
    has_full_offer_text: bool
    created_at: datetime
    updated_at: datetime
    # Populated only by GET /saved-jobs/{id} (the workspace detail view) -
    # None on the GET /saved-jobs list, which is a plain snapshot list.
    latest_diagnostic: DiagnosticReport | None = None
    documents: list[PersonalizedDocumentOut] = []
    application_status: str | None = None
