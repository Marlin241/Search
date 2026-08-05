# Diagnostic ATS — Frontend

## Setup

1. `npm install`
2. Copy `.env.local.example` to `.env.local` and adjust `NEXT_PUBLIC_API_URL` if the backend isn't running on `http://localhost:8000`.
3. Make sure the backend is running (see `../backend/README.md`) — CORS is already configured for `http://localhost:3000`.
4. `npm run dev`
5. Open `http://localhost:3000`.

## Tests

`npm test`

## Pages

- `/login` — sign in / register (single form, toggled mode)
- `/diagnostic` — upload a CV + job offer, see the diagnostic report
- `/historique` — past diagnostics, expandable inline, with a full-history purge option
- `/` — redirects to `/diagnostic` or `/login` depending on auth state
