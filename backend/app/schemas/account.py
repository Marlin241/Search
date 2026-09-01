from pydantic import BaseModel, Field


class AccountDeleteIn(BaseModel):
    password: str = Field(min_length=1)
