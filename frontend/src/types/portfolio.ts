export type SkillLevel = "beginner" | "intermediate" | "advanced" | "expert";

export interface SkillDraft {
  name: string;
  canonical_name?: string | null;
  category: string;
  level: SkillLevel;
  confidence: number;
}

export type ProjectStatus = "planned" | "in_progress" | "finished";

export interface Project {
  id: string;
  title: string;
  description: string;
  tech_stack: string[];
  start_date: string;
  end_date?: string | null;
  media_urls?: string[];
  seniority?: string | null;
  achievements?: string[];
  skills?: SkillDraft[];
  status?: ProjectStatus;
}

export interface ProjectDraft {
  title: string;
  description: string;
  skills: SkillDraft[];
  tech_stack: string[];
  start_date?: string | null;
  end_date?: string | null;
  media_urls: string[];
  achievements: string[];
  seniority?: string | null;
  source: "form" | "upload";
}
