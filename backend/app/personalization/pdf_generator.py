from pathlib import Path

from fpdf import FPDF

from app.personalization.schemas import CoverLetter, RewrittenCv

_FONTS_DIR = Path(__file__).parent / "fonts"


def _new_pdf() -> FPDF:
    # fpdf2's core fonts (Helvetica, ...) only support latin-1 and raise
    # FPDFUnicodeEncodingException on characters Claude routinely emits in
    # French prose (curly apostrophes, "œ", em dashes, ellipses, "€"). A
    # vendored Unicode TTF avoids that class of crash regardless of what the
    # LLM writes.
    pdf = FPDF(format="A4")
    pdf.add_font("DejaVu", "", str(_FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    return pdf


def render_cv_pdf(cv: RewrittenCv) -> bytes:
    pdf = _new_pdf()

    pdf.set_font("DejaVu", "B", 14)
    pdf.multi_cell(0, 8, "CV")
    pdf.ln(2)

    pdf.set_font("DejaVu", "", 11)
    pdf.multi_cell(0, 6, cv.summary)
    pdf.ln(4)

    pdf.set_font("DejaVu", "B", 12)
    pdf.multi_cell(0, 7, "Expérience")
    pdf.ln(2)
    for entry in cv.experience:
        pdf.set_font("DejaVu", "B", 11)
        pdf.multi_cell(0, 6, f"{entry.title} - {entry.company} ({entry.dates})")
        pdf.ln(1)
        pdf.set_font("DejaVu", "", 11)
        for bullet in entry.bullets:
            pdf.multi_cell(0, 6, f"- {bullet}")
            pdf.ln(1)
        pdf.ln(2)
    pdf.ln(2)

    pdf.set_font("DejaVu", "B", 12)
    pdf.multi_cell(0, 7, "Formation")
    pdf.ln(2)
    pdf.set_font("DejaVu", "", 11)
    for item in cv.education:
        pdf.multi_cell(0, 6, item)
        pdf.ln(1)
    pdf.ln(4)

    pdf.set_font("DejaVu", "B", 12)
    pdf.multi_cell(0, 7, "Compétences")
    pdf.ln(2)
    pdf.set_font("DejaVu", "", 11)
    pdf.multi_cell(0, 6, ", ".join(cv.skills))

    return bytes(pdf.output())


def render_cover_letter_pdf(letter: CoverLetter) -> bytes:
    pdf = _new_pdf()
    pdf.set_font("DejaVu", "", 11)

    pdf.multi_cell(0, 6, letter.greeting)
    pdf.ln(4)
    for paragraph in letter.body_paragraphs:
        pdf.multi_cell(0, 6, paragraph)
        pdf.ln(3)
    pdf.ln(2)
    pdf.multi_cell(0, 6, letter.closing_formula)
    pdf.ln(4)
    pdf.multi_cell(0, 6, letter.signature)

    return bytes(pdf.output())
