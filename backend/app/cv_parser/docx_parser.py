import io

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn

from app.cv_parser.models import CVParseResult
from app.cv_parser.sections import detect_sections


def _has_multi_column(document: DocxDocument) -> bool:
    for section in document.sections:
        for cols in section._sectPr.findall(qn("w:cols")):
            num = cols.get(qn("w:num"))
            if num is not None and int(num) > 1:
                return True
    return False


def parse_docx(file_bytes: bytes) -> CVParseResult:
    document = Document(io.BytesIO(file_bytes))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    return CVParseResult(
        text=text,
        has_tables=len(document.tables) > 0,
        has_multi_column=_has_multi_column(document),
        has_images=len(document.inline_shapes) > 0,
        detected_sections=detect_sections(text),
    )
