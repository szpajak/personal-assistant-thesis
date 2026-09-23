export type NodeFamily =
  | 'identity'
  | 'evidence'
  | 'competency'
  | 'market'
  | 'process';

export type PredicateFamily = 'evidence' | 'market' | 'career' | 'process';

export type GraphView = 'map' | 'focus' | 'matrix';

export type FilterMode = 'dismiss' | 'dim';

export type SkillOwnershipFilter = 'all' | 'owned' | 'gap';

export type CompanyRole = 'employer' | 'poster' | 'both' | 'other';

export interface KGNodePayload {
  id: string;
  type: string;
  data: {
    label: string;
    properties: Record<string, unknown>;
  };
}

export interface KGEdgePayload {
  id: string;
  source: string;
  target: string;
  label: string;
  properties?: Record<string, unknown>;
  animated?: boolean;
}

export interface KGGraphPayload {
  nodes: KGNodePayload[];
  edges: KGEdgePayload[];
  person_name?: string;
  person_id?: string;
}

export interface EnrichedNode extends KGNodePayload {
  family: NodeFamily;
  demandCount: number;
  evidenceCount: number;
  hasDirectSkillLink: boolean;
  skillScore: number;
  companyRole?: CompanyRole;
  isOwnedSkill?: boolean;
}

export interface EnrichedEdge extends KGEdgePayload {
  predicateFamily: PredicateFamily;
  sourceKind?: string;
  confidence?: number;
}

export interface GraphFilters {
  hiddenFamilies: NodeFamily[];
  hiddenPredicateFamilies: PredicateFamily[];
  hiddenTypes: string[];
  showPerson: boolean;
  search: string;
  filterMode: FilterMode;
  focusId: string | null;
  hops: 1 | 2;
  skillOwnership: SkillOwnershipFilter;
}
