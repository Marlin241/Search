from datetime import datetime

from pydantic import BaseModel


class CandidateProfileIn(BaseModel):
    first_name: str
    last_name: str
    phone: str
    address: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    work_authorization: str
    salary_expectation: str | None = None


class CandidateProfileOut(BaseModel):
    first_name: str
    last_name: str
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
    desired_job_titles: list[str] | None
    seniority_level: str | None
    desired_locations: list[str] | None
    remote_preference: bool
    contract_types: list[str] | None
    salary_min: int | None
    salary_max: int | None
    weekly_application_goal: int | None
    has_profile_photo: bool


class OnboardingProfileIn(BaseModel):
    first_name: str
    last_name: str
    desired_job_titles: list[str] = []
    seniority_level: str | None = None
    desired_locations: list[str] = []
    remote_preference: bool = False
    contract_types: list[str] = []
    salary_min: int | None = None
    salary_max: int | None = None
    weekly_application_goal: int | None = None


class ExtractedPhotoOut(BaseModel):
    key: str
    preview_url: str
