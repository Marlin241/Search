import pytest
from fastapi import HTTPException

from app.llm.dependencies import require_llm_enabled
from app.llm.switch import llm_features_enabled, set_llm_features_enabled


def test_default_is_enabled(db_session):
    assert llm_features_enabled(db_session) is True


def test_db_flag_overrides(db_session):
    set_llm_features_enabled(db_session, False)
    assert llm_features_enabled(db_session) is False
    set_llm_features_enabled(db_session, True)
    assert llm_features_enabled(db_session) is True


def test_dependency_raises_503_when_off(db_session):
    set_llm_features_enabled(db_session, False)
    with pytest.raises(HTTPException) as ei:
        require_llm_enabled(db_session)
    assert ei.value.status_code == 503
    assert ei.value.detail["code"] == "llm_paused"
