import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowUpRight, ChevronDown, Mail, Monitor, Moon, Search, Sun } from "lucide-react";
import { fetchFilters, fetchJobs, type Filters, type FiltersMeta, type Job } from "./api";

type Theme = "auto" | "light" | "dark";

const THEMES: Theme[] = ["auto", "light", "dark"];
const PAGE_SIZES = [10, 25, 50, 100];

const EMPTY: Filters = {
  q: "",
  type: "",
  work: "",
  dept: "",
  country: "",
  level: "",
  salaryOnly: false,
};

const TYPES = ["", "Full-time", "Contract", "Part-time"];
const WORKS = ["", "Remote", "Hybrid", "On-site"];
const DEPTS = ["", "Design", "Engineering", "Product"];
const LEVELS = ["", "Junior", "Mid", "Senior", "Lead"];

function themeLabel(theme: Theme) {
  return theme === "auto" ? "Auto" : theme === "light" ? "Light" : "Dark";
}

function ThemeIcon({ theme }: { theme: Theme }) {
  const props = { size: 15, strokeWidth: 1.8, "aria-hidden": true } as const;
  if (theme === "light") return <Sun {...props} />;
  if (theme === "dark") return <Moon {...props} />;
  return <Monitor {...props} />;
}

function applyTheme(theme: Theme) {
  if (theme === "auto") {
    localStorage.removeItem("nb-theme");
    document.documentElement.removeAttribute("data-theme");
  } else {
    localStorage.setItem("nb-theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
  }
}

function labelOf(value: string, all: string) {
  return value || all;
}

const JobRow = memo(function JobRow({
  job,
  open,
  onToggle,
}: {
  job: Job;
  open: boolean;
  onToggle: () => void;
}) {
  const meta = [job.co, job.place, job.work, job.type].filter(Boolean).join(" · ");
  return (
    <li className={open ? "job open" : "job"}>
      <button className="job-head" aria-expanded={open} onClick={onToggle}>
        <span className="job-title">{job.title}</span>
        <span className="job-sal">{job.sal}</span>
        <span className="job-sub">{meta}</span>
        <span className="job-flags">
          {job.level && <span className="flag">{job.level}</span>}
          {job.country && <span className="flag">{job.country}</span>}
        </span>
        <ChevronDown className="job-chev" size={18} strokeWidth={1.8} aria-hidden="true" />
      </button>
      {open && (
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
              <ArrowUpRight size={16} strokeWidth={2} aria-hidden="true" />
            </a>
          ) : (
            <a
              className="apply"
              href={`mailto:jobs@${job.co.toLowerCase().replace(/[^a-z]/g, "")}.example?subject=${encodeURIComponent(
                job.title + " at " + job.co
              )}`}
            >
              Apply to {job.co}
              <ArrowUpRight size={16} strokeWidth={2} aria-hidden="true" />
            </a>
          )}
        </div>
      )}
    </li>
  );
});

