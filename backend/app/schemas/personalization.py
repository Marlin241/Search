from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PersonalizedDocumentOut(BaseModel):
    kind: str
    needs_review: bool
    created_at: datetime
    updated_at: datetime
    ats_score_before: int | None = None
    ats_score_after: int | None = None
    content_json: dict[str, Any] | None = None
