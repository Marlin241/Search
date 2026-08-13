from types import SimpleNamespace

import anthropic
import pytest

from app.personalization.analyzer import (
    CoverLetterGenerator,
    CvRewriter,
    PersonalizationError,
)


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


_VALID_CV_PAYLOAD = {
    "summary": "Résumé optimisé.",
    "experience": [
        {
            "title": "Développeuse",
            "company": "Acme",
            "dates": "2020-2022",
            "bullets": ["A conçu des API."],
        }
    ],
    "education": ["Master Informatique"],
    "skills": ["Python", "Docker"],
}

_VALID_LETTER_PAYLOAD = {
    "greeting": "Madame, Monsieur,",
    "body_paragraphs": ["Je vous écris pour candidater à ce poste."],
    "closing_formula": "Cordialement,",
    "signature": "Jane Doe",
}


def test_rewrite_returns_parsed_cv_on_valid_response():
    client = FakeClient([_fake_tool_use_response(_VALID_CV_PAYLOAD)])
    rewriter = CvRewriter(client)

    cv = rewriter.rewrite("cv text", "offer text", ["Docker"], ["Add Docker"])

    assert cv.summary == "Résumé optimisé."
    assert cv.experience[0].company == "Acme"
    assert client.messages.calls[0]["tool_choice"] == {
        "type": "tool",
        "name": "submit_rewritten_cv",
    }
    assert client.messages.calls[0]["model"] == "claude-sonnet-5"
    assert client.messages.calls[0]["thinking"] == {"type": "disabled"}


def test_rewrite_retries_once_on_invalid_payload_then_succeeds():
    client = FakeClient(
        [
            _fake_tool_use_response({"summary": "x"}),
            _fake_tool_use_response(_VALID_CV_PAYLOAD),
        ]
    )
    rewriter = CvRewriter(client)

    cv = rewriter.rewrite("cv text", "offer text", [], [])

    assert cv.summary == "Résumé optimisé."
    assert len(client.messages.calls) == 2


def test_rewrite_raises_after_two_failures():
    client = FakeClient(
        [
            _fake_tool_use_response({"summary": "x"}),
            _fake_tool_use_response({"summary": "y"}),
        ]
    )
    rewriter = CvRewriter(client)

    with pytest.raises(PersonalizationError):
        rewriter.rewrite("cv text", "offer text", [], [])


def test_rewrite_retries_on_api_error():
    client = FakeClient(
        [
            anthropic.APIConnectionError(request=SimpleNamespace()),
            _fake_tool_use_response(_VALID_CV_PAYLOAD),
        ]
    )
    rewriter = CvRewriter(client)

    cv = rewriter.rewrite("cv text", "offer text", [], [])
    assert cv.summary == "Résumé optimisé."


def test_generate_returns_parsed_letter_on_valid_response():
    client = FakeClient([_fake_tool_use_response(_VALID_LETTER_PAYLOAD)])
    generator = CoverLetterGenerator(client)

    letter = generator.generate("cv text", "offer text", [], [])

    assert letter.greeting == "Madame, Monsieur,"
    assert letter.body_paragraphs == ["Je vous écris pour candidater à ce poste."]
    assert client.messages.calls[0]["tool_choice"] == {
        "type": "tool",
        "name": "submit_cover_letter",
    }
    assert client.messages.calls[0]["thinking"] == {"type": "disabled"}


def test_generate_raises_after_two_failures():
    client = FakeClient(
        [
            _fake_tool_use_response({"greeting": "x"}),
            _fake_tool_use_response({"greeting": "y"}),
        ]
    )
    generator = CoverLetterGenerator(client)

    with pytest.raises(PersonalizationError):
        generator.generate("cv text", "offer text", [], [])
