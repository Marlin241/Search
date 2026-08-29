from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    invite_code: str = Field(min_length=1)
    accept_terms: bool

    @field_validator("accept_terms")
    @classmethod
    def _must_accept(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Vous devez accepter les conditions.")
        return v


class UserOut(BaseModel):
    id: int
    email: str

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsageItemOut(BaseModel):
    feature: str
    label: str
    used: int
    limit: int
    reset_date: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=72)
