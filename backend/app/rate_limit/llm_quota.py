from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.llm_call_log import LlmCallLog
from app.models.user import User
from app.utils.time import utcnow

FEATURES = (
    "diagnostic",
    "cv",
    "lettre",
    "compatibility",
    "interview_prep",
    "ats_prefill",
)
FEATURE_LABELS = {
    "diagnostic": "diagnostics",
    "cv": "CV générés",
    "lettre": "lettres de motivation",
    "compatibility": "analyses de compatibilité",
    "interview_prep": "préparations d'entretien",
    "ats_prefill": "préremplissages de formulaire",
}


def _month_start() -> datetime:
    return utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month_start_date() -> date:
    d = _month_start().date()
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


class QuotaExceeded(Exception):
    def __init__(self, feature: str, limit: int, reset_date: str) -> None:
        self.feature = feature
        self.limit = limit
        self.reset_date = reset_date
        super().__init__(f"quota exceeded for {feature}")

    def as_dict(self) -> dict:
        label = FEATURE_LABELS.get(self.feature, self.feature)
        return {
            "code": "quota_exceeded",
            "feature": self.feature,
            "limit": self.limit,
            "reset_date": self.reset_date,
            "message": (
                f"Tu as atteint ta limite beta de {self.limit} {label} ce "
                f"mois-ci. Elle se réinitialise le {self.reset_date}."
            ),
        }


def monthly_limit(user: User, feature: str) -> int:
    if user.quota_overrides and feature in user.quota_overrides:
        return int(user.quota_overrides[feature])
    return get_settings().llm_monthly_quotas[feature]


def used_this_month(db: Session, user_id: int, feature: str) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(LlmCallLog)
            .where(
                LlmCallLog.user_id == user_id,
                LlmCallLog.feature == feature,
                LlmCallLog.created_at >= _month_start(),
            )
        )
        or 0
    )


def enforce_monthly_quota(db: Session, user: User, feature: str) -> None:
    limit = monthly_limit(user, feature)
    if used_this_month(db, user.id, feature) >= limit:
        raise QuotaExceeded(feature, limit, _next_month_start_date().isoformat())


def record_llm_call(
    db: Session,
    *,
    user_id: int,
    feature: str,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    db.add(
        LlmCallLog(
            user_id=user_id,
            feature=feature,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    )
    db.commit()


def usage_summary(db: Session, user: User) -> list[dict]:
    reset = _next_month_start_date().isoformat()
    return [
        {
            "feature": f,
            "label": FEATURE_LABELS[f],
            "used": used_this_month(db, user.id, f),
            "limit": monthly_limit(user, f),
            "reset_date": reset,
        }
        for f in FEATURES
    ]
