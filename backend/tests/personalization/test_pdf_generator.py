from app.personalization.pdf_generator import render_cover_letter_pdf, render_cv_pdf
from app.personalization.schemas import CoverLetter, CvExperienceEntry, RewrittenCv


def test_render_cv_pdf_returns_nonempty_pdf_bytes():
    cv = RewrittenCv(
        summary="Résumé optimisé pour cette offre.",
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

    pdf_bytes = render_cv_pdf(cv)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_render_cover_letter_pdf_returns_nonempty_pdf_bytes():
    letter = CoverLetter(
        greeting="Madame, Monsieur,",
        body_paragraphs=[
            "Je vous écris pour candidater au poste de développeuse.",
            "Mon expérience chez TechCorp Solutions correspond à vos besoins.",
        ],
        closing="Cordialement, Jane Doe",
    )

    pdf_bytes = render_cover_letter_pdf(letter)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 200
