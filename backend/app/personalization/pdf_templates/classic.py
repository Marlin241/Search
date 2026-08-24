from app.models.candidate_profile import CandidateProfile
from app.personalization.pdf_templates.base import (
    CvStyleOptions,
    new_pdf,
    render_header,
)
from app.personalization.schemas import RewrittenCv


def render(
    rewritten: RewrittenCv,
    profile: CandidateProfile | None,
    style: CvStyleOptions,
) -> tuple[bytes, int]:
    """Single-column layout with accent-colored section headers - this is
    the original (pre-Phase-4) CV layout, now parameterized by style."""
    pdf = new_pdf(style)
    lh = style.line_height

    render_header(pdf, profile)

    def section_header(text: str) -> None:
        pdf.set_font("DejaVu", "B", 12)
        pdf.set_text_color(style.accent_color)
        pdf.multi_cell(0, lh + 1, text)
        pdf.set_text_color("#000000")
        pdf.ln(2)

    pdf.set_font("DejaVu", "", 11)
    pdf.multi_cell(0, lh, rewritten.summary)
    pdf.ln(4)

    section_header("Expérience")
    for entry in rewritten.experience:
        pdf.set_font("DejaVu", "B", 11)
        pdf.multi_cell(0, lh, f"{entry.title} - {entry.company} ({entry.dates})")
        pdf.ln(1)
        pdf.set_font("DejaVu", "", 11)
        for bullet in entry.bullets:
            pdf.multi_cell(0, lh, f"- {bullet}")
            pdf.ln(1)
        pdf.ln(2)
    pdf.ln(2)

    section_header("Formation")
    pdf.set_font("DejaVu", "", 11)
    for item in rewritten.education:
        pdf.multi_cell(0, lh, item)
        pdf.ln(1)
    pdf.ln(4)

    section_header("Compétences")
    pdf.set_font("DejaVu", "", 11)
    pdf.multi_cell(0, lh, ", ".join(rewritten.skills))

    return bytes(pdf.output()), pdf.pages_count
