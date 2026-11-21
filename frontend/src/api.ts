import type { Job, JobsResponse } from "./types";

export type { Job, JobsResponse };

export type Filters = { q: string; type: string; place: string; dept: string };

export async function fetchJobs(filters: Filters): Promise<JobsResponse> {
  const url = new URL("/api/jobs", window.location.origin);
  for (const [k, v] of Object.entries(filters)) {
    if (v) url.searchParams.set(k, v);
  }
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return res.json();
  } catch {
    return { count: 0, jobs: [] };
  }
}
