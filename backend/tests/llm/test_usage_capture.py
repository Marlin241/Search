from app.llm.client import build_anthropic_client
from app.llm.usage import capture_usage, collected


class _FakeUsage:
    def __init__(self, i, o):
        self.input_tokens, self.output_tokens = i, o


class _FakeResp:
    def __init__(self, i, o):
        self.usage = _FakeUsage(i, o)
        self.content = []


class _FakeMessages:
    def create(self, **kw):
        return _FakeResp(100, 50)


class _FakeAnthropic:
    def __init__(self, **kw):
        self.messages = _FakeMessages()


def test_capture_sums_tokens_across_calls(monkeypatch):
    monkeypatch.setattr("app.llm.client.anthropic.Anthropic", _FakeAnthropic)
    client = build_anthropic_client(api_key="x")
    with capture_usage():
        client.messages.create(model="claude-haiku-4-5-20251001", messages=[])
        client.messages.create(model="claude-haiku-4-5-20251001", messages=[])
        assert collected() == ("claude-haiku-4-5-20251001", 200, 100)


def test_no_capture_context_is_noop(monkeypatch):
    monkeypatch.setattr("app.llm.client.anthropic.Anthropic", _FakeAnthropic)
    client = build_anthropic_client(api_key="x")
    client.messages.create(model="m", messages=[])  # must not raise
    assert collected() == (None, 0, 0)


def test_contexts_are_isolated(monkeypatch):
    monkeypatch.setattr("app.llm.client.anthropic.Anthropic", _FakeAnthropic)
    client = build_anthropic_client(api_key="x")
    with capture_usage():
        client.messages.create(model="m", messages=[])
    with capture_usage():
        assert collected() == (None, 0, 0)
