from functools import lru_cache

from app.ats_adapters.base import HtmlFormAdapter
from app.ats_adapters.greenhouse import GreenhouseAdapter
from app.ats_adapters.lever import LeverAdapter

_ADAPTERS: dict[str, type[HtmlFormAdapter]] = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
}


@lru_cache
def _adapter_instance(ats_type: str) -> HtmlFormAdapter:
    # Cached (one instance per ats_type, for the app's lifetime) rather than
    # constructed fresh on every call: each adapter holds its own httpx.Client
    # internally (Task 12), and get_ats_adapter is called directly - not
    # through a per-request FastAPI Depends - from Task 17's router on every
    # prefilled-form/confirm request, so a fresh instance per call would leak
    # an unclosed httpx.Client per request. This mirrors the lru_cache
    # singleton pattern already used for get_object_storage/get_semantic_analyzer.
    return _ADAPTERS[ats_type]()


def get_ats_adapter(ats_type: str | None) -> HtmlFormAdapter | None:
    if ats_type not in _ADAPTERS:
        return None
    return _adapter_instance(ats_type)
