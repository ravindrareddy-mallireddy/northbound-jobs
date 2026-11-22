"""Postgres storage for job listings. Connection settings come from .env."""
import json
import os
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "jobs.db"  # legacy SQLite, used only by the one-off migration
SEED_FILE = BASE / "jobs.json"


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is not None:
        return value
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return default


CONN_KW = dict(
    host=_env("PGHOST", "127.0.0.1"),
    port=int(_env("PGPORT", "5432")),
    user=_env("PGUSER", "northbound"),
    dbname=_env("PGDATABASE", "northbound"),
    password=_env("PGPASSWORD"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id BIGSERIAL PRIMARY KEY,
  source TEXT NOT NULL,
  ext_id TEXT NOT NULL,
  title TEXT NOT NULL,
  co TEXT NOT NULL,
  place TEXT NOT NULL,
  work TEXT NOT NULL,
  type TEXT NOT NULL,
  dept TEXT NOT NULL,
  sal TEXT NOT NULL,
  "desc" TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '[]',
  url TEXT NOT NULL DEFAULT '',
  first_seen BIGINT NOT NULL,
  last_seen BIGINT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE(source, ext_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(active);
"""

_COLS = "id, source, title, co, place, work, type, dept, sal, \"desc\", tags, url"


def _connect():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(**CONN_KW, row_factory=dict_row)


def _sample_jobs():
    if not SEED_FILE.exists():
        return []
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def init():
    con = _connect()
    con.execute(SCHEMA)
    if con.execute("SELECT COUNT(*) AS total FROM jobs").fetchone()["total"] == 0:
        now = int(time.time())
        for job in _sample_jobs():
            con.execute(
                "INSERT INTO jobs (source, ext_id, title, co, place, work, type, dept, sal, \"desc\", tags, url, first_seen, last_seen, active)"
                " VALUES (%(source)s, %(ext_id)s, %(title)s, %(co)s, %(place)s, %(work)s, %(type)s, %(dept)s, %(sal)s, %(desc)s, %(tags)s, %(url)s, %(now)s, %(now)s, TRUE)",
                {
                    "source": "sample",
                    "ext_id": job["title"].lower().replace(" ", "-")[:60],
                    "title": job["title"], "co": job["co"], "place": job["place"],
                    "work": job["work"], "type": job["type"], "dept": job["dept"],
                    "sal": job["sal"], "desc": job["desc"],
                    "tags": json.dumps(job["tags"]), "url": "", "now": now,
                },
            )
    con.commit()
    con.close()


def upsert(source: str, ext_id: str, job: dict) -> bool:
    """Insert or refresh one listing. Returns True when it is new."""
    con = _connect()
    now = int(time.time())
    try:
        con.execute(
            "INSERT INTO jobs (source, ext_id, title, co, place, work, type, dept, sal, \"desc\", tags, url, first_seen, last_seen, active)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)",
            (
                source, ext_id, job["title"], job["co"], job["place"], job["work"],
                job["type"], job["dept"], job["sal"], job["desc"],
                json.dumps(job["tags"]), job.get("url", ""), now, now,
            ),
        )
        con.commit()
        return True
    except Exception as e:
        if getattr(e, "sqlstate", "") != "23505":  # unique_violation
            raise
        con.rollback()
        con.execute(
            "UPDATE jobs SET title=%s, co=%s, place=%s, work=%s, type=%s, dept=%s, sal=%s, \"desc\"=%s, tags=%s, url=%s, last_seen=%s, active=TRUE"
            " WHERE source=%s AND ext_id=%s",
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
    if not live_ids:
        return
    con = _connect()
    marks = ",".join("%s" for _ in live_ids)
    cutoff = int(time.time()) - GRACE_DAYS * 86400
    con.execute(
        f"UPDATE jobs SET active=FALSE WHERE source=%s AND last_seen < %s AND ext_id NOT IN ({marks})",
        [source, cutoff, *live_ids],
    )
    con.commit()
    con.close()


def query(q: str, job_type: str, place: str, dept: str, page: int = 1, per_page: int = 50):
    """Return (total matching, one page of listings) ordered newest first."""
    con = _connect()
    clauses, params = ["active=TRUE"], []
    if job_type:
        clauses.append("type=%s")
        params.append(job_type)
    if place:
        clauses.append("work=%s")
        params.append(place)
    if dept:
        clauses.append("dept=%s")
        params.append(dept)
    if q:
        words = q.lower().split()
        for w in words:
            clauses.append("(lower(title) LIKE %s OR lower(co) LIKE %s OR lower(place) LIKE %s OR lower(tags) LIKE %s)")
            like = f"%{w}%"
            params.extend([like, like, like, like])
    where = " WHERE " + " AND ".join(clauses)
    total = con.execute("SELECT COUNT(*) AS total FROM jobs" + where, params).fetchone()["total"]
    rows = con.execute(
        "SELECT " + _COLS +
        " FROM jobs" + where + " ORDER BY last_seen DESC LIMIT %s OFFSET %s",
        params + [per_page, (page - 1) * per_page],
    ).fetchall()
    con.close()
    jobs = []
    for r in rows:
        j = dict(r)
        j["tags"] = json.loads(j["tags"])
        jobs.append(j)
    return total, jobs


def get_job(job_id: int):
    con = _connect()
    row = con.execute(
        "SELECT " + _COLS + " FROM jobs WHERE id=%s AND active=TRUE",
        (job_id,),
    ).fetchone()
    con.close()
    if row is None:
        return None
    j = dict(row)
    j["tags"] = json.loads(j["tags"])
    return j
