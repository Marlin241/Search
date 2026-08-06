import anthropic
from pydantic import BaseModel, ValidationError

from app.personalization.schemas import CoverLetter, RewrittenCv

PERSONALIZATION_MODEL = "claude-sonnet-5"

_MAX_ATTEMPTS = 2

_ANTI_HALLUCINATION_INSTRUCTIONS = (
    "Do not invent any experience, skill, employer, date, or qualification "
    "that is not already present in the original CV. Only reformulate, "
    "reorganize, and emphasize what is already there, using vocabulary from "
    "the job offer where genuinely applicable."
)

_CV_REWRITE_TOOL = {
    "name": "submit_rewritten_cv",
    "description": "Submit the CV rewritten and optimized for the target job offer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Short professional summary/hook at the top of the CV, tailored to the offer.",
            },
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "company": {"type": "string"},
                        "dates": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "company", "dates", "bullets"],
                },
                "description": "Work experience entries, reworded to highlight relevance to the offer.",
            },
            "education": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Education entries, unchanged in substance from the original CV.",
            },
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skills list, reordered/reworded to surface those matching the offer.",
            },
        },
        "required": ["summary", "experience", "education", "skills"],
    },
}

_COVER_LETTER_TOOL = {
    "name": "submit_cover_letter",
    "description": "Submit the generated cover letter for the target job offer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "greeting": {"type": "string", "description": "Opening line, e.g. 'Madame, Monsieur,'."},
            "body_paragraphs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Body paragraphs of the letter, in order.",
            },
            "closing_formula": {
                "type": "string",
                "description": "Closing formula only, e.g. 'Cordialement,'. Do not include the "
                "candidate's name here - use the separate signature field for that.",
            },
            "signature": {
                "type": "string",
                "description": "The candidate's name, used as the letter's signature line.",
            },
        },
        "required": ["greeting", "body_paragraphs", "closing_formula", "signature"],
    },
}


class PersonalizationError(Exception):
    pass


def _submit_via_tool_use(
    client,
    model: str,
    max_tokens: int,
    tool: dict,
    prompt: str,
    schema_cls: type[BaseModel],
):
    last_error: Exception | None = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                # claude-sonnet-5 runs adaptive thinking by default when
                # `thinking` is omitted, and max_tokens caps thinking +
                # response combined - which could silently truncate a
                # forced tool_use JSON payload on a long CV. This call is
                # deterministic structured extraction, not open-ended
                # reasoning, so thinking is disabled: max_tokens is then
                # dedicated entirely to the response.
                thinking={"type": "disabled"},
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{"role": "user", "content": prompt}],
            )
            tool_use = next((block for block in response.content if block.type == "tool_use"), None)
            if tool_use is None:
                raise PersonalizationError("No tool_use block in Claude response")
            return schema_cls.model_validate(tool_use.input)
        except (ValidationError, PersonalizationError, anthropic.APIError) as exc:
            last_error = exc
            continue
    raise PersonalizationError(f"Personalization call failed after retries: {last_error}")


class CvRewriter:
    def __init__(self, client, model: str = PERSONALIZATION_MODEL):
        self._client = client
        self._model = model

    def rewrite(
        self,
        cv_text: str,
        offer_text: str,
        missing_keywords: list[str],
        recommendations: list[str],
    ) -> RewrittenCv:
        prompt = (
            f"{_ANTI_HALLUCINATION_INSTRUCTIONS}\n\n"
            "Rewrite this CV to better match the job offer. The CV and offer "
            "may be in French or English; respond in the same language as "
            "the CV.\n\n"
            f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}\n\n"
            f"Missing keywords identified by a prior diagnostic: {missing_keywords}\n"
            f"Recommendations from a prior diagnostic: {recommendations}"
        )
        return _submit_via_tool_use(self._client, self._model, 4096, _CV_REWRITE_TOOL, prompt, RewrittenCv)


class CoverLetterGenerator:
    def __init__(self, client, model: str = PERSONALIZATION_MODEL):
        self._client = client
        self._model = model

    def generate(
        self,
        cv_text: str,
        offer_text: str,
        missing_keywords: list[str],
        recommendations: list[str],
    ) -> CoverLetter:
        prompt = (
            "Write a cover letter for this candidate applying to this job "
            "offer, based only on their CV - do not invent experience or "
            "skills not present in the CV. The CV and offer may be in "
            "French or English; respond in the same language as the CV.\n\n"
            f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}\n\n"
            f"Missing keywords identified by a prior diagnostic: {missing_keywords}\n"
            f"Recommendations from a prior diagnostic: {recommendations}"
        )
        return _submit_via_tool_use(self._client, self._model, 2048, _COVER_LETTER_TOOL, prompt, CoverLetter)
