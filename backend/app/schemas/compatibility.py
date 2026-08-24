from pydantic import BaseModel

from app.job_search.schemas import JobListing


class CompatibilityDetailIn(BaseModel):
    listing: JobListing


class CompatibilityScoreBreakdown(BaseModel):
    title: int
    location: int
    seniority: int
    salary: int
    freshness: int
    overall: int


class CompatibilityDetailOut(BaseModel):
    breakdown: CompatibilityScoreBreakdown
    summary: str
    strengths: list[str]
    concerns: list[str]
