import io

import pytest
from docx import Document
from fpdf import FPDF

from app.cv_parser.parser import MAX_CV_SIZE_BYTES, CVParsingError, parse_cv


def _docx_bytes(paragraph_text: str) -> bytes:
    document = Document()
    document.add_paragraph(paragraph_text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_parses_valid_docx_by_extension():
    result = parse_cv(
        _docx_bytes(
            "Expérience professionnelle chez Acme. Travaux importants en 2023 et 2024."
        ),
        "cv.docx",
    )
    assert "Acme" in result.text


def test_parses_valid_pdf_by_extension():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Expérience professionnelle chez Acme " * 5)
    result = parse_cv(bytes(pdf.output()), "cv.pdf")
    assert "Acme" in result.text


def test_rejects_unsupported_extension():
    with pytest.raises(CVParsingError):
        parse_cv(b"whatever", "cv.txt")


def test_rejects_file_too_large():
    oversized = b"0" * (MAX_CV_SIZE_BYTES + 1)
    with pytest.raises(CVParsingError):
        parse_cv(oversized, "cv.pdf")


def test_rejects_corrupt_pdf():
    with pytest.raises(CVParsingError):
        parse_cv(b"not a real pdf", "cv.pdf")


def test_rejects_scanned_cv_with_no_text():
    pdf = FPDF()
    pdf.add_page()
    with pytest.raises(CVParsingError):
        parse_cv(bytes(pdf.output()), "cv.pdf")
