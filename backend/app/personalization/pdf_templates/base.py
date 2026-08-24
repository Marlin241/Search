from pathlib import Path
from typing import Literal

from fpdf import FPDF
from pydantic import BaseModel

from app.models.candidate_profile import CandidateProfile

_FONTS_DIR = Path(__file__).parent.parent / "fonts"

_SPACING_LINE_HEIGHTS = {"compact": 5, "normal": 6, "relaxed": 7.5}


class CvStyleOptions(BaseModel):
    # Only one vendored font today - kept as a field for forward-compat
    # rather than hardcoding "dejavu" everywhere a style is threaded through.
    font: Literal["dejavu"] = "dejavu"
    accent_color: str = "#2563eb"
    margins: int = 15
    spacing: Literal["compact", "normal", "relaxed"] = "normal"

    @property
    def line_height(self) -> float:
        return _SPACING_LINE_HEIGHTS[self.spacing]


def new_pdf(style: CvStyleOptions) -> FPDF:
    # fpdf2's core fonts (Helvetica, ...) only support latin-1 and raise
    # FPDFUnicodeEncodingException on characters Claude routinely emits in
    # French prose (curly apostrophes, "œ", em dashes, ellipses, "€"). A
    # vendored Unicode TTF avoids that class of crash regardless of what the
    # LLM writes.
    pdf = FPDF(format="A4")
    pdf.add_font("DejaVu", "", str(_FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_margins(style.margins, style.margins)
    pdf.set_auto_page_break(auto=True, margin=style.margins)
    pdf.add_page()
    return pdf


def render_header(pdf: FPDF, profile: CandidateProfile | None) -> None:
    """Candidate name/contact block. The original single-template renderer
    had none at all - added here since it's shared across all templates."""
    if profile is None or not profile.full_name:
        return
    pdf.set_font("DejaVu", "B", 16)
    pdf.multi_cell(0, 8, profile.full_name)
    pdf.ln(1)
    contact_parts = [
        part for part in (profile.phone, profile.address, profile.linkedin_url) if part
    ]
    if contact_parts:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color("#555555")
        pdf.multi_cell(0, 5, " · ".join(contact_parts))
        pdf.set_text_color("#000000")
        pdf.ln(1)
    pdf.ln(2)
