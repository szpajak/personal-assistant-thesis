import { describe, expect, it } from "vitest";

import {
  applyVisibility,
  collapseCrowdedTypes,
  defaultFilters,
  enrichGraph,
  familyOfType,
  neighborIdsOf,
  nodesWithinHops,
  predicateFamilyOf,
  SKILL_COLLAPSE_THRESHOLD,
} from "../src/components/kg/graphModel";
import type { KGGraphPayload } from "../src/types/kg";

const payload: KGGraphPayload = {
  person_name: "Ada",
  person_id: "user_1",
  nodes: [
    {
      id: "user_1",
      type: "Person",
      data: { label: "Ada", properties: { name: "Ada" } },
    },
    {
      id: "skill_1",
      type: "Skill",
      data: {
        label: "Python",
        properties: { name: "Python", level: "expert", category: "backend" },
      },
    },
    {
      id: "proj_1",
      type: "Project",
      data: { label: "App", properties: { title: "App" } },
    },
    {
      id: "job_1",
      type: "JobOffer",
      data: { label: "SWE", properties: { title: "SWE" } },
    },
    {
      id: "app_1",
      type: "Application",
      data: { label: "Applied", properties: { status: "Applied" } },
    },
  ],
  edges: [
    { id: "e1", source: "user_1", target: "skill_1", label: "HAS_SKILL" },
    {
      id: "e2",
      source: "proj_1",
      target: "skill_1",
      label: "USES",
      properties: { source: "inferred", confidence: 0.8 },
    },
    { id: "e3", source: "job_1", target: "skill_1", label: "REQUIRES" },
    { id: "e4", source: "user_1", target: "app_1", label: "APPLIED_TO" },
  ],
};

