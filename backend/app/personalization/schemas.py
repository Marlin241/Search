import re

from pydantic import BaseModel, field_validator


class CvExperienceEntry(BaseModel):
    title: str
    company: str
    dates: str
    bullets: list[str]


class RewrittenCv(BaseModel):
    summary: str
    experience: list[CvExperienceEntry]
    education: list[str]
    skills: list[str]


def _clean_llm_text(value: str) -> str:
    # Claude occasionally emits a literal two-character "\n" escape sequence
    # as visible text (instead of an actual line break), most often right
    # before the closing formula - e.g. "...ma candidature.\n\nCordialement,".
    # PDF rendering already handles real paragraph breaks via separate
    # fields/pdf.ln() calls, so any such sequence is always spurious.
    without_literal_escapes = value.replace("\\n", " ")
    return re.sub(r"\s+", " ", without_literal_escapes).strip()


class CoverLetter(BaseModel):
    greeting: str
    body_paragraphs: list[str]
    closing_formula: str
    signature: str

    @field_validator("greeting", "closing_formula", "signature")
    @classmethod
    def _sanitize_text_field(cls, value: str) -> str:
        return _clean_llm_text(value)

    @field_validator("body_paragraphs")
    @classmethod
    def _sanitize_body_paragraphs(cls, value: list[str]) -> list[str]:
        return [_clean_llm_text(item) for item in value]
