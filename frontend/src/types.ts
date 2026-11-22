export type Job = {
  id?: number;
  source?: string;
  title: string;
  co: string;
  place: string;
  work: string;
  type: string;
  dept: "Design" | "Engineering" | "Product";
  sal: string;
  desc: string;
  tags: string[];
  url?: string;
};

export type JobsResponse = {
  count: number;
  page: number;
  per_page: number;
  jobs: Job[];
};
