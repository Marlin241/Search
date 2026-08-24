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
    """Visually distinct from classic: larger name block, accent-colored
    rule under each section header instead of colored text."""
    pdf = new_pdf(style)
    lh = style.line_height

    if profile is not None and profile.full_name:
        pdf.set_font("DejaVu", "B", 22)
        pdf.multi_cell(0, 11, profile.full_name)
        pdf.ln(1)
        contact_parts = [
            part
            for part in (profile.phone, profile.address, profile.linkedin_url)
            if part
        ]
        if contact_parts:
            pdf.set_font("DejaVu", "", 9)
            pdf.set_text_color("#555555")
            pdf.multi_cell(0, 5, " · ".join(contact_parts))
            pdf.set_text_color("#000000")
            pdf.ln(1)
        pdf.ln(3)
    else:
        render_header(pdf, profile)

    def section_header(text: str) -> None:
        pdf.set_font("DejaVu", "B", 12)
        pdf.multi_cell(0, lh, text.upper())
        y = pdf.get_y()
        pdf.set_draw_color(style.accent_color)
        pdf.set_line_width(0.8)
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.ln(3)

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
