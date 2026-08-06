from datetime import datetime

from pydantic import BaseModel


class PersonalizedDocumentOut(BaseModel):
    kind: str
    needs_review: bool
    created_at: datetime
    updated_at: datetime
