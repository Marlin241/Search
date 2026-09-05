import anthropic
from pydantic import BaseModel, ValidationError


class CompatibilityDetail(BaseModel):
    summary: str
    strengths: list[str]
    concerns: list[str]


class CompatibilityAnalysisError(Exception):
    pass


_COMPATIBILITY_DETAIL_TOOL = {
    "name": "submit_compatibility_detail",
    "description": (
        "Submit an honest explanation of an already-computed compatibility "
        "score between a CV and a job offer."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "1-2 sentence honest verdict explaining the given score.",
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete reasons this CV is a good match for this offer.",
            },
            "concerns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete gaps or mismatches the candidate should know about before applying.",
            },
        },
        "required": ["summary", "strengths", "concerns"],
    },
}

_MAX_ATTEMPTS = 2


class CompatibilityDetailAnalyzer:
    def __init__(self, client, model: str = "claude-haiku-4-5-20251001"):
        self._client = client
        self._model = model

    def analyze(
        self, cv_text: str, offer_text: str, score_breakdown: dict[str, int | None]
    ) -> CompatibilityDetail:
        def _fmt(key: str) -> str:
            value = score_breakdown[key]
            return (
                "non évalué (pas assez de données)" if value is None else f"{value}/100"
            )

        breakdown_summary = (
            f"Intitulé de poste: {_fmt('title')}, "
            f"Localisation: {_fmt('location')}, "
            f"Expérience/séniorité: {_fmt('seniority')}, "
            f"Salaire: {_fmt('salary')}, "
            f"Fraîcheur de l'offre: {_fmt('freshness')}, "
            f"Score global: {score_breakdown['overall']}/100"
        )
        last_error: Exception | None = None
        for _ in range(_MAX_ATTEMPTS):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    # anthropic>=1.0 dropped `temperature` from
                    # messages.create() entirely - determinism for this
                    # structured explanation comes from the forced
                    # tool_choice below instead (see app.llm_analyzer.analyzer
                    # for the same fix on the diagnostic analyzer).
                    tools=[_COMPATIBILITY_DETAIL_TOOL],
                    tool_choice={"type": "tool", "name": "submit_compatibility_detail"},
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                "A deterministic rubric already scored this CV against this "
                                "job offer on title/location/experience/salary/freshness "
                                "match (below). Explain that score honestly in 1-2 sentences, "
                                "then list concrete strengths and concerns a candidate should "
                                "know before applying. Do not recompute or contradict the "
                                "given score - explain it. Respond in the same language as "
                                "the CV.\n\n"
                                f"Score breakdown:\n{breakdown_summary}\n\n"
                                f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}"
                            ),
                        }
                    ],
                )
                tool_use = next(
                    (block for block in response.content if block.type == "tool_use"),
                    None,
                )
                if tool_use is None:
                    raise CompatibilityAnalysisError(
                        "No tool_use block in Claude response"
                    )
                return CompatibilityDetail.model_validate(tool_use.input)
            except (
                ValidationError,
                CompatibilityAnalysisError,
                anthropic.APIError,
            ) as exc:
                last_error = exc
                continue
        raise CompatibilityAnalysisError(
            f"Compatibility detail analysis failed after retries: {last_error}"
        )
