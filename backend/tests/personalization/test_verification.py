from app.personalization.schemas import CvExperienceEntry, RewrittenCv
from app.personalization.verification import cv_needs_review

_ORIGINAL_CV_TEXT = (
    "Jane Doe\n"
    "Expérience professionnelle\n"
    "Développeuse Full Stack chez TechCorp Solutions, 2020-2022\n"
    "- A conçu des API REST\n"
    "Formation\n"
    "Master Informatique, Université Paris-Saclay, 2019\n"
    "Compétences\n"
    "Python, Docker, PostgreSQL"
)


def test_returns_false_when_rewritten_only_reformulates_existing_content():
    rewritten = RewrittenCv(
        summary="Développeuse Full Stack expérimentée, spécialisée dans les API REST.",
        experience=[
            CvExperienceEntry(
                title="Développeuse Full Stack",
                company="TechCorp Solutions",
                dates="2020-2022",
                bullets=["A conçu et déployé des API REST performantes."],
            )
        ],
        education=["Master Informatique, Université Paris-Saclay, 2019"],
        skills=["Python", "Docker", "PostgreSQL"],
    )

    assert cv_needs_review(_ORIGINAL_CV_TEXT, rewritten) is False


def test_returns_true_when_rewritten_introduces_an_unknown_employer():
    rewritten = RewrittenCv(
        summary="Développeuse Full Stack expérimentée.",
        experience=[
            CvExperienceEntry(
                title="Développeuse Full Stack",
                company="Global Innovations Group",
                dates="2020-2022",
                bullets=["A conçu des API REST."],
            )
        ],
        education=["Master Informatique, Université Paris-Saclay, 2019"],
        skills=["Python", "Docker", "PostgreSQL"],
    )

    assert cv_needs_review(_ORIGINAL_CV_TEXT, rewritten) is True


def test_returns_false_when_entry_has_multiple_bullets_with_known_terms():
    rewritten = RewrittenCv(
        summary="Développeuse Full Stack expérimentée.",
        experience=[
            CvExperienceEntry(
                title="Développeuse Full Stack",
                company="TechCorp Solutions",
                dates="2020-2022",
                bullets=[
                    "A conçu des API en Python.",
                    "Docker utilisé pour le déploiement continu.",
                ],
            )
        ],
        education=["Master Informatique, Université Paris-Saclay, 2019"],
        skills=["Python", "Docker", "PostgreSQL"],
    )

    assert cv_needs_review(_ORIGINAL_CV_TEXT, rewritten) is False


def test_returns_true_when_rewritten_introduces_an_unknown_date():
    rewritten = RewrittenCv(
        summary="Développeuse Full Stack expérimentée.",
        experience=[
            CvExperienceEntry(
                title="Développeuse Full Stack",
                company="TechCorp Solutions",
                dates="2018-2021",
                bullets=["A conçu des API REST."],
            )
        ],
        education=["Master Informatique, Université Paris-Saclay, 2019"],
        skills=["Python", "Docker", "PostgreSQL"],
    )

    assert cv_needs_review(_ORIGINAL_CV_TEXT, rewritten) is True
