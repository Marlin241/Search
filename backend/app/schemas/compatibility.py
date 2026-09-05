from pydantic import BaseModel

from app.job_search.schemas import JobListing


class CompatibilityDetailIn(BaseModel):
    listing: JobListing


class CompatibilityScoreBreakdown(BaseModel):
    # None = not enough data to judge this criterion (no preference set, no
    # data on the listing...), never a guessed "neutral" value.
    title: int | None
    location: int | None
    seniority: int | None
    salary: int | None
    freshness: int | None
    overall: int


class CompatibilityDetailOut(BaseModel):
    breakdown: CompatibilityScoreBreakdown
    summary: str
    strengths: list[str]
    concerns: list[str]
