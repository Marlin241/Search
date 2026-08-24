from functools import lru_cache

import anthropic

from app.compatibility.analyzer import CompatibilityDetailAnalyzer
from app.config import get_settings


@lru_cache
def get_compatibility_detail_analyzer() -> CompatibilityDetailAnalyzer:
    settings = get_settings()
    # See app.llm_analyzer.dependencies.get_semantic_analyzer for why
    # max_retries=0 and a bounded timeout: this call holds a per-user DB row
    # lock for its duration (app.rate_limit.limiter), and the analyzer
    # already retries itself.
    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=30.0,
        max_retries=0,
    )
    return CompatibilityDetailAnalyzer(client)
