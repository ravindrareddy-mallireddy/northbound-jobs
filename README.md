# Northbound

A job board for senior design and engineering roles at European studios and
product teams. React 19 + TypeScript frontend (Vite), FastAPI backend, and a
scraper that pulls listings from the keyless public job feeds Remotive,
Arbeitnow and Jobicy.

## Run it

Backend (Python 3.12+):

    cd backend
    python3 -m venv .venv
    .venv/bin/pip install fastapi "uvicorn[standard]"
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
- `backend/db.py` stores listings in SQLite (`jobs.db`), deduped per source,
  with listings expiring when they leave a feed.
- `POST /api/jobs/refresh` pulls all sources; schedule it every few hours.
- `GET /api/jobs` supports keyword search plus type, place and department
  filters.

## Data notes

- Listings belong to their sources; each links back to the original post.
- `frontend/src/jobs.json` is a generated offline fallback for sandboxed
  previews, regenerated from a running backend; it is not committed.

Salaries appear as their sources publish them; jobs without a published
salary show "Not listed".
