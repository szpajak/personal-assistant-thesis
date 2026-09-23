import type {
  CompanyRole,
  EnrichedEdge,
  EnrichedNode,
  GraphFilters,
  KGEdgePayload,
  KGGraphPayload,
  KGNodePayload,
  NodeFamily,
  PredicateFamily,
  SkillOwnershipFilter,
} from '@/types/kg';

export const NODE_FAMILY_BY_TYPE: Record<string, NodeFamily> = {
  Person: 'identity',
  Employment: 'evidence',
  Education: 'evidence',
  Project: 'evidence',
  Certificate: 'evidence',
  Document: 'evidence',
  Skill: 'competency',
  LearningResource: 'competency',
  SkillDemandSnapshot: 'competency',
  JobOffer: 'market',
  Company: 'market',
  TargetRole: 'market',
  Application: 'process',
  Email: 'process',
};

export const PREDICATE_FAMILY_BY_TYPE: Record<string, PredicateFamily> = {
  USES: 'evidence',
  VALIDATES: 'evidence',
  USED_IN_ROLE: 'evidence',
  TEACHES: 'evidence',
  REQUIRES: 'market',
  POSTED_BY: 'market',
  AT_COMPANY: 'evidence',
  PRODUCED: 'career',
  WORKED_AT: 'career',
  STUDIED_AT: 'career',
  AIMS_FOR: 'career',
  HAS_SKILL: 'career',
  HAS_CERTIFICATE: 'career',
  RECOMMENDED: 'career',
  SAVED: 'career',
  APPLIED_TO: 'process',
  FOR_OFFER: 'process',
  HAS_EMAIL: 'process',
  RECEIVED: 'process',
  FROM_COMPANY: 'process',
  DEMAND_SNAPSHOT: 'process',
};

/** Types never drawn on the node-link canvas. */
export const NEVER_SHOW_TYPES = new Set(['SkillDemandSnapshot', 'Document']);

/** Default-hidden types on the career map (Person is a separate toggle). */
export const DEFAULT_HIDDEN_TYPES = new Set([
  'Email',
  'Application',
  'LearningResource',
  'Document',
  'SkillDemandSnapshot',
]);

export const DEFAULT_HIDDEN_FAMILIES: NodeFamily[] = ['process'];

export const DEFAULT_HIDDEN_PREDICATE_FAMILIES: PredicateFamily[] = ['career', 'process'];

export const FAMILY_THEME: Record<
  NodeFamily,
  { hex: string; label: string; description: string }
> = {
  identity: {
    hex: '#56B4E9',
    label: 'Identity',
    description: 'You — hidden by default on a per-user graph',
  },
  evidence: {
    hex: '#0072B2',
    label: 'Evidence',
    description: 'Projects, jobs held, certificates, education',
  },
  competency: {
    hex: '#009E73',
    label: 'Skills',
    description: 'The join key of the career graph',
  },
  market: {
    hex: '#D55E00',
    label: 'Market',
    description: 'Saved jobs and target roles',
  },
  process: {
    hex: '#CC79A7',
    label: 'Process',
    description: 'Applications and emails',
  },
};

export const PREDICATE_THEME: Record<PredicateFamily, { hex: string; label: string }> = {
  evidence: { hex: '#0072B2', label: 'Proof' },
  market: { hex: '#D55E00', label: 'Demand' },
  career: { hex: '#56B4E9', label: 'Career' },
  process: { hex: '#CC79A7', label: 'Process' },
};

export const TYPE_LABELS: Record<string, string> = {
  Person: 'Person',
  Project: 'Project',
  Skill: 'Skill',
  JobOffer: 'Job offer',
  Company: 'Company',
  Application: 'Application',
  Certificate: 'Certificate',
  Employment: 'Employment',
  Education: 'Education',
  TargetRole: 'Target role',
  Email: 'Email',
  LearningResource: 'Learning',
  Document: 'Document',
};

export const LEVEL_RANK: Record<string, number> = {
  beginner: 1,
  intermediate: 2,
  advanced: 3,
  expert: 4,
};

