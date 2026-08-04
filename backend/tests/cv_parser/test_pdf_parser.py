from fpdf import FPDF
from PIL import Image

from app.cv_parser.pdf_parser import parse_pdf


def _output(pdf: FPDF) -> bytes:
    return bytes(pdf.output())


def test_extracts_text_and_sections():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Expérience professionnelle\nDéveloppeur chez Acme\nFormation\nMaster\nCompétences\nPython")

    result = parse_pdf(_output(pdf))
    assert "Développeur chez Acme" in result.text
    assert result.detected_sections == {"experience", "education", "skills"}
    assert result.has_multi_column is False


def test_detects_table():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    x0, y0, col_w, row_h = 10, 10, 40, 10
    for row in range(3):
        for col in range(2):
            pdf.rect(x0 + col * col_w, y0 + row * row_h, col_w, row_h)

    result = parse_pdf(_output(pdf))
    assert result.has_tables is True


def test_detects_image():
    pdf = FPDF()
    pdf.add_page()
    img = Image.new("RGB", (10, 10), color="black")
    pdf.image(img, x=10, y=10, w=10, h=10)

    result = parse_pdf(_output(pdf))
    assert result.has_images is True


def test_detects_two_column_layout():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    pdf.set_xy(10, 10)
    pdf.multi_cell(90, 6, "Colonne gauche avec du texte. " * 40)
    pdf.set_xy(110, 10)
    pdf.multi_cell(90, 6, "Colonne droite avec du texte. " * 40)

    result = parse_pdf(_output(pdf))
    assert result.has_multi_column is True
