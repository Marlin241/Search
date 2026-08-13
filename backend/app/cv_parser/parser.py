from app.cv_parser.docx_parser import parse_docx
from app.cv_parser.models import CVParseResult
from app.cv_parser.pdf_parser import parse_pdf

MAX_CV_SIZE_BYTES = 5 * 1024 * 1024


class CVParsingError(Exception):
    pass


def parse_cv(file_bytes: bytes, filename: str) -> CVParseResult:
    if len(file_bytes) > MAX_CV_SIZE_BYTES:
        raise CVParsingError("Le fichier dépasse la taille maximale autorisée (5 Mo).")

    lowered_name = filename.lower()
    try:
        if lowered_name.endswith(".pdf"):
            result = parse_pdf(file_bytes)
        elif lowered_name.endswith(".docx"):
            result = parse_docx(file_bytes)
        else:
            raise CVParsingError(
                "Format de fichier non supporté. Utilisez un PDF ou un DOCX."
            )
    except CVParsingError:
        raise
    except Exception as exc:
        raise CVParsingError(f"Impossible de lire ce fichier : {exc}") from exc

    if len(result.text.strip()) < 50:
        raise CVParsingError(
            "Ce CV semble être une image scannée ou ne contient pas de texte extractible. "
            "L'analyse automatique n'est pas encore possible sur ce format."
        )
    return result
