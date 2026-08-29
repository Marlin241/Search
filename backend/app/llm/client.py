import anthropic

from app.llm.usage import _note


class _RecordingMessages:
    def __init__(self, inner) -> None:
        self._inner = inner

    def create(self, **kwargs):
        response = self._inner.create(**kwargs)
        _note(kwargs.get("model"), getattr(response, "usage", None))
        return response

    def __getattr__(self, name):
        return getattr(self._inner, name)


class UsageRecordingAnthropic:
    """Thin proxy over anthropic.Anthropic that records token usage of every
    messages.create() call into the app.llm.usage ContextVar. Every other
    attribute (.beta, streaming, etc.) delegates straight through - usage
    for those paths is simply not recorded (acceptable: the analyzers in
    this app only use messages.create)."""

    def __init__(self, inner: anthropic.Anthropic) -> None:
        self._inner = inner
        self.messages = _RecordingMessages(inner.messages)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def build_anthropic_client(**kwargs) -> UsageRecordingAnthropic:
    return UsageRecordingAnthropic(anthropic.Anthropic(**kwargs))
