export interface Skill {
  id: string;
  name: string;
  category: string;
  level: string;
}

export interface SkillDemand {
  name: string;
  demand: number;
  is_owned: boolean;
}

export interface SuggestedProject {
  title: string;
  description: string;
  tech_stack: string[];
  skills_covered: string[];
  key_steps?: string[];
  deliverables?: string[];
}

export interface SuggestedProjectsCache {
  suggested_projects: SuggestedProject[];
  skills: string[];
  cached: boolean;
}

export interface SkillGap {
  skill: string;
  gap_reason: string;
  priority: "high" | "medium" | "low";
  kind: "missing" | "underleveled";
  current_level?: string | null;
  expected_level?: string | null;
  demand: number;
}

export interface SkillAnalysis {
  core_strengths: string[];
  skill_gaps: SkillGap[];
  target_role_ready: boolean;
  target_role_title?: string | null;
  sample_status?: string | null;
  sample_job_count: number;
  error?: string | null;
}

export interface LearningPhase {
  title: string;
  duration: string;
  goal: string;
  concepts: string[];
  steps: string[];
  project_title?: string | null;
}

export interface LearningRoadmap {
  overview: string;
  overall_duration: string;
  phases: LearningPhase[];
}

export interface LearningRoadmapCache {
  roadmap: LearningRoadmap | null;
  cached: boolean;
}
