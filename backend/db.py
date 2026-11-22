"""SQLite storage for job listings, seeded from jobs.json if present."""
import json
import sqlite3
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "jobs.db"
SEED_FILE = BASE / "jobs.json"


def _sample_jobs():
    if not SEED_FILE.exists():
        return []
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  ext_id TEXT NOT NULL,
  title TEXT NOT NULL,
  co TEXT NOT NULL,
  place TEXT NOT NULL,
  work TEXT NOT NULL,
  type TEXT NOT NULL,
  dept TEXT NOT NULL,
  sal TEXT NOT NULL,
  desc TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '[]',
  url TEXT NOT NULL DEFAULT '',
  first_seen INTEGER NOT NULL,
  last_seen INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  UNIQUE(source, ext_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(active);
"""


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init():
    con = connect()
    con.executescript(SCHEMA)
    if con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0:
        now = int(time.time())
        for job in _sample_jobs():
            con.execute(
                "INSERT INTO jobs (source, ext_id, title, co, place, work, type, dept, sal, desc, tags, url, first_seen, last_seen, active)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                (
                    "sample", job["title"].lower().replace(" ", "-")[:60],
                    job["title"], job["co"], job["place"], job["work"], job["type"],
                    job["dept"], job["sal"], job["desc"], json.dumps(job["tags"]), "",
                    now, now,
                ),
            )
        con.commit()
    con.close()


def upsert(source: str, ext_id: str, job: dict) -> bool:
    """Insert or refresh one listing. Returns True when it is new."""
    con = connect()
    now = int(time.time())
    try:
        con.execute(
            "INSERT INTO jobs (source, ext_id, title, co, place, work, type, dept, sal, desc, tags, url, first_seen, last_seen, active)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
            (
                source, ext_id, job["title"], job["co"], job["place"], job["work"],
                job["type"], job["dept"], job["sal"], job["desc"],
                json.dumps(job["tags"]), job.get("url", ""), now, now,
            ),
        )
        con.commit()
        return True
    except sqlite3.IntegrityError:
        con.execute(
            "UPDATE jobs SET title=?, co=?, place=?, work=?, type=?, dept=?, sal=?, desc=?, tags=?, url=?, last_seen=?, active=1"
            " WHERE source=? AND ext_id=?",
            (
                job["title"], job["co"], job["place"], job["work"], job["type"],
                job["dept"], job["sal"], job["desc"], json.dumps(job["tags"]),
                job.get("url", ""), now, source, ext_id,
            ),
        )
        con.commit()
        return False
    finally:
        con.close()


GRACE_DAYS = 7


def expire_missing(source: str, live_ids: list[str]):
    """Mark a source's listings inactive only once they have been off its
    feed for GRACE_DAYS; fresh listings that merely fell off the page stay."""
    con = connect()
    marks = ",".join("?" for _ in live_ids)
    cutoff = int(time.time()) - GRACE_DAYS * 86400
    con.execute(
        f"UPDATE jobs SET active=0 WHERE source=? AND last_seen < ? AND ext_id NOT IN ({marks})",
        [source, cutoff, *live_ids],
    )
    con.commit()
    con.close()


def query(q: str, job_type: str, place: str, dept: str, page: int = 1, per_page: int = 50):
    """Return (total matching, one page of listings) ordered newest first."""
    con = connect()
    clauses, params = ["active=1"], []
    if job_type:
        clauses.append("type=?")
        params.append(job_type)
    if place:
        clauses.append("work=?")
        params.append(place)
    if dept:
        clauses.append("dept=?")
        params.append(dept)
    if q:
        words = q.lower().split()
        for w in words:
            clauses.append("(lower(title) LIKE ? OR lower(co) LIKE ? OR lower(place) LIKE ? OR lower(tags) LIKE ?)")
            like = f"%{w}%"
            params.extend([like, like, like, like])
    where = " WHERE " + " AND ".join(clauses)
    total = con.execute("SELECT COUNT(*) FROM jobs" + where, params).fetchone()[0]
    rows = con.execute(
        "SELECT id, source, title, co, place, work, type, dept, sal, desc, tags, url"
        " FROM jobs" + where + " ORDER BY last_seen DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page],
    ).fetchall()
    con.close()
    jobs = []
    for r in rows:
        j = dict(r)
        j["tags"] = json.loads(j["tags"])
        jobs.append(j)
    return total, jobs
