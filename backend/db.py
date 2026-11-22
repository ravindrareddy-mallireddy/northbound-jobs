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
  country TEXT NOT NULL DEFAULT '',
  level TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]',
  url TEXT NOT NULL DEFAULT '',
  first_seen BIGINT NOT NULL,
  last_seen BIGINT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE(source, ext_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(active);
"""

_COLS = "id, source, title, co, place, work, type, dept, sal, \"desc\", country, level, tags, url"


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
    con.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS country TEXT NOT NULL DEFAULT ''")
    con.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS level TEXT NOT NULL DEFAULT ''")
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
    backfill_derived()


def upsert(source: str, ext_id: str, job: dict) -> bool:
    """Insert or refresh one listing. Returns True when it is new."""
    con = _connect()
    now = int(time.time())
    try:
        con.execute(
            "INSERT INTO jobs (source, ext_id, title, co, place, work, type, dept, sal, \"desc\", country, level, tags, url, first_seen, last_seen, active)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)",
            (
                source, ext_id, job["title"], job["co"], job["place"],
                derive_work(job["work"], job["desc"]),
                job["type"], job["dept"], job["sal"], job["desc"],
                derive_country(job["place"]), derive_level(job["title"]),
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
            "UPDATE jobs SET title=%s, co=%s, place=%s, work=%s, type=%s, dept=%s, sal=%s, \"desc\"=%s, country=%s, level=%s, tags=%s, url=%s, last_seen=%s, active=TRUE"
            " WHERE source=%s AND ext_id=%s",
            (
                job["title"], job["co"], job["place"],
                derive_work(job["work"], job["desc"]), job["type"],
                job["dept"], job["sal"], job["desc"],
                derive_country(job["place"]), derive_level(job["title"]),
                json.dumps(job["tags"]), job.get("url", ""), now, source, ext_id,
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


def query(q: str, job_type: str, work: str, dept: str, country: str = "", level: str = "",
          salary_only: bool = False, page: int = 1, per_page: int = 50):
    """Return (total matching, one page of listings) ordered newest first."""
    con = _connect()
    clauses, params = ["active=TRUE"], []
    if job_type:
        clauses.append("type=%s")
        params.append(job_type)
    if work:
        clauses.append("work=%s")
        params.append(work)
    if dept:
        clauses.append("dept=%s")
        params.append(dept)
    if country:
        clauses.append("country=%s")
        params.append(country)
    if level:
        clauses.append("level=%s")
        params.append(level)
    if salary_only:
        clauses.append("sal IS NOT NULL AND sal <> '' AND lower(sal) <> 'not listed'")
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


# --- derived fields: country and experience level -------------------------

_COUNTRY_HINTS = [
    (("united states", "usa", "u.s.", " us,", "us only", "america"), "United States"),
    (("united kingdom", "uk", "england", "scotland", "wales", "london", "leeds", "manchester", "bristol", "edinburgh"), "United Kingdom"),
    (("germany", "berlin", "munich", "hamburg", "cologne", "frankfurt", "stuttgart"), "Germany"),
    (("poland", "warsaw", "krakow", "wroclaw", "gdansk"), "Poland"),
    (("portugal", "lisbon", "porto"), "Portugal"),
    (("denmark", "copenhagen"), "Denmark"),
    (("norway", "oslo"), "Norway"),
    (("sweden", "stockholm"), "Sweden"),
    (("switzerland", "basel", "zurich", "geneva"), "Switzerland"),
    (("netherlands", "amsterdam", "rotterdam"), "Netherlands"),
    (("spain", "madrid", "barcelona", "valencia"), "Spain"),
    (("france", "paris", "lyon"), "France"),
    (("ireland", "dublin"), "Ireland"),
    (("india", "bangalore", "bengaluru", "pune", "hyderabad", "mumbai", "delhi"), "India"),
    (("canada", "toronto", "vancouver", "montreal"), "Canada"),
    (("australia", "sydney", "melbourne"), "Australia"),
    (("brazil", "sao paulo"), "Brazil"),
    (("israel", "tel aviv"), "Israel"),
    (("japan", "tokyo"), "Japan"),
    (("singapore",), "Singapore"),
    (("europe", " eu", "emea", "european"), "Europe (remote)"),
    (("worldwide", "anywhere", "global", "remote"), "Worldwide"),
]


def derive_country(place: str) -> str:
    p = f" {place.lower()} "
    for hints, country in _COUNTRY_HINTS:
        if any(h in p for h in hints):
            return country
    cleaned = place.strip()
    return cleaned[:40] if cleaned and len(cleaned) <= 40 else "Other"


def derive_work(work: str, desc: str = "") -> str:
    """Hybrid is never declared by the feeds; infer it from the description."""
    if work == "Remote":
        return work
    if "hybrid" in (desc or "").lower()[:800]:
        return "Hybrid"
    return work


def derive_level(title: str, desc: str = "") -> str:
    t = f" {title.lower()} "
    if any(w in t for w in ("principal", "staff ", " lead", "head of", "director", "vp ", "chief")):
        return "Lead"
    if any(w in t for w in ("senior", "sr.", "sr ", "snr")):
        return "Senior"
    if any(w in t for w in ("junior", "jr ", "intern", "graduate", "entry level", "trainee")):
        return "Junior"
    return "Mid"


def backfill_derived():
    """Fill country and level for rows created before those columns existed."""
    con = _connect()
    rows = con.execute(
        "SELECT id, title, place, work, \"desc\" FROM jobs"
    ).fetchall()
    for r in rows:
        con.execute(
            "UPDATE jobs SET country=%s, level=%s, work=%s WHERE id=%s",
            (
                derive_country(r["place"] or ""),
                derive_level(r["title"] or ""),
                derive_work(r["work"] or "", r["desc"] or ""),
                r["id"],
            ),
        )
    con.commit()
    con.close()
    return len(rows)


def filters_meta() -> dict:
    """Distinct filter values with counts, for the filter controls."""
    con = _connect()
    def rows(sql):
        return [{"value": r["value"], "count": r["n"]} for r in con.execute(sql).fetchall()]
    out = {
        "works": rows("SELECT work AS value, COUNT(*) AS n FROM jobs WHERE active=TRUE GROUP BY work ORDER BY n DESC"),
        "types": rows("SELECT type AS value, COUNT(*) AS n FROM jobs WHERE active=TRUE GROUP BY type ORDER BY n DESC"),
        "depts": rows("SELECT dept AS value, COUNT(*) AS n FROM jobs WHERE active=TRUE GROUP BY dept ORDER BY n DESC"),
        "levels": rows("SELECT level AS value, COUNT(*) AS n FROM jobs WHERE active=TRUE AND level<>'' GROUP BY level ORDER BY n DESC"),
        "countries": rows("SELECT country AS value, COUNT(*) AS n FROM jobs WHERE active=TRUE AND country<>'' GROUP BY country ORDER BY n DESC LIMIT 40"),
        "salary_count": con.execute("SELECT COUNT(*) AS n FROM jobs WHERE active=TRUE AND lower(sal) <> 'not listed' AND sal <> ''").fetchone()["n"],
    }
    con.close()
    return out
