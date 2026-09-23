import dagre from "dagre";
import { Edge, MarkerType, Node, Position } from "reactflow";

import type { EnrichedEdge, EnrichedNode, NodeFamily } from "@/types/kg";
import {
  evidenceSectionOf,
  SUBSTRATE_REGIONS,
  substrateRegionFor,
} from "./graphModel";

export const NODE_WIDTH = 260;
export const NODE_HEIGHT = 72;
const REGION_WIDTH = 300;
const REGION_GAP = 80;
const REGION_PAD_X = 20;
const REGION_PAD_TOP = 48;
const NODE_GAP_Y = 14;
const CATEGORY_GAP = 28;

export type LayoutDirection = "TB" | "LR";
export type LayoutMode = "substrate" | "radial";

function asString(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : "";
}

export function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction: LayoutDirection = "TB",
): { nodes: Node[]; edges: Edge[] } {
  if (nodes.length === 0) {
    return { nodes, edges };
  }

  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: direction, nodesep: 60, ranksep: 80 });

  const isHorizontal = direction === "LR";

  nodes.forEach((node) => {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  edges.forEach((edge) => {
    graph.setEdge(edge.source, edge.target);
  });

  dagre.layout(graph);

  const layoutedNodes = nodes.map((node) => {
    const positioned = graph.node(node.id);

    return {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      position: {
        x: positioned.x - NODE_WIDTH / 2,
        y: positioned.y - NODE_HEIGHT / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

function sortNodes(nodes: EnrichedNode[]): EnrichedNode[] {
  return [...nodes].sort((a, b) => {
    if (a.type === "Skill" && b.type === "Skill") {
      if (b.skillScore !== a.skillScore) return b.skillScore - a.skillScore;
    }
    return displayLabel(a).localeCompare(displayLabel(b));
  });
}

function displayLabel(node: EnrichedNode): string {
  const props = node.data.properties ?? {};
  return String(props.name ?? props.title ?? node.data.label ?? node.id);
}

export function getSubstrateLayout(
  nodes: EnrichedNode[],
  edges: EnrichedEdge[],
): { nodes: Node[]; edges: Edge[] } {
  const regionNodes: Node[] = [];
  const entityNodes: Node[] = [];
  const byRegion = new Map<string, EnrichedNode[]>();

  for (const node of nodes) {
    const regionId = substrateRegionFor(node);
    const list = byRegion.get(regionId) ?? [];
    list.push(node);
    byRegion.set(regionId, list);
  }

  const visibleRegions = SUBSTRATE_REGIONS.filter((region) => {
    if (region.id === "orgs") return (byRegion.get("orgs") ?? []).length > 0;
    return true;
  });

  visibleRegions.forEach((region, regionIndex) => {
    const members = sortNodes(byRegion.get(region.id) ?? []);
    const byCategory = new Map<string, EnrichedNode[]>();

    if (region.id === "skills") {
      for (const node of members) {
        const category = asString(node.data.properties.category) || "Other";
        const list = byCategory.get(category) ?? [];
        list.push(node);
        byCategory.set(category, list);
      }
    } else if (region.id === "evidence") {
      const work = members.filter(
        (node) => evidenceSectionOf(node) === "Roles & work",
      );
      const employers = members.filter(
        (node) => evidenceSectionOf(node) === "Employers",
      );
      if (work.length) byCategory.set("Roles & work", work);
      if (employers.length) byCategory.set("Employers", employers);
    } else {
      byCategory.set("", members);
    }

    let y = REGION_PAD_TOP;
    const categories = [...byCategory.entries()];

    for (const [category, group] of categories) {
      if (category) {
        entityNodes.push({
          id: `section-${region.id}-${category}`,
          type: "kgSection",
          parentNode: `region-${region.id}`,
          extent: "parent",
          data: { label: category },
          position: { x: REGION_PAD_X, y },
          selectable: false,
          draggable: false,
          connectable: false,
        });
        y += 22;
      }
      for (const node of group) {
        entityNodes.push({
          id: node.id,
          type: "kgEntity",
          parentNode: `region-${region.id}`,
          extent: "parent",
          data: toEntityData(node),
          position: { x: REGION_PAD_X, y },
          sourcePosition: Position.Right,
          targetPosition: Position.Left,
        });
        y += NODE_HEIGHT + NODE_GAP_Y;
      }
      if (category) {
        y += CATEGORY_GAP - NODE_GAP_Y;
      }
    }

    const height = Math.max(y + 16, 160);
    regionNodes.push({
      id: `region-${region.id}`,
      type: "kgRegion",
      data: { label: region.title, regionId: region.id },
      position: { x: regionIndex * (REGION_WIDTH + REGION_GAP), y: 0 },
      selectable: false,
      draggable: false,
      connectable: false,
      style: { width: REGION_WIDTH, height, zIndex: 0 },
    });
  });

  const stray = byRegion.get("stray") ?? [];
  stray.forEach((node, index) => {
    entityNodes.push({
      id: node.id,
      type: "kgEntity",
      data: toEntityData(node),
      position: {
        x: visibleRegions.length * (REGION_WIDTH + REGION_GAP),
        y: 48 + index * (NODE_HEIGHT + NODE_GAP_Y),
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    });
  });

  return {
    nodes: [...regionNodes, ...entityNodes],
    edges: toFlowEdges(edges, "smoothstep"),
  };
}

const FAMILY_SECTOR: Record<NodeFamily, { start: number; end: number }> = {
  evidence: { start: Math.PI * 0.7, end: Math.PI * 1.3 },
  market: { start: -Math.PI * 0.3, end: Math.PI * 0.3 },
  competency: { start: Math.PI * 0.35, end: Math.PI * 0.65 },
  identity: { start: Math.PI * 1.35, end: Math.PI * 1.55 },
  process: { start: Math.PI * 1.55, end: Math.PI * 1.75 },
};

export function getRadialLayout(
  nodes: EnrichedNode[],
  edges: EnrichedEdge[],
  focusId: string,
): { nodes: Node[]; edges: Edge[] } {
  const focus = nodes.find((node) => node.id === focusId) ?? nodes[0];
  if (!focus) {
    return { nodes: [], edges: [] };
  }

  const hopOf = hopIndex(focus.id, nodes, edges);
  const byHopFamily = new Map<string, EnrichedNode[]>();

  for (const node of nodes) {
    if (node.id === focus.id) continue;
    const hop = hopOf.get(node.id) ?? 1;
    const key = `${Math.min(hop, 2)}:${node.family}`;
    const list = byHopFamily.get(key) ?? [];
    list.push(node);
    byHopFamily.set(key, list);
  }

  const laid: Node[] = [
    {
      id: focus.id,
      type: "kgEntity",
      data: { ...toEntityData(focus), focused: true },
      position: { x: -NODE_WIDTH / 2, y: -NODE_HEIGHT / 2 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    },
  ];

  for (const [key, group] of byHopFamily) {
    const [hopRaw, family] = key.split(":") as [string, NodeFamily];
    const hop = Number(hopRaw);
    const radius = hop === 1 ? 320 : 560;
    const sector = FAMILY_SECTOR[family] ?? FAMILY_SECTOR.competency;
    const sorted = sortNodes(group);

    sorted.forEach((node, index) => {
      const t = sorted.length === 1 ? 0.5 : index / (sorted.length - 1);
      const angle = sector.start + t * (sector.end - sector.start);
      laid.push({
        id: node.id,
        type: "kgEntity",
        data: toEntityData(node),
        position: {
          x: Math.cos(angle) * radius - NODE_WIDTH / 2,
          y: Math.sin(angle) * radius - NODE_HEIGHT / 2,
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      });
    });
  }

  return { nodes: laid, edges: toFlowEdges(edges, "default") };
}

function hopIndex(
  startId: string,
  nodes: EnrichedNode[],
  edges: EnrichedEdge[],
): Map<string, number> {
  const hops = new Map<string, number>([[startId, 0]]);
  const adj = new Map<string, Set<string>>();
  for (const edge of edges) {
    if (!adj.has(edge.source)) adj.set(edge.source, new Set());
    if (!adj.has(edge.target)) adj.set(edge.target, new Set());
    adj.get(edge.source)!.add(edge.target);
    adj.get(edge.target)!.add(edge.source);
  }
  const queue = [startId];
  while (queue.length) {
    const current = queue.shift()!;
    const depth = hops.get(current) ?? 0;
    for (const next of adj.get(current) ?? []) {
      if (!hops.has(next)) {
        hops.set(next, depth + 1);
        queue.push(next);
      }
    }
  }
  for (const node of nodes) {
    if (!hops.has(node.id)) hops.set(node.id, 2);
  }
  return hops;
}

function toEntityData(node: EnrichedNode) {
  return {
    ...node.data.properties,
    label: node.data.label,
    kgType: node.type,
    family: node.family,
    demandCount: node.demandCount,
    evidenceCount: node.evidenceCount,
    hasDirectSkillLink: node.hasDirectSkillLink,
    skillScore: node.skillScore,
    companyRole: node.companyRole,
    isOwnedSkill: node.isOwnedSkill,
  };
}

function toFlowEdges(
  edges: EnrichedEdge[],
  type: "smoothstep" | "default",
): Edge[] {
  return edges.map((edge) => {
    const inferred = edge.sourceKind === "inferred";
    const confidence = edge.confidence;
    const width = confidence != null ? 1 + confidence * 2 : 1.5;
    const familyColor =
      edge.predicateFamily === "evidence"
        ? "#0072B2"
        : edge.predicateFamily === "market"
          ? "#D55E00"
          : edge.predicateFamily === "process"
            ? "#CC79A7"
            : "#56B4E9";

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label.replaceAll("_", " "),
      type,
      animated: false,
      markerEnd: {
        type: MarkerType.ArrowClosed,
      },
      style: {
        stroke: familyColor,
        strokeWidth: width,
        strokeDasharray: inferred ? "6 4" : undefined,
        opacity: inferred ? 0.75 : 1,
      },
      labelStyle: { fontSize: 9, fill: "#64748b" },
      labelBgStyle: { fill: "#f8fafc", fillOpacity: 0.85 },
    };
  });
}
