from typing import Protocol

from app.rules_engine.rules import StructuralReport
from app.schemas.diagnostic import DiagnosticReport


class SemanticReportLike(Protocol):
    score: int
    missing_keywords: list[str]
    recommendations: list[str]


def build_diagnostic_report(
    structural: StructuralReport, semantic: SemanticReportLike
) -> DiagnosticReport:
    overall_score = round((structural.score + semantic.score) / 2)
    return DiagnosticReport(
        overall_score=overall_score,
        structural_score=structural.score,
        structural_issues=structural.issues,
        semantic_score=semantic.score,
        missing_keywords=semantic.missing_keywords,
        recommendations=semantic.recommendations,
    )
