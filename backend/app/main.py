import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import (
    database,
    models,  # noqa: F401 register models on Base
)
from app.applications.reminders import run_application_reminders
from app.config import get_settings
from app.database import get_db
from app.errors import register_exception_handlers
from app.job_search.crawl_runner import run_crawl
from app.job_search.daily_search import run_daily_search
from app.observability import init_sentry
from app.routers import (
    access_requests,
    admin,
    applications,
    auth,
    candidate_profile,
    dashboard,
    diagnostics,
    feedback,
    generation_jobs,
    interview_prep,
    interviews,
    job_search,
    personalization,
    saved_jobs,
)

settings = get_settings()

# No-op unless GLITCHTIP_DSN is set (so tests / dev are unaffected).
init_sentry()


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

    # Promote any account whose email is listed in ADMIN_EMAILS. Guarded so a
    # bootstrap hiccup never blocks startup. get_settings() is re-read (not the
    # module-level `settings`) so the test suite's env overrides take effect.
    if get_settings().admin_email_set:
        from app.auth.admin_bootstrap import promote_configured_admins

        try:
            with database.SessionLocal() as bootstrap_db:
                promote_configured_admins(bootstrap_db, get_settings().admin_email_set)
        except Exception:  # pragma: no cover - defensive
            logging.getLogger(__name__).exception("admin bootstrap failed")

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
    scheduler.add_job(
        # Same lookup-at-call-time convention as the jobs above so the test
        # suite's monkeypatch of database.SessionLocal takes effect.
        lambda: run_crawl(database.SessionLocal),
        trigger="interval",
        hours=settings.crawl_interval_hours,
        id="crawl",
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
app.include_router(admin.router)
app.include_router(applications.router)
app.include_router(diagnostics.router)
app.include_router(personalization.router)
app.include_router(candidate_profile.router)
app.include_router(job_search.router)
app.include_router(saved_jobs.router)
app.include_router(generation_jobs.router)
app.include_router(interview_prep.router)
app.include_router(interviews.router)
app.include_router(dashboard.router)
app.include_router(feedback.router)
app.include_router(access_requests.router)

register_exception_handlers(app)


APP_VERSION = "beta"


def _probe_db(db: Session) -> None:
    db.execute(text("SELECT 1"))


@app.get("/health")
def health(response: Response, db: Session = Depends(get_db)) -> dict[str, str | None]:
    try:
        _probe_db(db)
        return {"status": "ok", "db": "ok", "version": APP_VERSION}
    except Exception:  # noqa: BLE001 - a health probe must never propagate
        response.status_code = 503
        return {"status": "degraded", "db": "error", "version": APP_VERSION}
