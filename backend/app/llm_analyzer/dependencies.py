from functools import lru_cache

import anthropic

from app.config import get_settings
from app.llm_analyzer.analyzer import SemanticAnalyzer


@lru_cache
def get_semantic_analyzer() -> SemanticAnalyzer:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return SemanticAnalyzer(client)
