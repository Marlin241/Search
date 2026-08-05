from types import SimpleNamespace

import anthropic
import pytest

from app.llm_analyzer.analyzer import SemanticAnalyzer, LLMAnalysisError


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


def test_analyze_returns_parsed_report_on_valid_response():
    client = FakeClient(
        [_fake_tool_use_response({"score": 72, "missing_keywords": ["Docker"], "recommendations": ["Add Docker"]})]
    )
    analyzer = SemanticAnalyzer(client)

    report = analyzer.analyze("cv text", "offer text")

    assert report.score == 72
    assert report.missing_keywords == ["Docker"]
    assert report.recommendations == ["Add Docker"]
    assert client.messages.calls[0]["tool_choice"] == {"type": "tool", "name": "submit_diagnostic"}


def test_analyze_retries_once_on_invalid_payload_then_succeeds():
    client = FakeClient(
        [
            _fake_tool_use_response({"score": "not-a-number"}),
            _fake_tool_use_response({"score": 50, "missing_keywords": [], "recommendations": []}),
        ]
    )
    analyzer = SemanticAnalyzer(client)

    report = analyzer.analyze("cv text", "offer text")

    assert report.score == 50
    assert len(client.messages.calls) == 2


def test_analyze_raises_after_two_failures():
    client = FakeClient(
        [
            _fake_tool_use_response({"score": "not-a-number"}),
            _fake_tool_use_response({"score": "still-not-a-number"}),
        ]
    )
    analyzer = SemanticAnalyzer(client)

    with pytest.raises(LLMAnalysisError):
        analyzer.analyze("cv text", "offer text")


def test_analyze_retries_once_on_out_of_range_score_then_succeeds():
    client = FakeClient(
        [
            _fake_tool_use_response({"score": 150, "missing_keywords": [], "recommendations": []}),
            _fake_tool_use_response({"score": 50, "missing_keywords": [], "recommendations": []}),
        ]
    )
    analyzer = SemanticAnalyzer(client)

    report = analyzer.analyze("cv text", "offer text")

    assert report.score == 50
    assert len(client.messages.calls) == 2


def test_analyze_raises_when_both_attempts_return_out_of_range_score():
    client = FakeClient(
        [
            _fake_tool_use_response({"score": 1000, "missing_keywords": [], "recommendations": []}),
            _fake_tool_use_response({"score": -500, "missing_keywords": [], "recommendations": []}),
        ]
    )
    analyzer = SemanticAnalyzer(client)

    with pytest.raises(LLMAnalysisError):
        analyzer.analyze("cv text", "offer text")


def test_analyze_retries_on_api_error():
    client = FakeClient(
        [
            anthropic.APIConnectionError(request=SimpleNamespace()),
            _fake_tool_use_response({"score": 40, "missing_keywords": [], "recommendations": []}),
        ]
    )
    analyzer = SemanticAnalyzer(client)

    report = analyzer.analyze("cv text", "offer text")
    assert report.score == 40
