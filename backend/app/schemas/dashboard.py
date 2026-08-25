from datetime import datetime

from pydantic import BaseModel

from app.schemas.application import ApplicationOut


class KanbanSavedJobOut(BaseModel):
    """Purpose-built card shape for the Kanban's "Sauvegardées" column -
    a lighter subset of SavedJobOut, since a Kanban card doesn't need the
    full diagnostic/documents assembly GET /saved-jobs/{id} does."""

    id: int
    title: str
    company: str
    offer_url: str
    created_at: datetime


class KanbanBoardOut(BaseModel):
    sauvegardees: list[KanbanSavedJobOut]
    postule: list[ApplicationOut]
    entretien_programme: list[ApplicationOut]
    proposition: list[ApplicationOut]
    refusee: list[ApplicationOut]
