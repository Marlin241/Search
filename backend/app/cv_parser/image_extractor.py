import io
import logging
from dataclasses import dataclass

import pymupdf
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)

# Caps mirror the defensive posture used elsewhere for user uploads (e.g.
# MAX_CV_SIZE_BYTES in parser.py, MAX_RESPONSE_BYTES in offer_ingestion): a
# CV embeds at most a handful of real photos, so a hard cap avoids a
# pathological file (or a hostile one) forcing us to decode hundreds of
# images. Small images are skipped - they're almost always logos, icons, or
# decorative dividers, never a usable profile photo candidate.
MAX_EXTRACTED_IMAGES = 5
MIN_IMAGE_BYTES = 3_000
MIN_IMAGE_DIMENSION_PX = 80

_EXT_TO_CONTENT_TYPE = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "bmp": "image/bmp",
    "gif": "image/gif",
    "tiff": "image/tiff",
    "webp": "image/webp",
}


@dataclass
class ExtractedImage:
    content: bytes
    content_type: str


class ImageExtractionError(Exception):
    pass


def extract_embedded_images(file_bytes: bytes, filename: str) -> list[ExtractedImage]:
    """Best-effort extraction of embedded raster images from an uploaded CV,
    used to offer real photos found in the file as profile-picture
    candidates during onboarding. This is independent of the main text
    parsing pipeline (app.cv_parser.parser) - a CV that fails image
    extraction should still parse for text normally, so failures here are
    swallowed into an empty list rather than raised, except for a clearly
    unsupported file type."""
    lowered_name = filename.lower()
    if lowered_name.endswith(".pdf"):
        return _extract_from_pdf(file_bytes)
    if lowered_name.endswith(".docx"):
        return _extract_from_docx(file_bytes)
    raise ImageExtractionError(
        "Format de fichier non supporté. Utilisez un PDF ou un DOCX."
    )


def _extract_from_pdf(file_bytes: bytes) -> list[ExtractedImage]:
    images: list[ExtractedImage] = []
    try:
        with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                for image_info in page.get_images(full=True):
                    if len(images) >= MAX_EXTRACTED_IMAGES:
                        return images
                    xref = image_info[0]
                    try:
                        extracted = doc.extract_image(xref)
                    except Exception:
                        # Best-effort: one malformed embedded image (bad
                        # stream/filter) must not abort extraction of the
                        # others.
                        logger.exception(
                            "Échec d'extraction de l'image xref=%s du CV", xref
                        )
                        continue
                    image_bytes = extracted.get("image")
                    if not image_bytes or len(image_bytes) < MIN_IMAGE_BYTES:
                        continue
                    width = extracted.get("width", 0)
                    height = extracted.get("height", 0)
                    if (
                        width < MIN_IMAGE_DIMENSION_PX
                        or height < MIN_IMAGE_DIMENSION_PX
                    ):
                        continue
                    content_type = _EXT_TO_CONTENT_TYPE.get(
                        (extracted.get("ext") or "").lower(), "image/jpeg"
                    )
                    images.append(ExtractedImage(image_bytes, content_type))
    except Exception:
        # Best-effort: a PDF that PyMuPDF can't open at all (corrupt,
        # unsupported encryption) yields no photo candidates rather than
        # failing the onboarding step - the text parsing pipeline
        # (app.cv_parser.parser) is the one that must succeed, not this.
        logger.exception("Échec d'extraction des images du CV (PDF)")
        return []
    return images


def _extract_from_docx(file_bytes: bytes) -> list[ExtractedImage]:
    images: list[ExtractedImage] = []
    try:
        document = DocxDocument(io.BytesIO(file_bytes))
        for rel in document.part.rels.values():
            if "image" not in rel.reltype:
                continue
            if len(images) >= MAX_EXTRACTED_IMAGES:
                break
            try:
                image_bytes = rel.target_part.blob
                content_type = rel.target_part.content_type or "image/jpeg"
            except Exception:
                logger.exception("Échec d'extraction d'une image intégrée du CV (DOCX)")
                continue
            if len(image_bytes) < MIN_IMAGE_BYTES:
                continue
            images.append(ExtractedImage(image_bytes, content_type))
    except Exception:
        # Best-effort: a DOCX python-docx can't open at all (corrupt zip,
        # unexpected structure) yields no photo candidates rather than
        # failing the onboarding step.
        logger.exception("Échec d'extraction des images du CV (DOCX)")
        return []
    return images
