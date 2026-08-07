from functools import lru_cache

import anthropic

from app.config import get_settings
from app.ats_adapters.custom_fields import CustomFieldAnswerer


@lru_cache
def get_custom_field_answerer() -> CustomFieldAnswerer:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=30.0, max_retries=0)
    return CustomFieldAnswerer(client)
