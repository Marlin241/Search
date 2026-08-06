from fpdf import FPDF

from app.personalization.schemas import CoverLetter, RewrittenCv


def render_cv_pdf(cv: RewrittenCv) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, "CV")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, cv.summary)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, "Expérience")
    pdf.ln(2)
    for entry in cv.experience:
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 6, f"{entry.title} - {entry.company} ({entry.dates})")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 11)
        for bullet in entry.bullets:
            pdf.multi_cell(0, 6, f"- {bullet}")
            pdf.ln(1)
        pdf.ln(2)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, "Formation")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    for item in cv.education:
        pdf.multi_cell(0, 6, item)
        pdf.ln(1)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, "Compétences")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, ", ".join(cv.skills))

    return bytes(pdf.output())


def render_cover_letter_pdf(letter: CoverLetter) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 11)

    pdf.multi_cell(0, 6, letter.greeting)
    pdf.ln(4)
    for paragraph in letter.body_paragraphs:
        pdf.multi_cell(0, 6, paragraph)
        pdf.ln(3)
    pdf.ln(2)
    pdf.multi_cell(0, 6, letter.closing)

    return bytes(pdf.output())
