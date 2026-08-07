from types import SimpleNamespace

import anthropic
import pytest

from app.ats_adapters.custom_fields import CustomFieldAnsweringError, CustomFieldAnswerer
from app.ats_adapters.schemas import FormField


def _fake_tool_use_response(input_payload: dict):
    block = SimpleNamespace(type="tool_use", input=input_payload)
    return SimpleNamespace(content=[block])


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


_FIELDS = [
    FormField(name="custom_why", label="Why this role?", field_type="textarea", required=False, is_custom=True),
    FormField(name="custom_salary", label="Salary expectations", field_type="text", required=False, is_custom=True),
]


def test_answer_returns_only_confident_answers():
    client = FakeClient(
        [
            _fake_tool_use_response(
                {
                    "answers": [
                        {"field_name": "custom_why", "answer": "Mon expérience Python correspond au poste.", "confident": True},
                        {"field_name": "custom_salary", "answer": "", "confident": False},
                    ]
                }
            )
        ]
    )
    answerer = CustomFieldAnswerer(client)

    answers = answerer.answer(_FIELDS, "cv text", "offer text")

    assert answers == {"custom_why": "Mon expérience Python correspond au poste."}


def test_answer_with_no_custom_fields_skips_the_llm_call():
    client = FakeClient([])
    answerer = CustomFieldAnswerer(client)

    assert answerer.answer([], "cv text", "offer text") == {}
    assert client.messages.calls == []


def test_answer_retries_once_on_invalid_payload_then_succeeds():
    client = FakeClient(
        [
            _fake_tool_use_response({"answers": [{"field_name": "x"}]}),
            _fake_tool_use_response({"answers": [{"field_name": "custom_why", "answer": "OK", "confident": True}]}),
        ]
    )
    answerer = CustomFieldAnswerer(client)

    answers = answerer.answer(_FIELDS, "cv text", "offer text")
    assert answers == {"custom_why": "OK"}
    assert len(client.messages.calls) == 2


def test_answer_raises_after_two_failures():
    client = FakeClient([_fake_tool_use_response({"answers": [{"field_name": "x"}]})] * 2)
    answerer = CustomFieldAnswerer(client)

    with pytest.raises(CustomFieldAnsweringError):
        answerer.answer(_FIELDS, "cv text", "offer text")


def test_answer_retries_on_api_error():
    client = FakeClient(
        [
            anthropic.APIConnectionError(request=SimpleNamespace()),
            _fake_tool_use_response({"answers": [{"field_name": "custom_why", "answer": "OK", "confident": True}]}),
        ]
    )
    answerer = CustomFieldAnswerer(client)

    answers = answerer.answer(_FIELDS, "cv text", "offer text")
    assert answers == {"custom_why": "OK"}
