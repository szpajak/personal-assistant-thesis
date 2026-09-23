export interface JobOffer {
  id: string;
  title: string;
  company: string;
  url: string;
  description: string;
  required_skills: string[];
  scraped_at: string;
  /** staging = scraped listing; career = saved into the personal KG */
  tier?: 'staging' | 'career';
  location?: string;
  salary_range?: string | null;
  job_type?: string | null;
  source?: string | null;
  seniority?: string | null;
  min_experience_years?: number | null;
  max_experience_years?: number | null;
}

export type ExperienceBracket = '0-2' | '2-5' | '5+';
export type SeniorityFilter = 'junior' | 'mid' | 'senior';
export type MatchSource = 'overlap' | 'llm' | 'none';

export interface ScrapedJobFilters {
  search?: string;
  source?: string;
  seniority?: SeniorityFilter | '';
  experience_bracket?: ExperienceBracket | '';
}

export interface JobMatch {
  job_offer: JobOffer;
  score: number;
  matching_skills?: string[];
  missing_skills?: string[];
  justification?: string;
  quick_score?: number;
  is_stale?: boolean;
  matched_at?: string | null;
  source?: MatchSource;
}

export interface JobPromoteResponse {
  job_offer: JobOffer;
  promoted: boolean;
}
