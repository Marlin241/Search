from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.generation_jobs import state
from app.models.user import User
from app.schemas.generation_job import GenerationJobOut

router = APIRouter(prefix="/generation-jobs", tags=["generation_jobs"])


@router.get("/{job_id}", response_model=GenerationJobOut)
def get_generation_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> GenerationJobOut:
    job = state.get(job_id, current_user.id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable."
        )
    return GenerationJobOut(
        status=job.status,
        current_step=job.current_step,
        step_index=job.step_index,
        total_steps=job.total_steps,
        result=job.result,
        error=job.error,
    )
