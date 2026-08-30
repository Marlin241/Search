from pydantic import BaseModel, Field


class FeedbackIn(BaseModel):
    page: str = Field(max_length=255)
    message: str = Field(min_length=1, max_length=5000)
