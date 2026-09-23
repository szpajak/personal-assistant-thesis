import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PortfolioService } from "@/lib/api";
import type { ProjectRead, SkillDraft as ApiSkillDraft } from "@/lib/api";
import { apiFetch } from "@/lib/apiFetch";
import type {
  Project,
  ProjectStatus,
  SkillDraft,
  SkillLevel,
} from "@/types/portfolio";

const SKILL_LEVELS: SkillLevel[] = [
  "beginner",
  "intermediate",
  "advanced",
  "expert",
];

function normalizeSkillLevel(level: string | null | undefined): SkillLevel {
  return (SKILL_LEVELS as string[]).includes(level ?? "")
    ? (level as SkillLevel)
    : "intermediate";
}

export function normalizeSkillDraft(skill: ApiSkillDraft): SkillDraft {
  return {
    name: skill.name,
    canonical_name: skill.canonical_name ?? null,
    category: skill.category ?? "technical",
    level: normalizeSkillLevel(skill.level),
    confidence: skill.confidence ?? 1.0,
  };
}

function normalizeProject(project: ProjectRead & { status?: string }): Project {
  const status = project.status;
  const resolvedStatus: ProjectStatus =
    status === "planned" || status === "in_progress" || status === "finished"
      ? status
      : "in_progress";
  return {
    id: project.id,
    title: project.title,
    description: project.description,
    tech_stack: project.tech_stack ?? [],
    start_date: project.start_date,
    end_date: project.end_date ?? null,
    media_urls: project.media_urls ?? [],
    seniority: project.seniority ?? null,
    achievements: project.achievements ?? [],
    skills: (project.skills ?? []).map(normalizeSkillDraft),
    status: resolvedStatus,
  };
}

export function usePortfolioProjects(status?: ProjectStatus | "") {
  return useQuery({
    queryKey: ["portfolio", status || "all"],
    queryFn: async () => {
      const qs = status ? `?status=${status}` : "";
      const data = await apiFetch<(ProjectRead & { status?: string })[]>(
        `/api/v1/portfolio/${qs}`,
      );
      return data.map(normalizeProject);
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<Project> & { id: string }) =>
      apiFetch<ProjectRead>(`/api/v1/portfolio/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/portfolio/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });
}

export function useCreateProjectFromPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (item: {
      title: string;
      description?: string;
      url?: string;
      skill_name?: string;
    }) =>
      apiFetch<ProjectRead>("/api/v1/portfolio/from-plan", {
        method: "POST",
        body: JSON.stringify(item),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["kg-graph"] });
      queryClient.invalidateQueries({ queryKey: ["kg-stats"] });
    },
  });
}

export function useCreateProjectFromSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (suggestion: {
      title: string;
      description?: string;
      tech_stack?: string[];
      skills_covered?: string[];
      key_steps?: string[];
      deliverables?: string[];
    }) =>
      apiFetch<ProjectRead>("/api/v1/portfolio/from-suggestion", {
        method: "POST",
        body: JSON.stringify(suggestion),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

// Re-export for callers that still use the generated client list helper.
export { PortfolioService };
