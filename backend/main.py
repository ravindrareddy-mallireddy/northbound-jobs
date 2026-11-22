from pathlib import Path

import db
import sources
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE = Path(__file__).resolve().parent

db.init()

app = FastAPI(title="Northbound jobs API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/jobs")
def list_jobs(
    q: str = Query(default="", description="Free-text search over title, company, place and tags"),
    type: str = Query(default="", pattern="^(|Full-time|Contract|Part-time)$"),
    work: str = Query(default="", pattern="^(|Remote|Hybrid|On-site)$"),
    dept: str = Query(default="", pattern="^(|Design|Engineering|Product)$"),
    country: str = Query(default="", max_length=60),
    level: str = Query(default="", pattern="^(|Junior|Mid|Senior|Lead)$"),
    salary_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=10, le=200),
):
    total, jobs = db.query(q, type, work, dept, country, level, salary_only, page, per_page)
    return {"count": total, "page": page, "per_page": per_page, "jobs": jobs}


@app.get("/api/filters")
def filters():
    """Filter options with counts, so the UI shows only values that exist."""
    return db.filters_meta()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No such job")
    return job


@app.post("/api/jobs/refresh")
def refresh():
    report = sources.refresh_all()
    return report


# Serve the built frontend when it exists (npm run build first).
DIST = BASE.parent / "frontend" / "dist"
if (DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(DIST / "index.html")