export const SUBSTRATE_REGIONS: {
  id: 'evidence' | 'skills' | 'market' | 'orgs';
  title: string;
  types: string[];
}[] = [
  {
    id: 'evidence',
    title: 'Evidence',
    types: ['Project', 'Employment', 'Certificate', 'Education'],
  },
  {
    id: 'skills',
    title: 'Skills',
    types: ['Skill', 'LearningResource'],
  },
  {
    id: 'market',
    title: 'Offers / goals',
    types: ['JobOffer', 'TargetRole'],
  },
  {
    id: 'orgs',
    title: 'Organizations',
    types: [],
  },
];

export const SKILL_COLLAPSE_THRESHOLD = 24;
export const TYPE_COLLAPSE_THRESHOLD = 12;

export function familyOfType(type: string | undefined): NodeFamily {
  if (!type) return 'identity';
  return NODE_FAMILY_BY_TYPE[type] ?? 'identity';
}

export function predicateFamilyOf(relType: string | undefined): PredicateFamily {
  if (!relType) return 'career';
  return PREDICATE_FAMILY_BY_TYPE[relType] ?? 'career';
}

export function displayName(node: KGNodePayload): string {
  const props = node.data.properties ?? {};
  const fromProps =
    props.name ?? props.title ?? props.institution ?? props.status ?? props.label;
  return String(fromProps ?? node.data.label ?? node.id);
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function companyRoleOf(
  type: string,
  id: string,
  employers: Set<string>,
  posters: Set<string>,
): CompanyRole | undefined {
  if (type !== 'Company') return undefined;
  const employed = employers.has(id);
  const posted = posters.has(id);
  if (employed && posted) return 'both';
  if (employed) return 'employer';
  if (posted) return 'poster';
  return 'other';
}

export function enrichGraph(payload: KGGraphPayload | undefined): {
  nodes: EnrichedNode[];
  edges: EnrichedEdge[];
  personName: string;
  personId: string | null;
} {
  if (!payload?.nodes?.length) {
    return { nodes: [], edges: [], personName: '', personId: null };
  }

  const demand: Record<string, number> = {};
  const evidence: Record<string, number> = {};
  const directSkills = new Set<string>();
  const employerCompanies = new Set<string>();
  const posterCompanies = new Set<string>();

  const edges: EnrichedEdge[] = (payload.edges ?? []).map((edge) => {
    const props = edge.properties ?? {};
    if (edge.label === 'REQUIRES') {
      demand[edge.target] = (demand[edge.target] ?? 0) + 1;
    }
    if (edge.label === 'USES' || edge.label === 'VALIDATES' || edge.label === 'USED_IN_ROLE') {
      evidence[edge.target] = (evidence[edge.target] ?? 0) + 1;
    }
    if (edge.label === 'HAS_SKILL') {
      directSkills.add(edge.target);
    }
    if (edge.label === 'AT_COMPANY') {
      employerCompanies.add(edge.target);
    }
    if (edge.label === 'POSTED_BY') {
      posterCompanies.add(edge.target);
    }
    return {
      ...edge,
      properties: props,
      predicateFamily: predicateFamilyOf(edge.label),
      sourceKind: asString(props.source),
      confidence: asNumber(props.confidence),
    };
  });

  const nodes: EnrichedNode[] = payload.nodes.map((node) => {
    const props = node.data.properties ?? {};
    const demandCount = asNumber(props.demand_count) ?? demand[node.id] ?? 0;
    const evidenceCount = asNumber(props.evidence_count) ?? evidence[node.id] ?? 0;
    const hasDirectSkillLink =
      Boolean(props.has_direct_link) || directSkills.has(node.id);
    const level = asString(props.level)?.toLowerCase() ?? '';
    const skillScore =
      (LEVEL_RANK[level] ?? 0) * 10 + demandCount + evidenceCount;
    const companyRole = companyRoleOf(node.type, node.id, employerCompanies, posterCompanies);
    const family =
      node.type === 'Company' && (companyRole === 'employer' || companyRole === 'both')
        ? 'evidence'
        : familyOfType(node.type);

    return {
      ...node,
      family,
      demandCount,
      evidenceCount,
      hasDirectSkillLink,
      skillScore,
      companyRole,
      isOwnedSkill: node.type === 'Skill' ? hasDirectSkillLink : undefined,
    };
  });

  const person = nodes.find((node) => node.type === 'Person');
  return {
    nodes,
    edges,
    personName: payload.person_name || (person ? displayName(person) : ''),
    personId: payload.person_id ?? person?.id ?? null,
  };
}

export function defaultFilters(): GraphFilters {
  return {
    hiddenFamilies: [...DEFAULT_HIDDEN_FAMILIES],
    hiddenPredicateFamilies: [...DEFAULT_HIDDEN_PREDICATE_FAMILIES],
    hiddenTypes: [...DEFAULT_HIDDEN_TYPES],
    showPerson: false,
    search: '',
    filterMode: 'dismiss',
    focusId: null,
    hops: 1,
    skillOwnership: 'all',
  };
}

export function nodeMatchesSearch(node: EnrichedNode, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  const props = node.data.properties ?? {};
  const haystack = [
    displayName(node),
    node.type,
    asString(props.category),
    asString(props.level),
    asString(props.company),
    asString(props.status),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return haystack.includes(needle);
}

export function adjacency(edges: EnrichedEdge[]): Map<string, Set<string>> {
  const map = new Map<string, Set<string>>();
  const add = (from: string, to: string) => {
    if (!map.has(from)) map.set(from, new Set());
    map.get(from)!.add(to);
  };
  for (const edge of edges) {
    add(edge.source, edge.target);
    add(edge.target, edge.source);
  }
  return map;
}

export function nodesWithinHops(
  startId: string,
  edges: EnrichedEdge[],
  hops: number,
): Set<string> {
  const kept = new Set<string>([startId]);
  const graph = adjacency(edges);
  let frontier = [startId];
  for (let depth = 0; depth < hops; depth += 1) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const neighbor of graph.get(id) ?? []) {
        if (!kept.has(neighbor)) {
          kept.add(neighbor);
          next.push(neighbor);
        }
      }
    }
    frontier = next;
  }
  return kept;
}

