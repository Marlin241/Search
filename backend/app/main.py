from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import (
    database,
    models,  # noqa: F401 register models on Base
)
from app.applications.reminders import run_application_reminders
from app.config import get_settings
from app.job_search.daily_search import run_daily_search
from app.routers import (
    applications,
    auth,
    candidate_profile,
    diagnostics,
    job_search,
    personalization,
)

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

    # A fresh BackgroundScheduler is created on every lifespan entry
    # (rather than a module-level singleton) because APScheduler schedulers
    # cannot be restarted after shutdown() - a module-level instance would
    # break the second of any two `with TestClient(app)` blocks in the test
    # suite, which each trigger one lifespan start/stop cycle.
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        # Looked up as database.SessionLocal (not a bare `SessionLocal` name
        # imported at module load) so the test suite's monkeypatch of
        # database.SessionLocal (see tests/conftest.py) takes effect - same
        # convention as the background_discovery.run_discovery task.
        lambda: run_daily_search(database.SessionLocal),
        trigger="cron",
        minute=0,
        id="daily_search",
    )
    scheduler.add_job(
        # Same rationale as the daily_search job above: looked up as
        # database.SessionLocal at call time, not imported at module load,
        # so the test suite's monkeypatch takes effect.
        lambda: run_application_reminders(database.SessionLocal),
        trigger="cron",
        minute=0,
        id="application_reminders",
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="ATS Diagnostic API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(applications.router)
app.include_router(diagnostics.router)
app.include_router(personalization.router)
app.include_router(candidate_profile.router)
app.include_router(job_search.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
