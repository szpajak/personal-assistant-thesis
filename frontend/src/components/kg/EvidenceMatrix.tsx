'use client';

import { useMemo } from 'react';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { EnrichedEdge, EnrichedNode } from '@/types/kg';
import { displayName } from './graphModel';

const EVIDENCE_TYPES = new Set(['Project', 'Employment', 'Certificate']);
const EVIDENCE_RELS = new Set(['USES', 'USED_IN_ROLE', 'VALIDATES']);

interface EvidenceMatrixProps {
  nodes: EnrichedNode[];
  edges: EnrichedEdge[];
  onSelect: (nodeId: string) => void;
}

export function EvidenceMatrix({ nodes, edges, onSelect }: EvidenceMatrixProps) {
  const { rows, skills, cells } = useMemo(() => {
    const skillNodes = nodes
      .filter((node) => node.type === 'Skill')
      .sort((a, b) => displayName(a).localeCompare(displayName(b)));
    const evidenceNodes = nodes
      .filter((node) => EVIDENCE_TYPES.has(node.type))
      .sort((a, b) => displayName(a).localeCompare(displayName(b)));

    const linked = new Set<string>();
    for (const edge of edges) {
      if (!EVIDENCE_RELS.has(edge.label)) continue;
      linked.add(`${edge.source}::${edge.target}`);
      linked.add(`${edge.target}::${edge.source}`);
    }

    return { rows: evidenceNodes, skills: skillNodes, cells: linked };
  }, [nodes, edges]);

  if (rows.length === 0 || skills.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-dashed bg-white text-sm text-muted-foreground">
        Add projects or skills to see where expertise is demonstrated.
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto rounded-lg border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky left-0 z-10 min-w-[180px] bg-white">Evidence</TableHead>
            {skills.map((skill) => (
              <TableHead key={skill.id} className="min-w-[88px] text-center">
                <button type="button" className="hover:underline" onClick={() => onSelect(skill.id)}>
                  {displayName(skill)}
                </button>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell className="sticky left-0 bg-white font-medium">
                <button type="button" className="text-left hover:underline" onClick={() => onSelect(row.id)}>
                  <div>{displayName(row)}</div>
                  <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{row.type}</div>
                </button>
              </TableCell>
              {skills.map((skill) => {
                const filled = cells.has(`${row.id}::${skill.id}`);
                return (
                  <TableCell key={skill.id} className="text-center">
                    <button
                      type="button"
                      aria-label={`${displayName(row)} ${filled ? 'uses' : 'does not use'} ${displayName(skill)}`}
                      className="inline-flex h-6 w-6 items-center justify-center rounded-sm"
                      style={{ background: filled ? '#009E73' : '#e2e8f0' }}
                      onClick={() => onSelect(filled ? skill.id : row.id)}
                    />
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
