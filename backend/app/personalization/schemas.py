import re

from pydantic import BaseModel, field_validator


class CvExperienceEntry(BaseModel):
    title: str
    company: str
    dates: str
    bullets: list[str]


class HonestyAssessment(BaseModel):
    fit_summary: str = ""
    concerns: list[str] = []
    strengths: list[str] = []


class KeywordOmission(BaseModel):
    keyword: str
    reason: str


class ChangelogEntry(BaseModel):
    section: str
    change: str
    reason: str


class RewrittenCv(BaseModel):
    summary: str
    experience: list[CvExperienceEntry]
    education: list[str]
    skills: list[str]
    # Below: "Talya's eye" transparency fields. These are genuine tool_use
    # output the model fills in directly, not computed post-hoc by diffing
    # original vs. rewritten - a post-hoc diff can't tell you *why* a
    # keyword was left out, only that it was, which defeats the point of
    # the anti-hallucination guardrail this is meant to support. Defaults
    # are kept for existing callers (fakes in tests, older code paths) that
    # construct a RewrittenCv without these fields; the real API call
    # always supplies them because they're `required` in _CV_REWRITE_TOOL.
    honesty_assessment: HonestyAssessment = HonestyAssessment()
    keywords_added: list[str] = []
    keywords_already_present: list[str] = []
    keywords_deliberately_omitted: list[KeywordOmission] = []
    changelog: list[ChangelogEntry] = []


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
