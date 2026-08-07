import anthropic
from pydantic import BaseModel, ValidationError

from app.ats_adapters.schemas import FormField

_MAX_ATTEMPTS = 2

_CUSTOM_FIELDS_TOOL = {
    "name": "submit_custom_field_answers",
    "description": "Submit answers to a job application form's custom questions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_name": {"type": "string"},
                        "answer": {"type": "string"},
                        "confident": {
                            "type": "boolean",
                            "description": "False if the question cannot be answered with confidence from the CV/offer alone (e.g. a personal choice not derivable from the data) - in that case, answer should be empty.",
                        },
                    },
                    "required": ["field_name", "answer", "confident"],
                },
            }
        },
        "required": ["answers"],
    },
}


class CustomFieldAnsweringError(Exception):
    pass


class _CustomFieldAnswer(BaseModel):
    field_name: str
    answer: str
    confident: bool


class _CustomFieldAnswers(BaseModel):
    answers: list[_CustomFieldAnswer]


class CustomFieldAnswerer:
    def __init__(self, client, model: str = "claude-sonnet-5"):
        self._client = client
        self._model = model

    def answer(self, custom_fields: list[FormField], cv_text: str, offer_text: str) -> dict[str, str]:
        if not custom_fields:
            return {}

        fields_description = "\n".join(
            f"- name={f.name!r} label={f.label!r} options={f.options}" for f in custom_fields
        )
        prompt = (
            "A candidate is applying to this job offer using this CV. Answer "
            "each custom application question below on their behalf, using "
            "only information present in the CV and the offer - never invent "
            "experience or facts not present in the CV. If a question cannot "
            "be answered with confidence from the CV/offer alone (e.g. it "
            "asks for a personal choice like specific salary negotiation not "
            "derivable from the data), set confident=false and leave answer "
            "empty rather than guessing. Respond in the same language as the "
            "CV.\n\n"
            f"CV:\n{cv_text}\n\nJob offer:\n{offer_text}\n\nQuestions:\n{fields_description}"
        )

        last_error: Exception | None = None
        for _ in range(_MAX_ATTEMPTS):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    # claude-sonnet-5 runs adaptive thinking by default when
                    # `thinking` is omitted, and max_tokens caps thinking +
                    # response combined - which could silently truncate a
                    # forced tool_use JSON payload. This call is
                    # deterministic structured extraction, not open-ended
                    # reasoning, so thinking is disabled: max_tokens is then
                    # dedicated entirely to the response.
                    thinking={"type": "disabled"},
                    tools=[_CUSTOM_FIELDS_TOOL],
                    tool_choice={"type": "tool", "name": _CUSTOM_FIELDS_TOOL["name"]},
                    messages=[{"role": "user", "content": prompt}],
                )
                tool_use = next((block for block in response.content if block.type == "tool_use"), None)
                if tool_use is None:
                    raise CustomFieldAnsweringError("No tool_use block in Claude response")
                parsed = _CustomFieldAnswers.model_validate(tool_use.input)
                return {
                    a.field_name: a.answer.strip()
                    for a in parsed.answers
                    if a.confident and a.answer.strip()
                }
            except (ValidationError, CustomFieldAnsweringError, anthropic.APIError) as exc:
                last_error = exc
                continue
        raise CustomFieldAnsweringError(f"Custom field answering failed after retries: {last_error}")
