from functools import lru_cache

from app.compatibility.analyzer import CompatibilityDetailAnalyzer
from app.config import get_settings
from app.llm.client import build_anthropic_client


@lru_cache
def get_compatibility_detail_analyzer() -> CompatibilityDetailAnalyzer:
    settings = get_settings()
    # See app.llm_analyzer.dependencies.get_semantic_analyzer for why
    # max_retries=0 and a bounded timeout: this call holds a per-user DB row
    # lock for its duration (app.rate_limit.limiter), and the analyzer
    # already retries itself.
    client = build_anthropic_client(
        api_key=settings.anthropic_api_key,
        timeout=30.0,
        max_retries=0,
    )
    return CompatibilityDetailAnalyzer(client)
