import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
# Only used to satisfy Settings() validation for the module-level app.database.engine,
# which SQLAlchemy builds lazily and never actually connects to during tests — every
# test uses the isolated in-memory SQLite engine from the db_session fixture below.
os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost/unused")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401 register all models on Base

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # The app's lifespan calls database.Base.metadata.create_all(bind=database.engine)
    # on startup. Point it at the same isolated in-memory engine db_session uses,
    # instead of the real (unreachable in tests) DATABASE_URL-configured engine.
    monkeypatch.setattr(database, "engine", db_session.get_bind())
    # Background tasks (e.g. app.job_search.background_discovery.run_discovery)
    # can't use the request-scoped db_session/override_get_db above — they run
    # after the response, via their own database.SessionLocal() call. Rebind it
    # to the same in-memory test engine (StaticPool keeps it on the same
    # underlying connection as db_session) so it doesn't try to reach the
    # unused DATABASE_URL from the environment.
    monkeypatch.setattr(
        database, "SessionLocal", sessionmaker(bind=db_session.get_bind())
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