export function isNodeVisible(
  node: EnrichedNode,
  filters: GraphFilters,
  neighborhood: Set<string> | null,
  skillKeep: Set<string> | null,
): boolean {
  if (NEVER_SHOW_TYPES.has(node.type)) return false;
  if (node.type === 'Person' && !filters.showPerson) return false;
  if (node.type === 'Company' && node.companyRole === 'other' && filters.hiddenFamilies.includes('process')) {
    return false;
  }
  if (filters.hiddenTypes.includes(node.type)) return false;
  if (filters.hiddenFamilies.includes(node.family)) return false;
  if (neighborhood && !neighborhood.has(node.id)) return false;
  if (skillKeep && !skillKeep.has(node.id)) return false;
  if (filters.filterMode === 'dismiss' && !nodeMatchesSearch(node, filters.search)) {
    return false;
  }
  return true;
}

export function isEdgeVisible(
  edge: EnrichedEdge,
  visibleIds: Set<string>,
  filters: GraphFilters,
  showPerson: boolean,
): boolean {
  if (!visibleIds.has(edge.source) || !visibleIds.has(edge.target)) return false;
  if (filters.hiddenPredicateFamilies.includes(edge.predicateFamily)) return false;
  if (!showPerson && (edge.label === 'HAS_SKILL' || edge.label === 'PRODUCED')) {
    return false;
  }
  return true;
}

export interface VisibilityResult {
  visibleNodes: EnrichedNode[];
  dimmedNodeIds: Set<string>;
  visibleEdges: EnrichedEdge[];
}

