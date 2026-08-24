from pathlib import Path

from fpdf import FPDF

from app.personalization.schemas import CoverLetter

# CV rendering moved to app.personalization.pdf_templates (Phase 4: multiple
# templates + style options). This module now only renders the cover
# letter, which Phase 5 will overhaul the same way - untouched for now.
_FONTS_DIR = Path(__file__).parent / "fonts"


def _new_pdf() -> FPDF:
    pdf = FPDF(format="A4")
    pdf.add_font("DejaVu", "", str(_FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    return pdf


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
