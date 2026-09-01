from functools import lru_cache

from app.config import get_settings
from app.interview_prep.analyzer import InterviewPrepAnalyzer
from app.llm.client import build_anthropic_client


@lru_cache
def get_interview_prep_analyzer() -> InterviewPrepAnalyzer:
    settings = get_settings()
    # This runs entirely inside a background job (app.interview_prep.jobs),
    # never while holding the rate-limit row lock (unlike the synchronous
    # personalization calls) - so a long timeout is safe here. Phase A
    # (web search) alone can take several minutes per the plan.
    client = build_anthropic_client(
        api_key=settings.anthropic_api_key,
        timeout=300.0,
        max_retries=0,
    )
    return InterviewPrepAnalyzer(client)
