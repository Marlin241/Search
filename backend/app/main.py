from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app import database
from app.routers import auth, candidate_profile, diagnostics, personalization
import app.models  # noqa: F401 register models on Base

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Deferred to app startup (rather than module import time) so that
    # merely importing app.main - e.g. for linting, OpenAPI generation, or
    # `pytest --collect-only` - does not connect to and issue DDL against
    # whatever DATABASE_URL happens to be configured on the machine.
    # Looked up via the `database` module (not a direct `engine` import) so
    # tests can monkeypatch `app.database.engine` to an isolated in-memory
    # database before the lifespan runs.
    database.Base.metadata.create_all(bind=database.engine)
    yield


app = FastAPI(title="ATS Diagnostic API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(diagnostics.router)
app.include_router(personalization.router)
app.include_router(candidate_profile.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