export function skillOwnershipKeepIds(
  nodes: EnrichedNode[],
  edges: EnrichedEdge[],
  mode: SkillOwnershipFilter,
): Set<string> | null {
  if (mode === 'all') return null;

  // Seed only with the selected skill subset. Neighbors are added from this
  // seed alone — expanding from a growing `kept` set would leak sibling skills
  // that share a JobOffer/Project (e.g. owned Python would pull in gap K8s).
  const selectedSkills = new Set(
    nodes
      .filter((node) => node.type === 'Skill')
      .filter((node) => (mode === 'owned' ? node.isOwnedSkill : !node.isOwnedSkill))
      .map((node) => node.id),
  );

  const kept = new Set<string>(selectedSkills);
  for (const edge of edges) {
    if (selectedSkills.has(edge.source)) kept.add(edge.target);
    if (selectedSkills.has(edge.target)) kept.add(edge.source);
  }

  // Organizations sit one hop past offers/employment — include them without
  // also admitting other skills attached to those same offers.
  const companyHops = new Set(['POSTED_BY', 'AT_COMPANY']);
  const withCompanies = new Set(kept);
  for (const edge of edges) {
    if (!companyHops.has(edge.label)) continue;
    if (kept.has(edge.source)) withCompanies.add(edge.target);
    if (kept.has(edge.target)) withCompanies.add(edge.source);
  }

  return withCompanies;
}

export function applyVisibility(
  nodes: EnrichedNode[],
  edges: EnrichedEdge[],
  filters: GraphFilters,
): VisibilityResult {
  const neighborhood =
    filters.focusId != null
      ? nodesWithinHops(filters.focusId, edges, filters.hops)
      : null;
  const skillKeep = skillOwnershipKeepIds(nodes, edges, filters.skillOwnership);

  const dimmedNodeIds = new Set<string>();
  const visibleNodes: EnrichedNode[] = [];

  for (const node of nodes) {
    const passesStructural = isNodeVisible(
      node,
      { ...filters, filterMode: 'dismiss', search: '' },
      neighborhood,
      skillKeep,
    );
    if (!passesStructural) continue;

    const matchesSearch = nodeMatchesSearch(node, filters.search);
    if (!matchesSearch && filters.filterMode === 'dismiss') continue;
    if (!matchesSearch && filters.filterMode === 'dim') {
      dimmedNodeIds.add(node.id);
    }
    visibleNodes.push(node);
  }

  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = edges.filter((edge) =>
    isEdgeVisible(edge, visibleIds, filters, filters.showPerson),
  );

  return { visibleNodes, dimmedNodeIds, visibleEdges };
}

export function neighborIdsOf(selectedId: string | null, edges: EnrichedEdge[]): Set<string> {
  const neighborIds = new Set<string>();
  if (!selectedId) return neighborIds;
  neighborIds.add(selectedId);
  for (const edge of edges) {
    if (edge.source === selectedId) neighborIds.add(edge.target);
    if (edge.target === selectedId) neighborIds.add(edge.source);
  }
  return neighborIds;
}

export function collapseCrowdedTypes(
  nodes: EnrichedNode[],
  expandedTypes: Set<string>,
): { nodes: EnrichedNode[]; collapsed: Record<string, number> } {
  const byType = new Map<string, EnrichedNode[]>();
  for (const node of nodes) {
    const list = byType.get(node.type) ?? [];
    list.push(node);
    byType.set(node.type, list);
  }

  const kept: EnrichedNode[] = [];
  const collapsed: Record<string, number> = {};

  for (const [type, list] of byType) {
    const threshold =
      type === 'Skill' ? SKILL_COLLAPSE_THRESHOLD : TYPE_COLLAPSE_THRESHOLD;
    if (expandedTypes.has(type) || list.length <= threshold) {
      kept.push(...list);
      continue;
    }
    const ranked = [...list].sort((a, b) => b.skillScore - a.skillScore);
    kept.push(...ranked.slice(0, threshold));
    collapsed[type] = ranked.length - threshold;
  }

  return { nodes: kept, collapsed };
}

export function typeHref(type: string | undefined): string | null {
  switch (type) {
    case 'Skill':
      return '/skills';
    case 'Project':
      return '/portfolio';
    case 'JobOffer':
      return '/jobs';
    case 'Application':
      return '/applications';
    case 'Certificate':
      return '/certificates';
    case 'Employment':
    case 'Education':
    case 'TargetRole':
      return '/career';
    default:
      return null;
  }
}

