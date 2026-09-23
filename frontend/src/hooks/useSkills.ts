import { useQuery } from '@tanstack/react-query';
import { SkillsService } from '@/lib/api';
import { apiFetch } from '@/lib/apiFetch';
import type {
  LearningRoadmap,
  LearningRoadmapCache,
  SkillAnalysis,
  SkillDemand,
  SuggestedProject,
  SuggestedProjectsCache,
} from '@/types/skills';

export function useSkills() {
  return useQuery({
    queryKey: ['skills'],
    queryFn: () => SkillsService.listSkillsApiV1SkillsGet(),
  });
}

export function useSkillAnalysis(targetRoleId?: string | null) {
  return useQuery({
    queryKey: ['skill-analysis', targetRoleId ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (targetRoleId) params.set('target_role_id', targetRoleId);
      const qs = params.toString();
      return apiFetch<SkillAnalysis>(
        `/api/v1/skills/analysis${qs ? `?${qs}` : ''}`
      );
    },
    // Poll while the target role's market sample is still being scraped/
    // ingested, so gaps appear automatically once it's ready.
    refetchInterval: (query) => {
      const data = query.state.data as SkillAnalysis | undefined;
      return data && !data.target_role_ready && data.sample_status !== 'error'
        ? 4000
        : false;
    },
  });
}

export function useCachedSuggestedProjects() {
  return useQuery({
    queryKey: ['suggested-projects-cache'],
    queryFn: () =>
      apiFetch<SuggestedProjectsCache>('/api/v1/skills/suggested-projects'),
  });
}

export function useMarketDemand(limit: number = 10, targetRoleId?: string | null) {
  return useQuery({
    queryKey: ['market-demand', limit, targetRoleId ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (targetRoleId) params.set('target_role_id', targetRoleId);
      return apiFetch<SkillDemand[]>(
        `/api/v1/skills/market-demand?${params.toString()}`
      );
    },
  });
}

export function useCachedLearningRoadmap() {
  return useQuery({
    queryKey: ['learning-roadmap-cache'],
    queryFn: () =>
      apiFetch<LearningRoadmapCache>('/api/v1/skills/learning-roadmap'),
  });
}

export async function regenerateSuggestedProjects(
  skills: string[]
): Promise<SuggestedProject[]> {
  return apiFetch<SuggestedProject[]>('/api/v1/skills/suggested-projects', {
    method: 'POST',
    body: JSON.stringify({ skills }),
  });
}

export async function generateLearningRoadmap(
  skills: string[],
  targetRoleId: string | null,
  includedProjects: SuggestedProject[]
): Promise<LearningRoadmap> {
  return apiFetch<LearningRoadmap>('/api/v1/skills/learning-roadmap', {
    method: 'POST',
    body: JSON.stringify({
      skills,
      target_role_id: targetRoleId,
      included_projects: includedProjects,
    }),
  });
}