export default function App() {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [meta, setMeta] = useState<FiltersMeta | null>(null);
  const [perPage, setPerPage] = useState(25);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [count, setCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("nb-theme");
    return THEMES.includes(saved as Theme) ? (saved as Theme) : "auto";
  });

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    fetchFilters().then(setMeta).catch(() => setMeta(null));
  }, []);

  useEffect(() => {
    let alive = true;
    const timer = setTimeout(() => {
      fetchJobs(filters, 1, perPage)
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
    }, 300);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [filters, perPage]);

  const loadMore = useCallback(async () => {
    setLoadingMore(true);
    try {
      const res = await fetchJobs(filters, Math.floor(jobs.length / perPage) + 1, perPage);
      setJobs((prev) => {
        const seen = new Set(prev.map((j) => j.id ?? `${j.source}:${j.title}:${j.co}`));
        return [
          ...prev,
          ...res.jobs.filter((j) => !seen.has(j.id ?? `${j.source}:${j.title}:${j.co}`)),
        ];
      });
      setCount(res.count);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not reach the jobs API");
    } finally {
      setLoadingMore(false);
    }
  }, [filters, jobs.length, perPage]);

  const set = useCallback((patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setOpenIndex(null);
  }, []);

  const companies = useMemo(
    () => [...new Set(jobs.map((j) => j.co))].slice(0, 8).join(", "),
    [jobs]
  );

  const active =
    filters.q !== "" ||
    filters.type !== "" ||
    filters.work !== "" ||
    filters.dept !== "" ||
    filters.country !== "" ||
    filters.level !== "" ||
    filters.salaryOnly;

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
          <button
            className="theme"
            type="button"
            aria-label={`Theme: ${themeLabel(theme)}. Switch theme.`}
            onClick={() => setTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length])}
          >
            <ThemeIcon theme={theme} />
            {themeLabel(theme)}
          </button>
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
              <button type="submit">
                <Search size={17} strokeWidth={2} aria-hidden="true" />
                Search
              </button>
            </form>
          </div>
        </section>

        <div className="wrap" id="jobs">
          <div className="filters" role="group" aria-label="Filters">
            <span className="label">Work</span>
            {WORKS.map((w) => (
              <button
                key={w || "all-work"}
                className="chip"
                aria-pressed={filters.work === w}
                onClick={() => set({ work: w })}
              >
                {labelOf(w, "Any mode")}
              </button>
            ))}

            <label className="skip" htmlFor="country">Country</label>
            <select
              id="country"
              className="filter-select"
              value={filters.country}
              onChange={(e) => set({ country: e.target.value })}
            >
              <option value="">Any country</option>
              {(meta?.countries ?? []).map((c) => (
                <option key={c.value} value={c.value}>
                  {c.value} ({c.count})
                </option>
              ))}
            </select>

            <label className="skip" htmlFor="level">Experience</label>
            <select
              id="level"
              className="filter-select"
              value={filters.level}
              onChange={(e) => set({ level: e.target.value })}
            >
              <option value="">Any experience</option>
              {LEVELS.filter(Boolean).map((l) => {
                const found = meta?.levels.find((m) => m.value === l);
                return (
                  <option key={l} value={l}>
                    {l} ({found ? found.count : 0})
                  </option>
                );
              })}
            </select>

            <label className="skip" htmlFor="dept">Department</label>
            <select
              id="dept"
              className="filter-select"
              value={filters.dept}
              onChange={(e) => set({ dept: e.target.value })}
            >
              {DEPTS.map((d) => (
                <option key={d || "all"} value={d}>
                  {d ? d : "Every department"}
                </option>
              ))}
            </select>

            <span className="label">Type</span>
            {TYPES.filter((t) => !t || meta?.types.some((m) => m.value === t)).map((t) => (
              <button
                key={t || "all-type"}
                className="chip"
                aria-pressed={filters.type === t}
                onClick={() => set({ type: t })}
              >
                {labelOf(t, "All")}
              </button>
            ))}

            <label className="check">
              <input
                type="checkbox"
                checked={filters.salaryOnly}
                onChange={(e) => set({ salaryOnly: e.target.checked })}
              />
              Salary listed
              {meta && <span className="check-count">{meta.salary_count}</span>}
            </label>

            <label className="perpage" htmlFor="perpage">
              Jobs per page
              <select
                id="perpage"
                value={perPage}
                onChange={(e) => setPerPage(Number(e.target.value))}
              >
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="meta-row">
            <p className="count" aria-live="polite">
              <strong>{count} role{count === 1 ? "" : "s"}</strong> open
            </p>
            <div className="meta-right">
              {active && (
                <button className="clear" type="button" onClick={() => set(EMPTY)}>
                  Clear filters
                </button>
              )}
            </div>
          </div>

          {error && (
            <p className="error" role="alert">
              {error}. Start the FastAPI backend on port 8734 and reload.
            </p>
          )}

          <ul className="jobs">
            {jobs.map((job, i) => (
              <JobRow
                key={job.id ?? `${job.source}:${job.title}:${job.co}`}
                job={job}
                open={openIndex === i}
                onToggle={() => setOpenIndex(openIndex === i ? null : i)}
              />
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
        <p>
          <a href="mailto:hello@northbound.example">
            <Mail size={15} strokeWidth={1.8} aria-hidden="true" />
            hello@northbound.example
          </a>
        </p>
      </footer>
    </>
  );
}
