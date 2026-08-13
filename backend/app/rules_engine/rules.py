from pydantic import BaseModel

from app.cv_parser.models import CVParseResult


class StructuralReport(BaseModel):
    score: int
    issues: list[str]


_REQUIRED_SECTIONS = {
    "experience": "Aucune section 'Expérience' standard détectée.",
    "education": "Aucune section 'Formation' standard détectée.",
    "skills": "Aucune section 'Compétences' standard détectée.",
}


def evaluate_structure(parse_result: CVParseResult) -> StructuralReport:
    issues: list[str] = []
    penalty = 0

    if parse_result.has_multi_column:
        issues.append(
            "Ce CV utilise une mise en page en colonnes, souvent mal lue par les ATS."
        )
        penalty += 25
    if parse_result.has_tables:
        issues.append(
            "Ce CV contient des tableaux, qui peuvent être mal interprétés par les ATS."
        )
        penalty += 20
    if parse_result.has_images:
        issues.append(
            "Ce CV contient des images ; tout texte qu'elles contiennent ne sera pas lu par l'ATS."
        )
        penalty += 15

    for section, message in _REQUIRED_SECTIONS.items():
        if section not in parse_result.detected_sections:
            issues.append(message)
            penalty += 10

    return StructuralReport(score=max(0, 100 - penalty), issues=issues)
