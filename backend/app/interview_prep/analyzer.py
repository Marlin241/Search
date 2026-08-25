import logging

import anthropic
from pydantic import ValidationError

from app.interview_prep.schemas import InterviewPrepDossierContent

logger = logging.getLogger(__name__)

INTERVIEW_PREP_MODEL = "claude-sonnet-5"

_MAX_DOSSIER_ATTEMPTS = 2

_INTERVIEW_DOSSIER_TOOL = {
    "name": "submit_interview_dossier",
    "description": "Submit a structured interview-preparation dossier for this candidate/offer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "narrative_angle": {
                "type": "string",
                "description": "The core story the candidate should lead with in this "
                "interview - how their background connects to this specific offer.",
            },
            "company_facts": {
                "type": "object",
                "properties": {
                    "founding_year": {"type": ["integer", "null"]},
                    "headquarters": {"type": ["string", "null"]},
                    "sector": {"type": ["string", "null"]},
                    "revenue": {"type": ["string", "null"]},
                    "ceo": {"type": ["string", "null"]},
                    "confidence": {
                        "type": "string",
                        "enum": [
                            "verified_web_search",
                            "general_knowledge_unverified",
                        ],
                        "description": "'verified_web_search' only for facts genuinely "
                        "grounded in the research synthesis provided below; "
                        "'general_knowledge_unverified' otherwise - including whenever no "
                        "research synthesis was provided at all.",
                    },
                },
                "required": ["confidence"],
            },
            "recent_news": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "headline": {"type": "string"},
                        "summary": {"type": "string"},
                        "source_url": {"type": ["string", "null"]},
                    },
                    "required": ["headline", "summary"],
                },
                "description": "Only include entries genuinely drawn from the research "
                "synthesis below. Leave empty if no research was provided.",
            },
            "probable_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "targets_weak_point": {
                            "type": ["string", "null"],
                            "description": "The specific missing keyword or "
                            "recommendation from the candidate's diagnostic this "
                            "question probes, if any.",
                        },
                        "model_answer": {"type": "string"},
                    },
                    "required": ["question", "model_answer"],
                },
            },
            "practical_exercises": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "prompt": {"type": "string"},
                        "pitfalls_to_avoid": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["facile", "moyen", "difficile"],
                        },
                    },
                    "required": ["title", "prompt", "difficulty"],
                },
            },
            "coaching_checklist": {
                "type": "object",
                "properties": {
                    "before": {"type": "array", "items": {"type": "string"}},
                    "during": {"type": "array", "items": {"type": "string"}},
                    "after": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["before", "during", "after"],
            },
        },
        "required": [
            "narrative_angle",
            "company_facts",
            "recent_news",
            "probable_questions",
            "practical_exercises",
            "coaching_checklist",
        ],
    },
}


class InterviewPrepError(Exception):
    pass


