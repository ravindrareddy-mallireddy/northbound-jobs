# Northbound

A job board for senior design and engineering roles at European studios and
product teams. React 19 + TypeScript frontend (Vite), FastAPI backend, and a
scraper that pulls listings from the keyless public job feeds Remotive,
Arbeitnow and Jobicy.

## Run it

Backend (Python 3.12+, PostgreSQL 16 on localhost):

    cd backend
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    # put PGHOST/PGPORT/PGUSER/PGDATABASE/PGPASSWORD in backend/.env
    .venv/bin/uvicorn main:app --port 8734

Frontend (Node 22+):

    cd frontend
    npm install
    npm run dev        # dev server on 5173, proxies /api to the backend
    npm run build      # production build in dist/, served by the backend

The backend serves the built frontend from `dist/` on `/`.

## How it works

- `backend/sources.py` fetches and normalizes each feed; one failing source
  never blocks the others.
- `backend/db.py` stores listings in PostgreSQL, deduped per source,
  with listings expiring when they leave a feed for a week.
- `POST /api/jobs/refresh` pulls all sources; schedule it every few hours.
- `GET /api/jobs` supports keyword search plus type, place and department
  filters.

## Data notes

- Listings belong to their sources; each links back to the original post.
- `frontend/src/jobs.json` is a generated offline fallback for sandboxed
  previews. Regenerate it from a running backend with:

      curl -s http://127.0.0.1:8734/api/jobs > /tmp/jobs.json
      # then keep the "jobs" array of that response as src/jobs.json

Salaries appear as their sources publish them; jobs without a published
salary show "Not listed".
