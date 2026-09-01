from functools import lru_cache

from app.config import get_settings
from app.llm.client import UsageRecordingAnthropic, build_anthropic_client
from app.personalization.analyzer import CoverLetterGenerator, CvRewriter


def _build_client() -> UsageRecordingAnthropic:
    settings = get_settings()
    # Same reasoning as app.llm_analyzer.dependencies.get_semantic_analyzer:
    # this call holds the per-user rate-limit row lock for its duration, so
    # it must not be allowed to hang for the SDK's very-long default
    # timeout. max_retries=0 avoids double-retrying on top of the
    # 2-attempt retry loop in app.personalization.analyzer. The timeout is
    # higher than the diagnostic's 30s because CV rewriting produces more
    # output tokens.
    return build_anthropic_client(
        api_key=settings.anthropic_api_key,
        timeout=60.0,
        max_retries=0,
    )


@lru_cache
def get_cv_rewriter() -> CvRewriter:
    return CvRewriter(_build_client())


@lru_cache
def get_cover_letter_generator() -> CoverLetterGenerator:
    return CoverLetterGenerator(_build_client())
