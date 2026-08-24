import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from app.utils.time import utcnow

# Longer than job_search.background_discovery's 5 min TTL: interview-prep
# generation (a later phase, reusing this same infra) can take 5-10 min, and
# the state must outlive the whole run plus a reasonable client poll delay
# after completion.
_STATE_TTL = timedelta(minutes=30)


@dataclass
class JobState:
    user_id: int
    status: Literal["running", "done", "error"]
    current_step: str
    step_index: int
    total_steps: int
    started_at: datetime = field(default_factory=utcnow)
    result: Any | None = None
    error: str | None = None


_lock = threading.Lock()
_state: dict[str, JobState] = {}


def _purge_expired() -> None:
    cutoff = utcnow() - _STATE_TTL
    with _lock:
        expired = [
            job_id for job_id, entry in _state.items() if entry.started_at < cutoff
        ]
        for job_id in expired:
            del _state[job_id]


def create_job(user_id: int, total_steps: int) -> str:
    _purge_expired()
    job_id = secrets.token_urlsafe(16)
    with _lock:
        _state[job_id] = JobState(
            user_id=user_id,
            status="running",
            current_step="",
            step_index=0,
            total_steps=total_steps,
        )
    return job_id


def advance(job_id: str, step_index: int, current_step: str) -> None:
    with _lock:
        entry = _state.get(job_id)
        if entry is not None:
            entry.step_index = step_index
            entry.current_step = current_step


def complete(job_id: str, result: Any) -> None:
    with _lock:
        entry = _state.get(job_id)
        if entry is not None:
            entry.status = "done"
            entry.result = result


def fail(job_id: str, error: str) -> None:
    with _lock:
        entry = _state.get(job_id)
        if entry is not None:
            entry.status = "error"
            entry.error = error


def get(job_id: str, user_id: int) -> JobState | None:
    _purge_expired()
    with _lock:
        entry = _state.get(job_id)
        if entry is None or entry.user_id != user_id:
            return None
        return entry
