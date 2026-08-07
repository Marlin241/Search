from datetime import datetime

from pydantic import BaseModel


class CandidateProfileIn(BaseModel):
    full_name: str
    phone: str
    address: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    work_authorization: str
    salary_expectation: str | None = None


class CandidateProfileOut(BaseModel):
    full_name: str
    phone: str
    address: str | None
    linkedin_url: str | None
    portfolio_url: str | None
    work_authorization: str
    salary_expectation: str | None
    cv_filename: str | None
    has_cv: bool
    updated_at: datetime
