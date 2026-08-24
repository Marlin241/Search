# ATS Diagnostic — Backend

## Setup

PostgreSQL is required — there is no SQLite fallback. Start one via the
repo-root `docker compose up -d db`, or point `DATABASE_URL` at any
PostgreSQL instance you already have running.

1. `python -m venv venv && source venv/bin/activate`
2. `pip install -r requirements-dev.txt`
3. Copy `.env.example` to `.env` and fill in `JWT_SECRET`, `ANTHROPIC_API_KEY`, and `DATABASE_URL`.
4. `alembic upgrade head` — applies the database schema (see Migrations below).
5. `uvicorn app.main:app --reload`
6. Open `http://localhost:8000/docs` for the interactive API documentation.

## Migrations

Schema changes are managed with Alembic, not by hand. The app's own startup
also runs `Base.metadata.create_all(...)`, but that only ever creates
brand-new tables — it silently does nothing to a table that already exists,
even if its model gained a new column. Alembic is what actually evolves an
existing database.

- After changing a model, generate a migration: `alembic revision --autogenerate -m "add some_column"`.
- Read the generated file in `alembic/versions/` before committing it — autogenerate is a good first draft, not a guarantee.
- Apply pending migrations: `alembic upgrade head`.
- The Docker image runs `alembic upgrade head` automatically before starting the server (see `Dockerfile`).

## Tests

`pytest` — no PostgreSQL needed for tests, they run against an isolated
in-memory SQLite database created per test (via `create_all`, not migrations).

## Docker

From the repo root: `docker compose up --build` runs PostgreSQL, this
backend, and the frontend together. See the root `docker-compose.yml`.
