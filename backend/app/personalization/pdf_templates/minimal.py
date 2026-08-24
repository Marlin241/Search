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
    """Monochrome, tight spacing - no accent color, smaller header than
    classic/modern."""
    pdf = new_pdf(style)
    lh = style.line_height

    if profile is not None and profile.full_name:
        pdf.set_font("DejaVu", "B", 13)
        pdf.multi_cell(0, 7, profile.full_name)
        pdf.ln(1)
        contact_parts = [
            part
            for part in (profile.phone, profile.address, profile.linkedin_url)
            if part
        ]
        if contact_parts:
            pdf.set_font("DejaVu", "", 8)
            pdf.multi_cell(0, 4, " · ".join(contact_parts))
            pdf.ln(1)
        pdf.ln(1)
    else:
        render_header(pdf, profile)

    def section_header(text: str) -> None:
        pdf.set_font("DejaVu", "B", 10.5)
        pdf.multi_cell(0, lh, text.upper())
        pdf.ln(1)

    pdf.set_font("DejaVu", "", 10)
    pdf.multi_cell(0, lh, rewritten.summary)
    pdf.ln(2)

    section_header("Expérience")
    for entry in rewritten.experience:
        pdf.set_font("DejaVu", "B", 10)
        pdf.multi_cell(0, lh, f"{entry.title} - {entry.company} ({entry.dates})")
        pdf.ln(1)
        pdf.set_font("DejaVu", "", 10)
        for bullet in entry.bullets:
            pdf.multi_cell(0, lh, f"- {bullet}")
            pdf.ln(1)
    pdf.ln(1)

    section_header("Formation")
    pdf.set_font("DejaVu", "", 10)
    for item in rewritten.education:
        pdf.multi_cell(0, lh, item)
        pdf.ln(1)
    pdf.ln(1)

    section_header("Compétences")
    pdf.set_font("DejaVu", "", 10)
    pdf.multi_cell(0, lh, ", ".join(rewritten.skills))

    return bytes(pdf.output()), pdf.pages_count
