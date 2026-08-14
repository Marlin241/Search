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

    pdf_bytes, page_count = render_cv_pdf(cv)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
    assert page_count == 1


def test_render_cover_letter_pdf_returns_nonempty_pdf_bytes():
    letter = CoverLetter(
        greeting="Madame, Monsieur,",
        body_paragraphs=[
            "Je vous écris pour candidater au poste de développeuse.",
            "Mon expérience chez TechCorp Solutions correspond à vos besoins.",
        ],
        closing_formula="Cordialement,",
        signature="Jane Doe",
    )

    pdf_bytes = render_cover_letter_pdf(letter)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 200


def test_render_cv_pdf_handles_typographic_characters_claude_commonly_emits():
    # fpdf2's core Helvetica font is latin-1 only and raises
    # FPDFUnicodeEncodingException on these - regression test for the
    # crash this project's PDFs must never hit in production.
    cv = RewrittenCv(
        summary="A dirigé le cœur d'une équipe — 5 ans d'expérience…",
        experience=[
            CvExperienceEntry(
                title="Chef d'équipe",
                company="Société Générale d'Œuvres",
                dates="2020-2022",
                bullets=["A géré un budget de 50 000 €."],
            )
        ],
        education=["Master, l'Université Paris-Saclay"],
        skills=["Œuvre collective"],
    )

    pdf_bytes, _ = render_cv_pdf(cv)

    assert pdf_bytes.startswith(b"%PDF")


def test_render_cv_pdf_reports_page_count_above_one_when_content_overflows():
    cv = RewrittenCv(
        summary="Résumé optimisé pour cette offre. " * 20,
        experience=[
            CvExperienceEntry(
                title=f"Poste {i}",
                company="TechCorp Solutions",
                dates="2020-2022",
                bullets=[f"Réalisation notable numéro {i}. " * 10 for _ in range(6)],
            )
            for i in range(10)
        ],
        education=["Master Informatique, Université Paris-Saclay, 2019"],
        skills=["Python", "Docker", "PostgreSQL"],
    )

    _, page_count = render_cv_pdf(cv)

    assert page_count > 1


def test_render_cover_letter_pdf_handles_typographic_characters_claude_commonly_emits():
    letter = CoverLetter(
        greeting="Madame, Monsieur,",
        body_paragraphs=["Je suis passionné par le cœur de métier — c'est mon œuvre…"],
        closing_formula="Cordialement,",
        signature="Jane Doe",
    )

    pdf_bytes = render_cover_letter_pdf(letter)

    assert pdf_bytes.startswith(b"%PDF")
