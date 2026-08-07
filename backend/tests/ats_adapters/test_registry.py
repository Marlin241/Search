from app.ats_adapters.greenhouse import GreenhouseAdapter
from app.ats_adapters.lever import LeverAdapter
from app.ats_adapters.registry import get_ats_adapter


def test_get_ats_adapter_returns_greenhouse_adapter():
    assert isinstance(get_ats_adapter("greenhouse"), GreenhouseAdapter)


def test_get_ats_adapter_returns_lever_adapter():
    assert isinstance(get_ats_adapter("lever"), LeverAdapter)


def test_get_ats_adapter_returns_none_for_unsupported_type():
    assert get_ats_adapter("workday") is None
    assert get_ats_adapter(None) is None
