# ATS Diagnostic — Backend

## Setup

1. `python -m venv venv && source venv/bin/activate`
2. `pip install -r requirements-dev.txt`
3. Copy `.env.example` to `.env` and fill in `JWT_SECRET`, `ANTHROPIC_API_KEY`, and `DATABASE_URL` (PostgreSQL in production; a local SQLite file works for manual testing).
4. `uvicorn app.main:app --reload`
5. Open `http://localhost:8000/docs` for the interactive API documentation.

## Tests

`pytest`
