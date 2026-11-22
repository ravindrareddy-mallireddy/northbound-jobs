import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchJobs, type Job } from "./api";

type Filters = { q: string; type: string; place: string; dept: string };

const EMPTY: Filters = { q: "", type: "", place: "", dept: "" };
const PAGE_SIZE = 50;

const TYPES = ["", "Full-time", "Contract"];
const PLACES = ["", "Remote", "On-site"];
const DEPTS = ["", "Design", "Engineering", "Product"];

function labelOf(value: string, all: string) {
  return value || all;
}

export default function App() {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [count, setCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchJobs(filters, 1)
      .then((res) => {
        if (!alive) return;
        setJobs(res.jobs);
        setCount(res.count);
        setError(null);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setError(e instanceof Error ? e.message : "Could not reach the jobs API");
      });
    return () => {
      alive = false;
    };
  }, [filters]);

  const loadMore = useCallback(async () => {
    setLoadingMore(true);
    try {
      const res = await fetchJobs(filters, Math.floor(jobs.length / PAGE_SIZE) + 1);
      setJobs((prev) => {
        const seen = new Set(prev.map((j) => `${j.source}:${j.title}:${j.co}`));
        return [...prev, ...res.jobs.filter((j) => !seen.has(`${j.source}:${j.title}:${j.co}`))];
      });
      setCount(res.count);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not reach the jobs API");
    } finally {
      setLoadingMore(false);
    }
  }, [filters, jobs.length]);

  const set = useCallback((patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setOpenIndex(null);
  }, []);

  const companies = useMemo(
    () => [...new Set(jobs.map((j) => j.co))].join(", "),
    [jobs]
  );

  const active =
    filters.q !== "" || filters.type !== "" || filters.place !== "" || filters.dept !== "";

  return (
    <>
      <a className="skip" href="#jobs">Skip to the listings</a>

      <header className="site">
        <div className="wrap nav">
          <a className="wordmark" href="/">
            <span className="glyph" aria-hidden="true" />
            Northbound
          </a>
          <nav className="nav-links" aria-label="Main">
            <a href="#jobs">Browse roles</a>
            <a href="#about">About</a>
            <a className="post" href="mailto:post@northbound.example">Post a role</a>
          </nav>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="wrap">
            <h1>Senior roles at studios and product teams, <em>listed plainly.</em></h1>
            <p className="lede">
              Northbound collects design and engineering positions from independent
              studios and product companies across Europe. Every listing states its
              salary and its team.
            </p>
            <form
              className="searchbar"
              role="search"
              onSubmit={(e) => e.preventDefault()}
            >
              <label className="skip" htmlFor="q">Search roles</label>
              <input
                id="q"
                type="search"
                placeholder="Design systems, Rust, Copenhagen"
                autoComplete="off"
                value={filters.q}
                onChange={(e) => set({ q: e.target.value })}
              />
              <button type="submit">Search</button>
            </form>
          </div>
        </section>

        <div className="wrap" id="jobs">
          <div className="filters" role="group" aria-label="Filters">
            <span className="label">Type</span>
            {TYPES.map((t) => (
              <button
                key={t || "all-type"}
                className="chip"
                aria-pressed={filters.type === t}
                onClick={() => set({ type: t })}
              >
                {labelOf(t, "All")}
              </button>
            ))}
            <span className="label" style={{ marginLeft: 14 }}>Place</span>
            {PLACES.map((p) => (
              <button
                key={p || "all-place"}
                className="chip"
                aria-pressed={filters.place === p}
                onClick={() => set({ place: p })}
              >
                {labelOf(p, "Anywhere")}
              </button>
            ))}
            <label className="skip" htmlFor="dept">Department</label>
            <select
              id="dept"
              value={filters.dept}
              onChange={(e) => set({ dept: e.target.value })}
            >
              {DEPTS.map((d) => (
                <option key={d || "all"} value={d}>
                  {d ? d : "Every department"}
                </option>
              ))}
            </select>
          </div>

          <div className="meta-row">
            <p className="count">
              <strong>{count} role{count === 1 ? "" : "s"}</strong> open
            </p>
            {active && (
              <button className="clear" type="button" onClick={() => set(EMPTY)}>
                Clear filters
              </button>
            )}
          </div>

          {error && (
            <p className="error">
              {error}. Start the FastAPI backend on port 8734 and reload.
            </p>
          )}

          <ul className="jobs">
            {jobs.map((job, i) => (
              <li key={job.title + job.co} className={openIndex === i ? "job open" : "job"}>
                <button
                  className="job-head"
                  aria-expanded={openIndex === i}
                  onClick={() => setOpenIndex(openIndex === i ? null : i)}
                >
                  <span className="job-title">{job.title}</span>
                  <span className="job-sal">{job.sal}</span>
                  <span className="job-sub">
                    <span className="co">{job.co}</span> · {job.place} · {job.type}
                  </span>
                  <span className="job-flags">{job.work}</span>
                </button>
                {openIndex === i && (
                  <div className="job-detail">
                    <p>{job.desc}</p>
                    <div className="tags">
                      {job.tags.map((t) => (
                        <span key={t} className="tag">{t}</span>
                      ))}
                    </div>
                    {job.url ? (
                      <a className="apply" href={job.url} target="_blank" rel="noreferrer">
                        View the listing
                      </a>
                    ) : (
                      <a
                        className="apply"
                        href={`mailto:jobs@${job.co.toLowerCase().replace(/[^a-z]/g, "")}.example?subject=${encodeURIComponent(
                          job.title + " at " + job.co
                        )}`}
                      >
                        Apply to {job.co}
                      </a>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>

          {!error && jobs.length === 0 && (
            <div className="empty">
              <strong>Nothing matches yet.</strong>
              Try a broader search, or clear the filters to see all roles.
            </div>
          )}

          {!error && jobs.length < count && (
            <div className="more-row">
              <button className="more" type="button" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? "Loading" : `Show more (${jobs.length} of ${count})`}
              </button>
            </div>
          )}
        </div>

        <section className="band" id="about">
          <div className="wrap">
            <h2>About Northbound</h2>
            <p>
              Northbound is an independent job board. Listings are pulled from
              public job feeds: Remotive, Arbeitnow and Jobicy, refreshed
              every few hours. Salaries appear as their sources publish them, and
              every listing links back to the original post.
            </p>
            {companies && <p className="names">Currently hiring: <span aria-hidden="true">, </span>{companies}</p>}
          </div>
        </section>
      </main>

      <footer className="site wrap">
        <p>Listings from Remotive, Arbeitnow and Jobicy.</p>
        <p><a href="mailto:hello@northbound.example">hello@northbound.example</a></p>
      </footer>
    </>
  );
}
