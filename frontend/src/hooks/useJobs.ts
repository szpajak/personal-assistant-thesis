import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ApplicationsService,
  JobsService,
  type ApplicationCreate,
  type JobScrapeRequest,
} from '@/lib/api';
import { apiFetch } from '@/lib/apiFetch';
import type { JobOffer, JobMatch, ScrapedJobFilters } from '@/types/jobs';

export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: () => JobsService.listJobsApiV1JobsGet(undefined, 'active', undefined, 'all'),
  });
}

/** Cached matches + live quick_score. Never triggers LLM. */
export function useJobMatches() {
  return useQuery({
    queryKey: ['job-matches'],
    queryFn: () => apiFetch<JobMatch[]>('/api/v1/jobs/match'),
  });
}

export function useMatchSingleJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      apiFetch<JobMatch>(`/api/v1/jobs/${encodeURIComponent(jobId)}/match`, {
        method: 'POST',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-matches'] });
    },
  });
}

export function useMatchJobsBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobIds?: string[] | null) =>
      apiFetch<JobMatch[]>('/api/v1/jobs/match', {
        method: 'POST',
        body: JSON.stringify({ job_ids: jobIds ?? null }),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-matches'] });
    },
  });
}

export function useScrapedJobs(filters: ScrapedJobFilters = {}) {
  const params = new URLSearchParams();
  if (filters.search) params.set('search', filters.search);
  if (filters.source) params.set('source', filters.source);
  if (filters.seniority) params.set('seniority', filters.seniority);
  if (filters.experience_bracket) {
    params.set('experience_bracket', filters.experience_bracket);
  }
  const qs = params.toString();
  return useQuery({
    queryKey: ['scraped-jobs', filters],
    queryFn: () =>
      apiFetch<JobOffer[]>(`/api/v1/jobs/scraped${qs ? `?${qs}` : ''}`),
  });
}

export function useDeleteScrapedJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (listingId: string) =>
      apiFetch<void>(`/api/v1/jobs/scraped/${listingId}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scraped-jobs'] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

/**
 * Queues a background Celery scrape into the Postgres staging table.
 */
export function useTriggerJobScrape() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (filters: JobScrapeRequest) =>
      JobsService.triggerJobScrapeApiV1JobsScrapePost(filters),
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['jobs'] });
        queryClient.invalidateQueries({ queryKey: ['scraped-jobs'] });
        queryClient.invalidateQueries({ queryKey: ['job-matches'] });
      }, 15000);
    },
  });
}

/** Promote a staging listing into the career knowledge graph. */
export function usePromoteJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      JobsService.promoteJobApiV1JobsJobIdPromotePost(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['scraped-jobs'] });
      queryClient.invalidateQueries({ queryKey: ['job-matches'] });
    },
  });
}

/** Create an application (backend promotes the listing first). */
export function useCreateApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ApplicationCreate) =>
      ApplicationsService.createApplicationApiV1ApplicationsPost(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['scraped-jobs'] });
      queryClient.invalidateQueries({ queryKey: ['job-matches'] });
    },
  });
}
