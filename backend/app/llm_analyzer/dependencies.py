from functools import lru_cache

from app.config import get_settings
from app.llm.client import build_anthropic_client
from app.llm_analyzer.analyzer import SemanticAnalyzer


@lru_cache
def get_semantic_analyzer() -> SemanticAnalyzer:
    settings = get_settings()
    # Bound the worst-case latency of a single Anthropic call: this request
    # holds a per-user DB row lock (see app.rate_limit.limiter) for the
    # duration of the LLM call, so an unbounded/very-long default timeout
    # combined with the Anthropic SDK's own retries could hold that lock
    # (and a DB connection) for a very long time under a hung API response.
    # max_retries=0 avoids double-retrying on top of SemanticAnalyzer's own
    # 2-attempt retry loop.
    client = build_anthropic_client(
        api_key=settings.anthropic_api_key,
        timeout=30.0,
        max_retries=0,
    )
    return SemanticAnalyzer(client)
