from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, diagnostics
import app.models  # noqa: F401 register models on Base

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Deferred to app startup (rather than module import time) so that
    # merely importing app.main - e.g. for linting, OpenAPI generation, or
    # `pytest --collect-only` - does not connect to and issue DDL against
    # whatever DATABASE_URL happens to be configured on the machine.
    Base.metadata.create_all(bind=engine)
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
