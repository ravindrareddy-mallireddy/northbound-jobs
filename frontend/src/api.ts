import type { Job, JobsResponse } from "./types";

export type { Job, JobsResponse };

export type Filters = { q: string; type: string; place: string; dept: string };

export async function fetchJobs(
  filters: Filters,
  page: number,
  perPage = 50
): Promise<JobsResponse> {
  const url = new URL("/api/jobs", window.location.origin);
  if (filters.q) url.searchParams.set("q", filters.q);
  if (filters.type) url.searchParams.set("type", filters.type);
  if (filters.place) url.searchParams.set("place", filters.place);
  if (filters.dept) url.searchParams.set("dept", filters.dept);
  url.searchParams.set("page", String(page));
  url.searchParams.set("per_page", String(perPage));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}
