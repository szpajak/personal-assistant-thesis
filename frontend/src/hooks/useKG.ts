import { useQuery } from "@tanstack/react-query";
import { KnowledgeGraphService } from "@/lib/api";

export function useKGStats() {
  return useQuery({
    queryKey: ["kg-stats"],
    queryFn: () => KnowledgeGraphService.getStatsApiV1KgStatsGet(),
  });
}

export function useKGGraph() {
  return useQuery({
    queryKey: ["kg-graph"],
    queryFn: () => KnowledgeGraphService.getGraphApiV1KgGraphGet(),
  });
}