describe("graphModel", () => {
  it("maps types to families and predicates", () => {
    expect(familyOfType("Skill")).toBe("competency");
    expect(familyOfType("Project")).toBe("evidence");
    expect(familyOfType("JobOffer")).toBe("market");
    expect(predicateFamilyOf("USES")).toBe("evidence");
    expect(predicateFamilyOf("REQUIRES")).toBe("market");
    expect(predicateFamilyOf("AT_COMPANY")).toBe("evidence");
    expect(predicateFamilyOf("POSTED_BY")).toBe("market");
  });

  it("enriches skills with demand, evidence, and direct-link flags", () => {
    const { nodes, edges, personName } = enrichGraph(payload);
    expect(personName).toBe("Ada");
    const skill = nodes.find((node) => node.id === "skill_1");
    expect(skill?.demandCount).toBe(1);
    expect(skill?.evidenceCount).toBe(1);
    expect(skill?.hasDirectSkillLink).toBe(true);
    expect(skill?.skillScore).toBeGreaterThan(10);
    expect(edges.find((edge) => edge.id === "e2")?.sourceKind).toBe("inferred");
  });

  it("hides Person, applications, and HAS_SKILL on the default career map", () => {
    const { nodes, edges } = enrichGraph(payload);
    const visible = applyVisibility(nodes, edges, defaultFilters());
    const ids = visible.visibleNodes.map((node) => node.id);
    expect(ids).toContain("skill_1");
    expect(ids).toContain("proj_1");
    expect(ids).toContain("job_1");
    expect(ids).not.toContain("user_1");
    expect(ids).not.toContain("app_1");
    expect(visible.visibleEdges.map((edge) => edge.label)).toEqual([
      "USES",
      "REQUIRES",
    ]);
  });

  it("keeps a 1-hop neighborhood in focus view", () => {
    const { nodes, edges } = enrichGraph(payload);
    const visible = applyVisibility(nodes, edges, {
      ...defaultFilters(),
      focusId: "skill_1",
      hops: 1,
    });
    expect(visible.visibleNodes.map((node) => node.id).sort()).toEqual([
      "job_1",
      "proj_1",
      "skill_1",
    ]);
  });

  it("dims search misses instead of dropping them when asked", () => {
    const { nodes, edges } = enrichGraph(payload);
    const visible = applyVisibility(nodes, edges, {
      ...defaultFilters(),
      search: "python",
      filterMode: "dim",
    });
    expect(visible.dimmedNodeIds.has("proj_1")).toBe(true);
    expect(visible.dimmedNodeIds.has("skill_1")).toBe(false);
    expect(visible.visibleNodes.map((node) => node.id)).toContain("proj_1");
  });

  it("computes neighbor ids from visible edges", () => {
    const { edges } = enrichGraph(payload);
    expect([...neighborIdsOf("skill_1", edges)].sort()).toEqual([
      "job_1",
      "proj_1",
      "skill_1",
      "user_1",
    ]);
  });

  it("collapses crowded skill lists until expanded", () => {
    const { nodes } = enrichGraph({
      nodes: Array.from(
        { length: SKILL_COLLAPSE_THRESHOLD + 3 },
        (_, index) => ({
          id: `s${index}`,
          type: "Skill",
          data: {
            label: `S${index}`,
            properties: { name: `S${index}`, level: "beginner" },
          },
        }),
      ),
      edges: [],
    });
    const collapsed = collapseCrowdedTypes(nodes, new Set());
    expect(collapsed.nodes).toHaveLength(SKILL_COLLAPSE_THRESHOLD);
    expect(collapsed.collapsed.Skill).toBe(3);
    const expanded = collapseCrowdedTypes(nodes, new Set(["Skill"]));
    expect(expanded.nodes).toHaveLength(SKILL_COLLAPSE_THRESHOLD + 3);
  });

  it("walks undirected hops", () => {
    const { edges } = enrichGraph(payload);
    expect(nodesWithinHops("proj_1", edges, 1).has("skill_1")).toBe(true);
    expect(nodesWithinHops("proj_1", edges, 1).has("job_1")).toBe(false);
    expect(nodesWithinHops("proj_1", edges, 2).has("job_1")).toBe(true);
  });

  it("places past employers in evidence and posters as hiring orgs", () => {
    const { nodes } = enrichGraph({
      nodes: [
        {
          id: "emp_1",
          type: "Employment",
          data: { label: "SWE", properties: { title: "SWE" } },
        },
        {
          id: "acme",
          type: "Company",
          data: { label: "Acme", properties: { name: "Acme" } },
        },
        {
          id: "mega",
          type: "Company",
          data: { label: "Mega", properties: { name: "Mega" } },
        },
        {
          id: "both",
          type: "Company",
          data: { label: "BothCo", properties: { name: "BothCo" } },
        },
        {
          id: "job_1",
          type: "JobOffer",
          data: { label: "SWE", properties: { title: "SWE" } },
        },
      ],
      edges: [
        { id: "e1", source: "emp_1", target: "acme", label: "AT_COMPANY" },
        { id: "e2", source: "job_1", target: "mega", label: "POSTED_BY" },
        { id: "e3", source: "emp_1", target: "both", label: "AT_COMPANY" },
        { id: "e4", source: "job_1", target: "both", label: "POSTED_BY" },
      ],
    });
    const acme = nodes.find((node) => node.id === "acme");
    const mega = nodes.find((node) => node.id === "mega");
    const both = nodes.find((node) => node.id === "both");
    expect(acme?.companyRole).toBe("employer");
    expect(acme?.family).toBe("evidence");
    expect(mega?.companyRole).toBe("poster");
    expect(mega?.family).toBe("market");
    expect(both?.companyRole).toBe("both");
    expect(both?.family).toBe("evidence");
  });

  it("keeps owned skills and their neighborhood, including posting companies", () => {
    const { nodes, edges } = enrichGraph({
      person_id: "user_1",
      nodes: [
        {
          id: "user_1",
          type: "Person",
          data: { label: "Ada", properties: { name: "Ada" } },
        },
        {
          id: "python",
          type: "Skill",
          data: { label: "Python", properties: { name: "Python" } },
        },
        {
          id: "k8s",
          type: "Skill",
          data: { label: "K8s", properties: { name: "K8s" } },
        },
        {
          id: "proj_1",
          type: "Project",
          data: { label: "App", properties: { title: "App" } },
        },
        {
          id: "job_1",
          type: "JobOffer",
          data: { label: "SWE", properties: { title: "SWE" } },
        },
        {
          id: "mega",
          type: "Company",
          data: { label: "Mega", properties: { name: "Mega" } },
        },
      ],
      edges: [
        { id: "e1", source: "user_1", target: "python", label: "HAS_SKILL" },
        { id: "e2", source: "proj_1", target: "python", label: "USES" },
        { id: "e3", source: "job_1", target: "python", label: "REQUIRES" },
        { id: "e4", source: "job_1", target: "k8s", label: "REQUIRES" },
        { id: "e5", source: "job_1", target: "mega", label: "POSTED_BY" },
      ],
    });

    const owned = applyVisibility(nodes, edges, {
      ...defaultFilters(),
      skillOwnership: "owned",
    });
    const ownedIds = owned.visibleNodes.map((node) => node.id);
    expect(ownedIds).toContain("python");
    expect(ownedIds).toContain("proj_1");
    expect(ownedIds).toContain("job_1");
    expect(ownedIds).toContain("mega");
    expect(ownedIds).not.toContain("k8s");
    expect(ownedIds).not.toContain("user_1");

    const gap = applyVisibility(nodes, edges, {
      ...defaultFilters(),
      skillOwnership: "gap",
    });
    const gapIds = gap.visibleNodes.map((node) => node.id);
    expect(gapIds).toContain("k8s");
    expect(gapIds).toContain("job_1");
    expect(gapIds).toContain("mega");
    expect(gapIds).not.toContain("python");
    expect(gapIds).not.toContain("proj_1");
  });
});
