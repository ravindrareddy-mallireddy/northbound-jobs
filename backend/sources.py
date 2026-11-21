"""Job feed adapters: Remotive, Arbeitnow and Jobicy (all keyless).

Each adapter returns a list of normalized dicts matching the Job schema.
Fetches are bounded and identified; a failing source never breaks the others.
"""
import json
import re
import time
import urllib.request
import urllib.error
from html import unescape

USER_AGENT = "NorthboundJobsBoard/1.0 (contact: hello@northbound.example)"


def _get(url: str, tries: int = 2) -> dict | list:
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as res:
                return json.loads(res.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(2)
    raise RuntimeError(f"fetch failed: {url} ({last})")


def _strip_html(text: str, limit: int = 600) -> str:
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def _dept(title: str, desc: str) -> str:
    t = f"{title} {desc[:200]}".lower()
    if any(w in t for w in ("design", " ux ", "ui/", "brand", "illustrat", "type designer", "creative")):
        return "Design"
    if any(w in t for w in ("product manager", "product owner", "head of product", "product lead")):
        return "Product"
    return "Engineering"


def _s(value) -> str:
    """Coerce feed fields that are sometimes lists or None into a string."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value if isinstance(v, str))
    return "" if value is None else str(value)


def _norm_type(raw) -> str:
    r = _s(raw).lower()
    if "contract" in r or "freelance" in r:
        return "Contract"
    if "part" in r:
        return "Part-time"
    return "Full-time"


def fetch_remotive() -> list[dict]:
    data = _get("https://remotive.com/api/remote-jobs?limit=50")
    jobs = []
    for j in data.get("jobs", []):
        desc = _strip_html(j.get("description", ""))
        jobs.append({
            "title": j.get("title", "").strip(),
            "co": j.get("company_name", "").strip(),
            "place": j.get("candidate_required_location", "") or "Remote",
            "work": "Remote",
            "type": _norm_type(j.get("job_type", "")),
            "dept": _dept(j.get("title", ""), desc),
            "sal": (j.get("salary") or "Not listed").strip(),
            "desc": desc,
            "tags": [t for t in (j.get("tags") or []) if isinstance(t, str)][:3],
            "url": j.get("url", ""),
            "ext_id": str(j.get("id", j.get("url", ""))),
        })
    return jobs


def fetch_arbeitnow() -> list[dict]:
    data = _get("https://www.arbeitnow.com/api/job-board-api")
    jobs = []
    for j in data.get("data", [])[:100]:
        desc = _strip_html(j.get("description", ""))
        types = j.get("job_types") or []
        raw = types[0] if types else ""
        remote = bool(j.get("remote"))
        jobs.append({
            "title": j.get("title", "").strip(),
            "co": j.get("company_name", "").strip(),
            "place": (j.get("location") or "").strip() or ("Remote" if remote else "Germany"),
            "work": "Remote" if remote else "On-site",
            "type": _norm_type(raw),
            "dept": _dept(j.get("title", ""), desc),
            "sal": "Not listed",
            "desc": desc,
            "tags": [t for t in types if t != raw][:3],
            "url": j.get("url", ""),
            "ext_id": j.get("slug", j.get("url", "")),
        })
    return jobs


def fetch_jobicy() -> list[dict]:
    data = _get("https://jobicy.com/api/v2/remote-jobs?count=50&industry=dev")
    jobs = []
    for j in data.get("jobs", []):
        desc = _strip_html(_s(j.get("jobDescription")) or _s(j.get("jobExcerpt")))
        geo = _s(j.get("jobGeo")) or "Remote"
        sal = _s(j.get("jobSalary")) or "Not listed"
        level = _s(j.get("jobLevel")).title()
        company = j.get("companyName")
        co = _s(company.get("name") if isinstance(company, dict) else company).strip()
        jobs.append({
            "title": _s(j.get("jobTitle")).strip(),
            "co": co,
            "place": geo,
            "work": "Remote",
            "type": _norm_type(j.get("jobType")),
            "dept": _dept(_s(j.get("jobTitle")), desc),
            "sal": sal.strip(),
            "desc": desc,
            "tags": [t for t in (j.get("jobTags") or []) if isinstance(t, str)][:3] or ([level] if level else []),
            "url": _s(j.get("url")),
            "ext_id": _s(j.get("id")) or _s(j.get("url")),
        })
    return jobs


SOURCES = {
    "remotive": fetch_remotive,
    "arbeitnow": fetch_arbeitnow,
    "jobicy": fetch_jobicy,
}


def refresh_all() -> dict:
    """Pull every source. Returns a per-source report."""
    import db

    report = {}
    for name, fn in SOURCES.items():
        try:
            jobs = fn()
        except Exception as e:  # one source failing never blocks the rest
            report[name] = {"ok": False, "error": str(e)[:200], "new": 0, "seen": 0}
            continue
        new = 0
        live = []
        for job in jobs:
            if not job["title"] or not job["co"]:
                continue
            ext = job.pop("ext_id")
            live.append(ext)
            if db.upsert(name, ext, job):
                new += 1
        db.expire_missing(name, live)
        report[name] = {"ok": True, "new": new, "seen": len(live)}
    return report
