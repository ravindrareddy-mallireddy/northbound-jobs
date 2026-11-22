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
  country?: string;
  level?: string;
  tags: string[];
  url?: string;
};

export type JobsResponse = {
  count: number;
  page: number;
  per_page: number;
  jobs: Job[];
};

export type OptionCount = { value: string; count: number };

export type FiltersMeta = {
  works: OptionCount[];
  types: OptionCount[];
  depts: OptionCount[];
  levels: OptionCount[];
  countries: OptionCount[];
  salary_count: number;
};
