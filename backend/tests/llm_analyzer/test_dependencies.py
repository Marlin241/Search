from app.llm_analyzer.dependencies import get_semantic_analyzer


def test_semantic_analyzer_client_has_bounded_timeout_and_no_sdk_retries():
    # The per-user rate-limit row lock (app.rate_limit.limiter) is held for
    # the duration of the LLM call, so the Anthropic client must not be
    # allowed to hang for its very-long SDK default timeout. max_retries=0
    # avoids double-retrying on top of SemanticAnalyzer's own 2-attempt
    # retry loop. get_semantic_analyzer is @lru_cache'd, so this reads back
    # whatever client was actually constructed for the app.
    get_semantic_analyzer.cache_clear()
    analyzer = get_semantic_analyzer()
    client = analyzer._client

    assert client.timeout == 30.0
    assert client.max_retries == 0

    get_semantic_analyzer.cache_clear()
