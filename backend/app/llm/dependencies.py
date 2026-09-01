from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.switch import llm_features_enabled


def require_llm_enabled(db: Session = Depends(get_db)) -> None:
    if not llm_features_enabled(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "llm_paused",
                "message": (
                    "Cette fonctionnalité est en pause (capacité beta). "
                    "Réessaie plus tard."
                ),
            },
        )
