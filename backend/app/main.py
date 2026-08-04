from fastapi import FastAPI

from app.database import Base, engine
from app.routers import auth
import app.models  # noqa: F401 register models on Base

app = FastAPI(title="ATS Diagnostic API")

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
