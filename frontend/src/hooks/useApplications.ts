import { useQuery } from '@tanstack/react-query';
import { ApplicationsService } from '@/lib/api';

export function useApplications() {
  return useQuery({
    queryKey: ['applications'],
    queryFn: () => ApplicationsService.listApplicationsApiV1ApplicationsGet(),
    refetchInterval: 30000, // Poll every 30 seconds
  });
}
