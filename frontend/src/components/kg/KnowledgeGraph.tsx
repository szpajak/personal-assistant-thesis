'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';

import type {
  GraphFilters,
  GraphView,
  KGGraphPayload,
  NodeFamily,
  PredicateFamily,
} from '@/types/kg';
import { EvidenceMatrix } from './EvidenceMatrix';
import { GraphLegend } from './GraphLegend';
import { GraphToolbar } from './GraphToolbar';
import {
  applyVisibility,
  collapseCrowdedTypes,
  defaultFilters,
  displayName,
  enrichGraph,
  FAMILY_THEME,
  neighborIdsOf,
  nodeMatchesSearch,
} from './graphModel';
import { getRadialLayout, getSubstrateLayout } from './layoutGraph';
import { NodeDetailPanel } from './NodeDetailPanel';
import { KgEntityNode, KgRegionNode, KgSectionNode, type KgEntityData } from './Nodes';

const nodeTypes = {
  kgEntity: KgEntityNode,
  kgRegion: KgRegionNode,
  kgSection: KgSectionNode,
};

interface KnowledgeGraphProps {
  data: KGGraphPayload | undefined;
  isLoading: boolean;
}

function withHighlight(
  nodes: Node[],
  edges: ReturnType<typeof getSubstrateLayout>['edges'],
  selectedId: string | null,
  neighborIds: Set<string>,
  dimmedNodeIds: Set<string>,
) {
  const selecting = Boolean(selectedId);
  return {
    nodes: nodes.map((node) => {
      if (node.type === 'kgRegion' || node.type === 'kgSection') return node;
      const dimmed = dimmedNodeIds.has(node.id) || (selecting && !neighborIds.has(node.id));
      return {
        ...node,
        data: {
          ...node.data,
          dimmed,
          highlighted: selecting && neighborIds.has(node.id),
          focused: node.id === selectedId,
        },
        style: { ...node.style, opacity: dimmed ? 0.22 : 1 },
      };
    }),
    edges: edges.map((edge) => {
      const related = !selecting || edge.source === selectedId || edge.target === selectedId;
      return {
        ...edge,
        style: {
          ...edge.style,
          opacity: related ? 1 : 0.12,
        },
      };
    }),
  };
}

