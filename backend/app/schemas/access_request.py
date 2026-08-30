from pydantic import BaseModel, EmailStr, Field


class AccessRequestIn(BaseModel):
    email: EmailStr
    note: str = Field(default="", max_length=1000)
    # Honeypot : un vrai humain laisse ce champ vide ; un bot le remplit.
    company: str = ""


class AdminAccessRequestOut(BaseModel):
    id: int
    email: str
    note: str
    created_at: str
    handled_at: str | None
