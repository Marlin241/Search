from pydantic import BaseModel

from app.schemas.auth import UsageItemOut


class AdminUserOut(BaseModel):
    id: int
    email: str
    created_at: str
    is_admin: bool
    is_active: bool
    invite_note: str | None
    consent_version: str | None
    consent_accepted_at: str | None
    last_activity_at: str | None
    quota_overrides: dict | None = None
    usage: list[UsageItemOut]


class QuotaPatchIn(BaseModel):
    feature: str
    limit: int | None


class ActivePatchIn(BaseModel):
    active: bool


class AdminInviteOut(BaseModel):
    code: str
    note: str | None
    created_at: str
    expires_at: str | None
    used_by_email: str | None
    used_at: str | None


class InviteCreateIn(BaseModel):
    count: int
    note: str | None = None


class InviteCreateOut(BaseModel):
    codes: list[str]


class LlmToggleIn(BaseModel):
    enabled: bool


class LlmToggleOut(BaseModel):
    enabled: bool


class AdminFeedbackOut(BaseModel):
    id: int
    user_email: str | None
    page: str
    message: str
    created_at: str
    handled_at: str | None
