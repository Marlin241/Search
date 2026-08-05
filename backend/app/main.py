from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, diagnostics
import app.models  # noqa: F401 register models on Base

settings = get_settings()

app = FastAPI(title="ATS Diagnostic API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(diagnostics.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