class InterviewPrepAnalyzer:
    def __init__(self, client, model: str = INTERVIEW_PREP_MODEL):
        self._client = client
        self._model = model

    def research_company(
        self, company_name: str, job_title: str
    ) -> tuple[str, list[dict]]:
        """Phase A: an open-ended web-search turn. Returns (synthesis_text,
        sources) - sources is a list of {"title": ..., "url": ...} drawn
        from web_search_tool_result blocks.

        A single attempt, no retry loop: unlike Phase B this isn't
        structured extraction, so a transient failure just means "no
        research this time" (the caller falls back to unverified company
        facts), not a broken pipeline.
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                # Genuinely open-ended tool use (the model decides whether/how
                # much to search), unlike every other call in this codebase -
                # thinking stays adaptive rather than disabled, and
                # tool_choice is left at its default (auto).
                thinking={"type": "adaptive"},
                tools=[{"type": "web_search_20260209", "name": "web_search"}],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Search the web for recent, relevant information about "
                            f"the company '{company_name}' for a candidate preparing "
                            f"for a job interview for a '{job_title}' role there. "
                            "Focus on: what the company does, its size/sector, "
                            "recent news (product launches, funding, leadership "
                            "changes, layoffs, notable events from the last 12 "
                            "months), and anything a candidate should know to sound "
                            "informed in an interview. Write a concise synthesis of "
                            "what you found."
                        ),
                    }
                ],
            )
        except anthropic.APIError as exc:
            logger.warning("Interview prep web search failed: %s", exc)
            return "", []

        # response.stop_reason can be "pause_turn" on a long open-ended
        # web-search turn (the model may still be mid-search). Rather than
        # loop to resume the turn, this uses whatever was captured in this
        # single response as the synthesis - a real API characteristic for
        # long tool-use turns, not a bug to work around here.
        text_parts: list[str] = []
        sources: list[dict] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "web_search_tool_result":
                content = block.content
                # Success: a list of web_search_result items. Failure: a
                # single error object (e.g. {"error_code": ...}) - branch on
                # shape before indexing, never assume success.
                if isinstance(content, list):
                    for result in content:
                        url = getattr(result, "url", None)
                        title = getattr(result, "title", None)
                        if url:
                            sources.append({"title": title or url, "url": url})

        return "\n".join(text_parts).strip(), sources

    def draft_dossier(
        self,
        cv_text: str,
        offer_text: str,
        missing_keywords: list[str],
        recommendations: list[str],
        persona: str,
        extra_context: str | None,
        company_research: tuple[str, list[dict]] | None,
    ) -> InterviewPrepDossierContent:
        if company_research is not None and company_research[0]:
            research_block = (
                "Web research synthesis about the company (use this to fill "
                "company_facts and recent_news, marking confidence as "
                "'verified_web_search' for facts genuinely grounded in it):\n"
                f"{company_research[0]}"
            )
        else:
            research_block = (
                "No web research is available for this company. Do NOT invent "
                "specific facts (founding year, revenue, CEO name, recent news) "
                "you are not confident about - leave those fields null and mark "
                "company_facts.confidence as 'general_knowledge_unverified'. You "
                "may still use general knowledge you're confident about, but never "
                "fabricate anything to sound more informed."
            )

        prompt = (
            "Prepare a structured interview-preparation dossier for this "
            "candidate, who has a diagnostic already run against this specific "
            f"offer. Adopt this coaching persona/tone: {persona}.\n\n"
            f"{research_block}\n\n"
            f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}\n\n"
            f"Missing keywords from the candidate's diagnostic: {missing_keywords}\n"
            f"Recommendations from the candidate's diagnostic: {recommendations}\n\n"
            "For probable_questions, ground several questions in the actual "
            "missing keywords/recommendations above via targets_weak_point, so "
            "they read as tailored to this candidate's real gaps rather than "
            "generic interview questions."
        )
        if extra_context:
            prompt += f"\n\nAdditional context from the candidate: {extra_context}"

        last_error: Exception | None = None
        for _ in range(_MAX_DOSSIER_ATTEMPTS):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    # Structured extraction, not open-ended reasoning - and no
                    # web_search tool declared here, so a forced tool_choice
                    # can't be sidetracked into searching mid-extraction.
                    thinking={"type": "disabled"},
                    tools=[_INTERVIEW_DOSSIER_TOOL],
                    tool_choice={
                        "type": "tool",
                        "name": _INTERVIEW_DOSSIER_TOOL["name"],
                    },
                    messages=[{"role": "user", "content": prompt}],
                )
                tool_use = next(
                    (block for block in response.content if block.type == "tool_use"),
                    None,
                )
                if tool_use is None:
                    raise InterviewPrepError("No tool_use block in Claude response")
                return InterviewPrepDossierContent.model_validate(tool_use.input)
            except (ValidationError, InterviewPrepError, anthropic.APIError) as exc:
                last_error = exc
                continue
        raise InterviewPrepError(
            f"Dossier generation failed after retries: {last_error}"
        )
