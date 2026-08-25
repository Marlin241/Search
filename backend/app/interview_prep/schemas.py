from typing import Literal

from pydantic import BaseModel


class CompanyFacts(BaseModel):
    founding_year: int | None = None
    headquarters: str | None = None
    sector: str | None = None
    revenue: str | None = None
    ceo: str | None = None
    confidence: Literal["verified_web_search", "general_knowledge_unverified"]


class RecentNewsItem(BaseModel):
    headline: str
    summary: str
    source_url: str | None = None


class ProbableQuestion(BaseModel):
    question: str
    # References the specific missing_keyword/recommendation this question
    # targets, so questions read as tailored to this candidate's real gaps
    # rather than generic interview prep. Null when a question is a general
    # one not tied to a specific weak point.
    targets_weak_point: str | None = None
    model_answer: str


class PracticalExercise(BaseModel):
    title: str
    prompt: str
    pitfalls_to_avoid: list[str] = []
    difficulty: Literal["facile", "moyen", "difficile"]


class CoachingChecklist(BaseModel):
    before: list[str] = []
    during: list[str] = []
    after: list[str] = []


class InterviewPrepDossierContent(BaseModel):
    narrative_angle: str
    company_facts: CompanyFacts
    recent_news: list[RecentNewsItem] = []
    probable_questions: list[ProbableQuestion] = []
    practical_exercises: list[PracticalExercise] = []
    coaching_checklist: CoachingChecklist
