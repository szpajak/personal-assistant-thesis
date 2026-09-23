import { describe, expect, it } from 'vitest';

import { enrichGraph, substrateRegionFor } from '../src/components/kg/graphModel';
import { getRadialLayout, getSubstrateLayout } from '../src/components/kg/layoutGraph';
import type { KGGraphPayload } from '../src/types/kg';

const payload: KGGraphPayload = {
  nodes: [
    { id: 'user_1', type: 'Person', data: { label: 'Ada', properties: { name: 'Ada' } } },
    {
      id: 'skill_1',
      type: 'Skill',
      data: { label: 'Python', properties: { name: 'Python', category: 'backend' } },
    },
    { id: 'proj_1', type: 'Project', data: { label: 'App', properties: { title: 'App' } } },
    { id: 'job_1', type: 'JobOffer', data: { label: 'SWE', properties: { title: 'SWE' } } },
  ],
  edges: [
    { id: 'e2', source: 'proj_1', target: 'skill_1', label: 'USES' },
    { id: 'e3', source: 'job_1', target: 'skill_1', label: 'REQUIRES' },
  ],
};

describe('layoutGraph', () => {
  it('places evidence, skills, and offers into three substrate regions', () => {
    const { nodes, edges } = enrichGraph(payload);
    const laid = getSubstrateLayout(
      nodes.filter((node) => node.type !== 'Person'),
      edges,
    );
    const regions = laid.nodes.filter((node) => node.type === 'kgRegion');
    expect(regions.map((node) => node.id)).toEqual([
      'region-evidence',
      'region-skills',
      'region-market',
    ]);
    const skill = laid.nodes.find((node) => node.id === 'skill_1');
    const project = laid.nodes.find((node) => node.id === 'proj_1');
    const job = laid.nodes.find((node) => node.id === 'job_1');
    expect(skill?.parentNode).toBe('region-skills');
    expect(project?.parentNode).toBe('region-evidence');
    expect(job?.parentNode).toBe('region-market');
    expect(regions[0].position.x).toBeLessThan(regions[1].position.x);
    expect(regions[1].position.x).toBeLessThan(regions[2].position.x);
    expect(laid.edges.every((edge) => edge.animated !== true)).toBe(true);
  });

  it('puts past employers in Evidence and hiring companies in Organizations', () => {
    const { nodes, edges } = enrichGraph({
      nodes: [
        { id: 'emp_1', type: 'Employment', data: { label: 'SWE', properties: { title: 'SWE' } } },
        { id: 'acme', type: 'Company', data: { label: 'Acme', properties: { name: 'Acme' } } },
        { id: 'mega', type: 'Company', data: { label: 'Mega', properties: { name: 'Mega' } } },
        { id: 'both', type: 'Company', data: { label: 'BothCo', properties: { name: 'BothCo' } } },
        { id: 'job_1', type: 'JobOffer', data: { label: 'SWE', properties: { title: 'SWE' } } },
        { id: 'skill_1', type: 'Skill', data: { label: 'Python', properties: { name: 'Python' } } },
      ],
      edges: [
        { id: 'e1', source: 'emp_1', target: 'acme', label: 'AT_COMPANY' },
        { id: 'e2', source: 'job_1', target: 'mega', label: 'POSTED_BY' },
        { id: 'e3', source: 'emp_1', target: 'both', label: 'AT_COMPANY' },
        { id: 'e4', source: 'job_1', target: 'both', label: 'POSTED_BY' },
        { id: 'e5', source: 'job_1', target: 'skill_1', label: 'REQUIRES' },
      ],
    });

    expect(substrateRegionFor(nodes.find((node) => node.id === 'acme')!)).toBe('evidence');
    expect(substrateRegionFor(nodes.find((node) => node.id === 'mega')!)).toBe('orgs');
    expect(substrateRegionFor(nodes.find((node) => node.id === 'both')!)).toBe('evidence');

    const laid = getSubstrateLayout(
      nodes.filter((node) => node.type !== 'Person'),
      edges,
    );
    expect(laid.nodes.filter((node) => node.type === 'kgRegion').map((node) => node.id)).toEqual([
      'region-evidence',
      'region-skills',
      'region-market',
      'region-orgs',
    ]);
    expect(laid.nodes.find((node) => node.id === 'acme')?.parentNode).toBe('region-evidence');
    expect(laid.nodes.find((node) => node.id === 'both')?.parentNode).toBe('region-evidence');
    expect(laid.nodes.find((node) => node.id === 'mega')?.parentNode).toBe('region-orgs');
    expect(laid.nodes.find((node) => node.id === 'job_1')?.parentNode).toBe('region-market');
    expect(laid.nodes.some((node) => node.data?.label === 'Employers')).toBe(true);
  });

  it('puts the focus node at the origin of a radial layout', () => {
    const { nodes, edges } = enrichGraph(payload);
    const laid = getRadialLayout(nodes, edges, 'skill_1');
    const focus = laid.nodes.find((node) => node.id === 'skill_1');
    expect(focus?.position).toEqual({ x: -130, y: -36 });
    const others = laid.nodes.filter((node) => node.id !== 'skill_1');
    expect(others.length).toBeGreaterThan(0);
    expect(
      others.every(
        (node) => Math.hypot(node.position.x + 130, node.position.y + 36) > 100,
      ),
    ).toBe(true);
  });
});
