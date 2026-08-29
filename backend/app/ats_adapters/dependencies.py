from functools import lru_cache

from app.ats_adapters.custom_fields import CustomFieldAnswerer
from app.config import get_settings
from app.llm.client import build_anthropic_client


@lru_cache
def get_custom_field_answerer() -> CustomFieldAnswerer:
    settings = get_settings()
    client = build_anthropic_client(
        api_key=settings.anthropic_api_key, timeout=30.0, max_retries=0
    )
    return CustomFieldAnswerer(client)
