from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.app_setting import AppSetting
from app.utils.time import utcnow

_KEY = "llm_features_enabled"


def llm_features_enabled(db: Session) -> bool:
    """DB flag wins over the env default, so the kill-switch takes effect
    without a redeploy."""
    row = db.get(AppSetting, _KEY)
    if row is not None:
        return row.value == "true"
    return get_settings().llm_features_enabled


def set_llm_features_enabled(db: Session, enabled: bool) -> None:
    row = db.get(AppSetting, _KEY)
    value = "true" if enabled else "false"
    if row is None:
        db.add(AppSetting(key=_KEY, value=value, updated_at=utcnow()))
    else:
        row.value = value
        row.updated_at = utcnow()
    db.commit()
