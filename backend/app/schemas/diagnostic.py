from datetime import datetime

from pydantic import BaseModel

from app.schemas.personalization import PersonalizedDocumentOut


class DiagnosticReport(BaseModel):
    id: int | None = None
    created_at: datetime | None = None
    overall_score: int
    structural_score: int
    structural_issues: list[str]
    semantic_score: int
    missing_keywords: list[str]
    recommendations: list[str]
    documents: list[PersonalizedDocumentOut] = []
