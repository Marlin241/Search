import io

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image

from app.cv_parser.docx_parser import parse_docx


def _save(document: Document) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_parses_simple_docx_and_detects_sections():
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    document.add_paragraph("Développeur chez Acme, 2020-2024")
    document.add_paragraph("Formation")
    document.add_paragraph("Master informatique")
    document.add_paragraph("Compétences")
    document.add_paragraph("Python, FastAPI")

    result = parse_docx(_save(document))

    assert "Développeur chez Acme" in result.text
    assert result.detected_sections == {"experience", "education", "skills"}
    assert result.has_tables is False
    assert result.has_images is False
    assert result.has_multi_column is False


def test_detects_table():
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    document.add_table(rows=2, cols=2)

    result = parse_docx(_save(document))
    assert result.has_tables is True


def test_detects_image():
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    img_buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="black").save(img_buffer, format="PNG")
    img_buffer.seek(0)
    document.add_picture(img_buffer)

    result = parse_docx(_save(document))
    assert result.has_images is True


def test_detects_multi_column_section():
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    section = document.sections[0]
    cols = OxmlElement("w:cols")
    cols.set(qn("w:num"), "2")
    section._sectPr.append(cols)

    result = parse_docx(_save(document))
    assert result.has_multi_column is True
