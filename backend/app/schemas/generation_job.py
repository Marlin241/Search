from typing import Any, Literal

from pydantic import BaseModel


class GenerationJobStarted(BaseModel):
    job_id: str


class GenerationJobOut(BaseModel):
    status: Literal["running", "done", "error"]
    current_step: str
    step_index: int
    total_steps: int
    result: dict[str, Any] | None = None
    error: str | None = None
