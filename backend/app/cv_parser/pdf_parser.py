import io

import pdfplumber

from app.cv_parser.models import CVParseResult
from app.cv_parser.sections import detect_sections

_TABLE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}


def _detect_multi_column(page: "pdfplumber.page.Page") -> bool:
    words = page.extract_words()
    if len(words) < 20:
        return False
    band_start = page.width * 0.45
    band_end = page.width * 0.55
    words_in_band = [w for w in words if band_start <= w["x0"] and w["x1"] <= band_end]
    words_left = [w for w in words if w["x0"] < band_start]
    words_right = [w for w in words if w["x0"] > band_end]
    if not words_left or not words_right:
        return False
    return (len(words_in_band) / len(words)) < 0.02


def parse_pdf(file_bytes: bytes) -> CVParseResult:
    text_parts: list[str] = []
    has_tables = False
    has_images = False
    has_multi_column = False

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
            if page.find_tables(table_settings=_TABLE_SETTINGS):
                has_tables = True
            if page.images:
                has_images = True
            if _detect_multi_column(page):
                has_multi_column = True

    text = "\n".join(text_parts)
    return CVParseResult(
        text=text,
        has_tables=has_tables,
        has_multi_column=has_multi_column,
        has_images=has_images,
        detected_sections=detect_sections(text),
    )
