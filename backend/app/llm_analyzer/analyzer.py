import anthropic
from pydantic import BaseModel, Field, ValidationError


class SemanticReport(BaseModel):
    score: int = Field(ge=0, le=100)
    missing_keywords: list[str]
    recommendations: list[str]


class LLMAnalysisError(Exception):
    pass


_DIAGNOSTIC_TOOL = {
    "name": "submit_diagnostic",
    "description": "Submit the semantic match diagnostic between a CV and a job offer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "description": "Compatibility score from 0 to 100 between the CV and the job offer.",
            },
            "missing_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skills or keywords present in the offer but missing from the CV.",
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete, actionable recommendations to improve the match.",
            },
        },
        "required": ["score", "missing_keywords", "recommendations"],
    },
}

_MAX_ATTEMPTS = 2


class SemanticAnalyzer:
    def __init__(self, client, model: str = "claude-haiku-4-5-20251001"):
        self._client = client
        self._model = model

    def analyze(self, cv_text: str, offer_text: str) -> SemanticReport:
        last_error: Exception | None = None
        for _ in range(_MAX_ATTEMPTS):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    tools=[_DIAGNOSTIC_TOOL],
                    tool_choice={"type": "tool", "name": "submit_diagnostic"},
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                "Compare this CV and this job offer. Identify the compatibility "
                                "score, missing keywords/skills, and concrete recommendations. "
                                "The CV and offer may be in French or English; respond in the "
                                "same language as the CV.\n\n"
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
                    raise LLMAnalysisError("No tool_use block in Claude response")
                return SemanticReport.model_validate(tool_use.input)
            except (ValidationError, LLMAnalysisError, anthropic.APIError) as exc:
                last_error = exc
                continue
        raise LLMAnalysisError(f"Semantic analysis failed after retries: {last_error}")
