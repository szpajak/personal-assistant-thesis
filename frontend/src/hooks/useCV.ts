import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/apiFetch';

export function useGenerateCV() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, force = false }: { jobId: string; force?: boolean }) => {
      const params = new URLSearchParams({ job_id: jobId });
      if (force) params.set('force', 'true');
      return apiFetch<{ cv_content: string; cached: boolean }>(
        `/api/v1/cv/generate?${params.toString()}`,
        { method: 'POST' }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}
