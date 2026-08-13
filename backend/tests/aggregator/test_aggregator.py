from pydantic import BaseModel

from app.aggregator.aggregator import build_diagnostic_report
from app.rules_engine.rules import StructuralReport


class FakeSemanticReport(BaseModel):
    score: int
    missing_keywords: list[str]
    recommendations: list[str]


def test_aggregates_scores_and_details():
    structural = StructuralReport(score=80, issues=["Missing skills section"])
    semantic = FakeSemanticReport(
        score=60, missing_keywords=["Docker"], recommendations=["Add Docker"]
    )

    report = build_diagnostic_report(structural, semantic)

    assert report.overall_score == 70
    assert report.structural_score == 80
    assert report.structural_issues == ["Missing skills section"]
    assert report.semantic_score == 60
    assert report.missing_keywords == ["Docker"]
    assert report.recommendations == ["Add Docker"]


def test_overall_score_rounds_to_nearest_int():
    structural = StructuralReport(score=100, issues=[])
    semantic = FakeSemanticReport(score=83, missing_keywords=[], recommendations=[])

    report = build_diagnostic_report(structural, semantic)
    # Python's round() uses round-half-to-even: (100 + 83) / 2 == 91.5 -> 92
    assert report.overall_score == 92
