import type { Job, JobsResponse, FiltersMeta } from "./types";

export type { Job, JobsResponse, FiltersMeta };

export type Filters = {
  q: string;
  type: string;
  work: string;
  dept: string;
  country: string;
  level: string;
  salaryOnly: boolean;
};

export async function fetchJobs(
  filters: Filters,
  page: number,
  perPage = 50
): Promise<JobsResponse> {
  const url = new URL("/api/jobs", window.location.origin);
  if (filters.q) url.searchParams.set("q", filters.q);
  if (filters.type) url.searchParams.set("type", filters.type);
  if (filters.work) url.searchParams.set("work", filters.work);
  if (filters.dept) url.searchParams.set("dept", filters.dept);
  if (filters.country) url.searchParams.set("country", filters.country);
  if (filters.level) url.searchParams.set("level", filters.level);
  if (filters.salaryOnly) url.searchParams.set("salary_only", "true");
  url.searchParams.set("page", String(page));
  url.searchParams.set("per_page", String(perPage));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

export async function fetchFilters(): Promise<FiltersMeta> {
  const res = await fetch(new URL("/api/filters", window.location.origin));
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}
