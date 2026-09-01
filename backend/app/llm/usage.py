from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_calls: ContextVar[list["_Call"] | None] = ContextVar("_llm_calls", default=None)


@dataclass(frozen=True)
class _Call:
    model: str | None
    input_tokens: int
    output_tokens: int


@contextmanager
def capture_usage():
    """Within this context, every messages.create() call made through a
    client built by app.llm.client.build_anthropic_client is recorded."""
    token = _calls.set([])
    try:
        yield
    finally:
        _calls.reset(token)


def _note(model: str | None, usage) -> None:
    bucket = _calls.get()
    if bucket is None:
        return
    it = int(getattr(usage, "input_tokens", 0) or 0)
    ot = int(getattr(usage, "output_tokens", 0) or 0)
    bucket.append(_Call(model, it, ot))


def collected() -> tuple[str | None, int, int]:
    """(model of the first sub-call, summed input tokens, summed output
    tokens). (None, 0, 0) if nothing was recorded."""
    bucket = _calls.get() or []
    if not bucket:
        return (None, 0, 0)
    return (
        bucket[0].model,
        sum(c.input_tokens for c in bucket),
        sum(c.output_tokens for c in bucket),
    )
