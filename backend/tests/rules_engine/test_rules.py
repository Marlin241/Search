from app.cv_parser.models import CVParseResult
from app.rules_engine.rules import evaluate_structure


def _clean_cv() -> CVParseResult:
    return CVParseResult(
        text="...",
        has_tables=False,
        has_multi_column=False,
        has_images=False,
        detected_sections={"experience", "education", "skills"},
    )


def test_clean_cv_scores_100_with_no_issues():
    report = evaluate_structure(_clean_cv())
    assert report.score == 100
    assert report.issues == []


def test_multi_column_lowers_score_and_adds_issue():
    cv = _clean_cv().model_copy(update={"has_multi_column": True})
    report = evaluate_structure(cv)
    assert report.score == 75
    assert any("colonnes" in issue for issue in report.issues)


def test_missing_sections_lower_score_and_add_issues():
    cv = _clean_cv().model_copy(update={"detected_sections": set()})
    report = evaluate_structure(cv)
    assert report.score == 70
    assert len(report.issues) == 3


def test_score_never_goes_below_zero():
    cv = CVParseResult(
        text="...",
        has_tables=True,
        has_multi_column=True,
        has_images=True,
        detected_sections=set(),
    )
    report = evaluate_structure(cv)
    assert report.score == 0
