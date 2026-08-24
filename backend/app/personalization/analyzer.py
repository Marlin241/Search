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
            "honesty_assessment": {
                "type": "object",
                "description": "Your candid, unvarnished assessment of how well this "
                "candidate actually fits the offer - not a sales pitch.",
                "properties": {
                    "fit_summary": {
                        "type": "string",
                        "description": "One or two honest sentences on overall fit, "
                        "including real gaps if there are any.",
                    },
                    "concerns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Genuine gaps or mismatches between the candidate "
                        "and the offer. Empty list only if there truly are none.",
                    },
                    "strengths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The candidate's strongest, most genuine points "
                        "of alignment with the offer.",
                    },
                },
                "required": ["fit_summary", "concerns", "strengths"],
            },
            "keywords_added": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Offer keywords this rewrite newly incorporated, because "
                "the candidate genuinely has that experience/skill.",
            },
            "keywords_already_present": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Offer keywords that were already present in the "
                "original CV, unchanged by the rewrite.",
            },
            "keywords_deliberately_omitted": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string"},
                        "reason": {
                            "type": "string",
                            "description": "Why it was left out - e.g. the candidate "
                            "has no real experience with it. Never invent matching "
                            "experience just to add a keyword.",
                        },
                    },
                    "required": ["keyword", "reason"],
                },
                "description": "Keywords from the offer or the prior diagnostic's "
                "missing-keywords list that you deliberately did NOT add, because doing "
                "so would misrepresent the candidate. It is expected and good practice "
                "to list entries here rather than fabricate matching experience - an "
                "empty list should only happen when every relevant keyword genuinely "
                "applies.",
            },
            "changelog": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {"type": "string"},
                        "change": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["section", "change", "reason"],
                },
                "description": "A human-readable summary of what changed vs. the "
                "original CV, section by section, and why.",
            },
        },
        "required": [
            "summary",
            "experience",
            "education",
            "skills",
            "honesty_assessment",
            "keywords_added",
            "keywords_already_present",
            "keywords_deliberately_omitted",
            "changelog",
        ],
    },
}

_TARGET_LANGUAGE_NAMES = {
    "fr": "French",
    "en": "English",
    "es": "Spanish",
    "de": "German",
}

_LENGTH_INSTRUCTIONS = (
    "The rewritten CV must fit on a single A4 page when rendered. To achieve "
    "this: keep the summary to 2-3 sentences; keep each experience entry to "
    "at most 3-4 short bullets; if the original CV has more than 4 "
    "experience entries, keep only the ones most relevant to the offer "
    "(you may omit older or less relevant ones) rather than shortening all "
    "of them equally; keep the skills list focused rather than exhaustive. "
    "Prioritize relevance to the offer over completeness."
)

_SHRINK_FURTHER_INSTRUCTIONS = (
    "A previous attempt at this rewrite still did not fit on a single A4 "
    "page. Cut further: reduce the summary to a single sentence, keep at "
    "most 2-3 bullets per experience entry, keep only the 2-3 most "
    "relevant experience entries, and trim the skills list to the terms "
    "most relevant to the offer."
)

_COVER_LETTER_TOOL = {
    "name": "submit_cover_letter",
    "description": "Submit the generated cover letter for the target job offer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "greeting": {
                "type": "string",
                "description": "Opening line, e.g. 'Madame, Monsieur,'.",
            },
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
                # anthropic>=1.0 dropped `temperature` from
                # messages.create() entirely - determinism for this
                # structured extraction/rewriting task now comes from
                # thinking being disabled and the forced tool_choice below,
                # not from sampling temperature.
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{"role": "user", "content": prompt}],
            )
            tool_use = next(
                (block for block in response.content if block.type == "tool_use"), None
            )
            if tool_use is None:
                raise PersonalizationError("No tool_use block in Claude response")
            return schema_cls.model_validate(tool_use.input)
        except (ValidationError, PersonalizationError, anthropic.APIError) as exc:
            last_error = exc
            continue
    raise PersonalizationError(
        f"Personalization call failed after retries: {last_error}"
    )


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
        stricter_length: bool = False,
        template: str = "classic",
        target_language: str = "fr",
    ) -> RewrittenCv:
        # `template` only affects PDF rendering (see app.personalization.pdf_templates)
        # - it never reaches the prompt, the LLM has no notion of visual layout.
        length_instructions = _LENGTH_INSTRUCTIONS
        if stricter_length:
            length_instructions = (
                f"{_LENGTH_INSTRUCTIONS}\n\n{_SHRINK_FURTHER_INSTRUCTIONS}"
            )
        language_name = _TARGET_LANGUAGE_NAMES.get(target_language, target_language)
        prompt = (
            f"{_ANTI_HALLUCINATION_INSTRUCTIONS}\n\n"
            "Rewrite this CV to better match the job offer. Write the "
            f"rewritten CV in {language_name}, regardless of the language "
            "the original CV or offer are written in.\n\n"
            f"{length_instructions}\n\n"
            "You must also honestly assess the candidate's real fit for "
            "this offer (honesty_assessment), and account for every "
            "relevant keyword: list ones you genuinely added "
            "(keywords_added), ones already present (keywords_already_present), "
            "and - just as important - ones you deliberately left out because "
            "adding them would misrepresent the candidate "
            "(keywords_deliberately_omitted, with the reason). Never invent "
            "matching experience to justify adding a keyword; it is expected "
            "and correct to leave real gaps in keywords_deliberately_omitted "
            "rather than fabricate them. Also summarize what changed and why "
            "(changelog).\n\n"
            f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}\n\n"
            f"Missing keywords identified by a prior diagnostic: {missing_keywords}\n"
            f"Recommendations from a prior diagnostic: {recommendations}"
        )
        return _submit_via_tool_use(
            self._client, self._model, 4096, _CV_REWRITE_TOOL, prompt, RewrittenCv
        )


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
        return _submit_via_tool_use(
            self._client, self._model, 2048, _COVER_LETTER_TOOL, prompt, CoverLetter
        )
