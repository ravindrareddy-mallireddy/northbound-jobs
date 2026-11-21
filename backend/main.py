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
    place: str = Query(default="", pattern="^(|Remote|On-site)$"),
    dept: str = Query(default="", pattern="^(|Design|Engineering|Product)$"),
):
    jobs = db.query(q, type, place, dept)
    return {"count": len(jobs), "jobs": jobs}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int):
    con = db.connect()
    row = con.execute(
        "SELECT id, source, title, co, place, work, type, dept, sal, desc, tags, url FROM jobs WHERE id=? AND active=1",
        (job_id,),
    ).fetchone()
    con.close()
    if row is None:
        raise HTTPException(status_code=404, detail="No such job")
    job = dict(row)
    import json
    job["tags"] = json.loads(job["tags"])
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
