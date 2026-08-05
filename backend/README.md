# ATS Diagnostic — Backend

## Setup

PostgreSQL is required — there is no SQLite fallback. Start one via the
repo-root `docker compose up -d db`, or point `DATABASE_URL` at any
PostgreSQL instance you already have running.

1. `python -m venv venv && source venv/bin/activate`
2. `pip install -r requirements-dev.txt`
3. Copy `.env.example` to `.env` and fill in `JWT_SECRET`, `ANTHROPIC_API_KEY`, and `DATABASE_URL`.
4. `uvicorn app.main:app --reload`
5. Open `http://localhost:8000/docs` for the interactive API documentation.

## Tests

`pytest` — no PostgreSQL needed for tests, they run against an isolated
in-memory SQLite database created per test.

## Docker

From the repo root: `docker compose up --build` runs PostgreSQL, this
backend, and the frontend together. See the root `docker-compose.yml`.
