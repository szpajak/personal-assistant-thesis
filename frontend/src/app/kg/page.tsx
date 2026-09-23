"use client";

import KnowledgeGraph from '@/components/kg/KnowledgeGraph';
import { useKGGraph } from '@/hooks/useKG';
import type { KGGraphPayload } from '@/types/kg';

export default function KnowledgeGraphPage() {
  const { data: rawGraphData, isLoading } = useKGGraph();
  const graphData = rawGraphData as KGGraphPayload | undefined;

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col space-y-3">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Personal Knowledge Graph</h1>
        <p className="text-muted-foreground">
          Skills sit in the center: evidence on the left, offers to the right, organizations one hop further.
          Click a node for details, double-click to focus its neighborhood.
        </p>
      </div>

      <div className="min-h-0 flex-1">
        <KnowledgeGraph data={graphData} isLoading={isLoading} />
      </div>
    </div>
  );
}