export function curatedFields(
  node: EnrichedNode,
): { key: string; label: string; value: unknown }[] {
  const props = node.data.properties ?? {};
  const pick = (key: string, label: string) => {
    const value = props[key];
    if (value === undefined || value === null || value === '') return null;
    if (Array.isArray(value) && value.length === 0) return null;
    return { key, label, value };
  };

  const byType: Record<string, { key: string; label: string }[]> = {
    Skill: [
      { key: 'category', label: 'Category' },
      { key: 'level', label: 'Level' },
    ],
    Project: [
      { key: 'status', label: 'Status' },
      { key: 'seniority', label: 'Seniority' },
      { key: 'tech_stack', label: 'Tech stack' },
      { key: 'description', label: 'Description' },
    ],
    JobOffer: [
      { key: 'company', label: 'Company' },
      { key: 'status', label: 'Status' },
      { key: 'url', label: 'URL' },
    ],
    Company: [
      { key: 'industry', label: 'Industry' },
      { key: 'website', label: 'Website' },
    ],
    Certificate: [
      { key: 'issuer', label: 'Issuer' },
      { key: 'issued_at', label: 'Issued' },
    ],
    Employment: [
      { key: 'company', label: 'Company' },
      { key: 'title', label: 'Title' },
      { key: 'start_date', label: 'Start' },
      { key: 'end_date', label: 'End' },
    ],
    Education: [
      { key: 'institution', label: 'Institution' },
      { key: 'degree', label: 'Degree' },
      { key: 'field_of_study', label: 'Field' },
    ],
    TargetRole: [{ key: 'title', label: 'Title' }],
    Application: [
      { key: 'status', label: 'Status' },
      { key: 'applied_at', label: 'Applied' },
      { key: 'notes', label: 'Notes' },
    ],
    Person: [
      { key: 'email', label: 'Email' },
      { key: 'phone', label: 'Phone' },
      { key: 'location', label: 'Location' },
      { key: 'linkedin_url', label: 'LinkedIn' },
      { key: 'github_url', label: 'GitHub' },
      { key: 'website_url', label: 'Website' },
      { key: 'bio', label: 'Bio' },
    ],
    Email: [
      { key: 'subject', label: 'Subject' },
      { key: 'sender', label: 'Sender' },
      { key: 'classification', label: 'Classification' },
    ],
  };

  const fields = (byType[node.type] ?? []).map((item) => pick(item.key, item.label));
  const extras: { key: string; label: string; value: unknown }[] = [];
  if (node.type === 'Skill' && node.demandCount > 0) {
    extras.push({ key: 'demand', label: 'Jobs requiring this', value: node.demandCount });
  }
  if (node.type === 'Skill' && node.evidenceCount > 0) {
    extras.push({
      key: 'evidence',
      label: 'Evidence links',
      value: node.evidenceCount,
    });
  }
  if (node.type === 'Company' && node.companyRole === 'employer') {
    extras.push({ key: 'role', label: 'Role', value: 'Past employer' });
  }
  if (node.type === 'Company' && node.companyRole === 'poster') {
    extras.push({ key: 'role', label: 'Role', value: 'Posted a saved offer' });
  }
  if (node.type === 'Company' && node.companyRole === 'both') {
    extras.push({ key: 'role', label: 'Role', value: 'Past employer · also in saved jobs' });
  }
  return [...fields.filter((item): item is NonNullable<typeof item> => item !== null), ...extras];
}

export function substrateRegionFor(
  node: EnrichedNode,
): 'evidence' | 'skills' | 'market' | 'orgs' | 'stray' {
  if (node.type === 'Company') {
    if (node.companyRole === 'employer' || node.companyRole === 'both') return 'evidence';
    if (node.companyRole === 'poster') return 'orgs';
    return 'stray';
  }
  for (const region of SUBSTRATE_REGIONS) {
    if (region.types.includes(node.type)) return region.id;
  }
  return 'stray';
}

export function evidenceSectionOf(node: EnrichedNode): string {
  if (node.type === 'Company') return 'Employers';
  return 'Roles & work';
}
