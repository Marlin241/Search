from datetime import datetime
from typing import Any

from pydantic import BaseModel


class InterviewPrepRequestIn(BaseModel):
    persona: str
    extra_context: str | None = None
    use_web_search: bool = False


class InterviewPrepDossierOut(BaseModel):
    saved_job_id: int
    persona: str
    extra_context: str | None
    web_search_used: bool
    dossier: dict[str, Any]
    sources: list[dict[str, Any]] | None
    created_at: datetime
    updated_at: datetime
