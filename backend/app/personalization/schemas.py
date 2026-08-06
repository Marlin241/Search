from pydantic import BaseModel


class CvExperienceEntry(BaseModel):
    title: str
    company: str
    dates: str
    bullets: list[str]


class RewrittenCv(BaseModel):
    summary: str
    experience: list[CvExperienceEntry]
    education: list[str]
    skills: list[str]


class CoverLetter(BaseModel):
    greeting: str
    body_paragraphs: list[str]
    closing: str