function KnowledgeGraphCanvas({ data, isLoading }: KnowledgeGraphProps) {
  const { nodes: enrichedNodes, edges: enrichedEdges, personName, personId } = useMemo(
    () => enrichGraph(data),
    [data],
  );
  const [filters, setFilters] = useState<GraphFilters>(defaultFilters);
  const [view, setView] = useState<GraphView>('map');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const { fitView } = useReactFlow();

  const visibility = useMemo(
    () => applyVisibility(enrichedNodes, enrichedEdges, filters),
    [enrichedNodes, enrichedEdges, filters],
  );
  const neighborIds = useMemo(
    () => neighborIdsOf(selectedId, visibility.visibleEdges),
    [selectedId, visibility.visibleEdges],
  );

  const { nodes: sceneNodes, collapsed } = useMemo(
    () => collapseCrowdedTypes(visibility.visibleNodes, expandedTypes),
    [visibility.visibleNodes, expandedTypes],
  );

  const sceneEdges = useMemo(() => {
    const ids = new Set(sceneNodes.map((node) => node.id));
    return visibility.visibleEdges.filter(
      (edge) => ids.has(edge.source) && ids.has(edge.target),
    );
  }, [sceneNodes, visibility.visibleEdges]);

  const layoutMode = view === 'focus' || filters.showPerson ? 'radial' : 'substrate';
  const radialFocusId =
    filters.focusId ??
    (filters.showPerson ? personId : null) ??
    sceneNodes[0]?.id ??
    null;

  const laid = useMemo(() => {
    if (view === 'matrix' || sceneNodes.length === 0) {
      return { nodes: [] as Node[], edges: [] as ReturnType<typeof getSubstrateLayout>['edges'] };
    }
    if (layoutMode === 'radial' && radialFocusId) {
      return getRadialLayout(sceneNodes, sceneEdges, radialFocusId);
    }
    return getSubstrateLayout(sceneNodes, sceneEdges);
  }, [view, layoutMode, radialFocusId, sceneNodes, sceneEdges]);

  const painted = useMemo(
    () =>
      withHighlight(laid.nodes, laid.edges, selectedId, neighborIds, visibility.dimmedNodeIds),
    [laid, selectedId, neighborIds, visibility.dimmedNodeIds],
  );

  useEffect(() => {
    setNodes(painted.nodes);
    setEdges(painted.edges);
  }, [painted, setNodes, setEdges]);

  useEffect(() => {
    if (view === 'matrix' || laid.nodes.length === 0) return;
    window.requestAnimationFrame(() => {
      fitView({ padding: 0.18, duration: 280 });
    });
  }, [view, layoutMode, radialFocusId, sceneNodes, sceneEdges, fitView, laid.nodes.length]);

  const selectedFlowNode = nodes.find((node) => node.id === selectedId && node.type === 'kgEntity') as
    | Node<KgEntityData>
    | undefined;
  const selectedEnriched = enrichedNodes.find((node) => node.id === selectedId);

  const focusLabel = useMemo(() => {
    if (!filters.focusId) return null;
    const node = enrichedNodes.find((item) => item.id === filters.focusId);
    return node ? displayName(node) : 'selection';
  }, [filters.focusId, enrichedNodes]);

  const enterFocus = useCallback((nodeId: string) => {
    setView('focus');
    setFilters((current) => ({ ...current, focusId: nodeId, hops: 1 }));
    setSelectedId(nodeId);
  }, []);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.type === 'kgRegion' || node.type === 'kgSection') return;
    setSelectedId(node.id);
  }, []);

  const onNodeDoubleClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (node.type === 'kgRegion' || node.type === 'kgSection') return;
      enterFocus(node.id);
    },
    [enterFocus],
  );

  const onPaneClick = useCallback(() => {
    setSelectedId(null);
  }, []);

  const handleViewChange = useCallback(
    (next: GraphView) => {
      setView(next);
      if (next === 'map') {
        setFilters((current) => ({ ...current, focusId: null, showPerson: false }));
      }
      if (next === 'focus' && !filters.focusId) {
        const fallback =
          selectedId ??
          sceneNodes.find((node) => node.type === 'Skill')?.id ??
          sceneNodes[0]?.id ??
          null;
        if (fallback) {
          setFilters((current) => ({ ...current, focusId: fallback }));
        }
      }
    },
    [filters.focusId, selectedId, sceneNodes],
  );

  const handleShowPerson = useCallback(
    (value: boolean) => {
      setFilters((current) => {
        let hiddenPredicateFamilies = current.hiddenPredicateFamilies;
        if (value) {
          hiddenPredicateFamilies = hiddenPredicateFamilies.filter((item) => item !== 'career');
        } else if (!hiddenPredicateFamilies.includes('career')) {
          hiddenPredicateFamilies = [...hiddenPredicateFamilies, 'career'];
        }
        return {
          ...current,
          showPerson: value,
          hiddenPredicateFamilies,
          focusId: value ? personId : current.focusId === personId ? null : current.focusId,
        };
      });
      if (value && personId) {
        setView('focus');
        setSelectedId(personId);
      } else if (!value && view === 'focus' && filters.focusId === personId) {
        setView('map');
      }
    },
    [personId, view, filters.focusId],
  );

  const handleSearchSubmit = useCallback(() => {
    const matches = enrichedNodes.filter((node) => nodeMatchesSearch(node, filters.search));
    if (matches.length === 1) {
      enterFocus(matches[0].id);
    } else if (matches.length > 1) {
      const preferred =
        matches.find((node) => node.type === 'Skill') ?? matches[0];
      setSelectedId(preferred.id);
    }
  }, [enrichedNodes, filters.search, enterFocus]);

  const toggleFamily = useCallback((family: NodeFamily) => {
    setFilters((current) => {
      const hidden = current.hiddenFamilies.includes(family)
        ? current.hiddenFamilies.filter((item) => item !== family)
        : [...current.hiddenFamilies, family];
      return { ...current, hiddenFamilies: hidden };
    });
  }, []);

  const togglePredicate = useCallback((family: PredicateFamily) => {
    setFilters((current) => {
      const hidden = current.hiddenPredicateFamilies.includes(family)
        ? current.hiddenPredicateFamilies.filter((item) => item !== family)
        : [...current.hiddenPredicateFamilies, family];
      return { ...current, hiddenPredicateFamilies: hidden };
    });
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border bg-slate-50/50">
        <div className="flex items-center gap-2 text-lg animate-pulse">
          <div className="h-4 w-4 animate-bounce rounded-full bg-primary" />
          Loading Knowledge Graph...
        </div>
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center space-y-4 rounded-lg border border-dashed bg-white">
        <div className="text-xl font-semibold">Your Knowledge Graph is empty</div>
        <p className="max-w-md text-center text-muted-foreground">
          Start by adding projects, skills, or applying for jobs to see your personal professional network grow.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <GraphToolbar
        view={view}
        onViewChange={handleViewChange}
        search={filters.search}
        onSearchChange={(search) => setFilters((current) => ({ ...current, search }))}
        onSearchSubmit={handleSearchSubmit}
        showPerson={filters.showPerson}
        onShowPersonChange={handleShowPerson}
        personName={personName}
        hiddenFamilies={filters.hiddenFamilies}
        onToggleFamily={toggleFamily}
        hiddenPredicateFamilies={filters.hiddenPredicateFamilies}
        onTogglePredicateFamily={togglePredicate}
        filterMode={filters.filterMode}
        onFilterModeChange={(filterMode) => setFilters((current) => ({ ...current, filterMode }))}
        hops={filters.hops}
        onHopsChange={(hops) => setFilters((current) => ({ ...current, hops }))}
        focusLabel={view === 'focus' ? focusLabel : null}
        onClearFocus={() => {
          setFilters((current) => ({ ...current, focusId: null, showPerson: false }));
          setView('map');
        }}
        collapsed={collapsed}
        skillOwnership={filters.skillOwnership}
        onSkillOwnershipChange={(skillOwnership) =>
          setFilters((current) => ({ ...current, skillOwnership }))
        }
        onExpandType={(type) =>
          setExpandedTypes((current) => {
            const next = new Set(current);
            next.add(type);
            return next;
          })
        }
      />

      {view === 'matrix' ? (
        <div className="min-h-0 flex-1">
          <EvidenceMatrix
            nodes={visibility.visibleNodes}
            edges={visibility.visibleEdges}
            onSelect={(id) => {
              enterFocus(id);
            }}
          />
        </div>
      ) : (
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-lg border bg-slate-50/40">
          {sceneNodes.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {filters.skillOwnership === 'owned'
                ? 'No owned skills match the current filters.'
                : filters.skillOwnership === 'gap'
                  ? 'No gap skills match the current filters.'
                  : 'Nothing to show with the current filters. Enable a family or clear search.'}
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              onNodeDoubleClick={onNodeDoubleClick}
              onPaneClick={onPaneClick}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.2}
              maxZoom={1.6}
              nodesConnectable={false}
              deleteKeyCode={null}
            >
              <Background color="#cbd5e1" gap={20} />
              <Controls />
              <MiniMap
                nodeColor={(node) => {
                  if (node.type === 'kgRegion' || node.type === 'kgSection') return '#e2e8f0';
                  const family = (node.data as KgEntityData | undefined)?.family;
                  return family ? FAMILY_THEME[family].hex : '#94a3b8';
                }}
              />
            </ReactFlow>
          )}
          <GraphLegend />
          {selectedFlowNode && (
            <NodeDetailPanel
              node={selectedFlowNode}
              enriched={selectedEnriched}
              onClose={() => setSelectedId(null)}
              onFocus={() => enterFocus(selectedFlowNode.id)}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default function KnowledgeGraph(props: KnowledgeGraphProps) {
  return (
    <ReactFlowProvider>
      <KnowledgeGraphCanvas {...props} />
    </ReactFlowProvider>
  );
}
