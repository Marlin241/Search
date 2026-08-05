from pydantic import BaseModel


class DiagnosticReport(BaseModel):
    overall_score: int
    structural_score: int
    structural_issues: list[str]
    semantic_score: int
    missing_keywords: list[str]
    recommendations: list[str]
