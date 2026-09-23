export interface Employment {
  id: string;
  title: string;
  company: string;
  start_date: string;
  end_date?: string | null;
  description?: string;
  achievements?: string[];
  skills?: string[];
}

export interface EmploymentCreateInput {
  title: string;
  company: string;
  start_date: string;
  end_date?: string | null;
  description?: string;
  achievements?: string[];
  skills?: string[];
}

export interface Education {
  id: string;
  institution: string;
  degree: string;
  field_of_study?: string;
  start_date: string;
  end_date?: string | null;
  description?: string;
}

export interface EducationCreateInput {
  institution: string;
  degree: string;
  field_of_study?: string;
  start_date: string;
  end_date?: string | null;
  description?: string;
}

export type TargetRoleSampleStatus =
  | "idle"
  | "scraping"
  | "ingesting"
  | "ready"
  | "error";

export interface TargetRole {
  id: string;
  title: string;
  location: string;
  country: string;
  // Derived from the market sample - never set directly by the client.
  required_skills: string[];
  sample_status: TargetRoleSampleStatus;
  sample_job_count: number;
  last_sampled_at?: string | null;
}

export interface TargetRoleCreateInput {
  title: string;
  location?: string;
  country?: string;
}

export interface TargetRoleRefreshResponse {
  id: string;
  sample_status: TargetRoleSampleStatus;
  task_id?: string | null;
}

export interface ProfileSummary {
  total_years_experience: number;
  employment_count: number;
  education_count: number;
  target_role_count: number;
  current_title?: string | null;
  current_company?: string | null;
}

export interface PersonProfile {
  name: string;
  email: string;
  bio: string;
  phone: string;
  location: string;
  linkedin_url: string;
  github_url: string;
  website_url: string;
  languages_spoken: string;
  interests: string;
  awards: string[];
}

export interface PersonProfileUpdateInput {
  bio?: string;
  phone?: string;
  location?: string;
  linkedin_url?: string;
  github_url?: string;
  website_url?: string;
  languages_spoken?: string;
  interests?: string;
  awards?: string[];
}

export interface ProfileExtractResponse {
  employment: Array<{
    title: string;
    company: string;
    start_date?: string | null;
    end_date?: string | null;
    description?: string;
    achievements?: string[];
    skills?: string[];
  }>;
  education: Array<{
    institution: string;
    degree?: string;
    field_of_study?: string;
    start_date?: string | null;
    end_date?: string | null;
    description?: string;
  }>;
}
