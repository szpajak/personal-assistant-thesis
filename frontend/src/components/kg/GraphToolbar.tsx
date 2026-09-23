'use client';

import { Search, UserRound } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { FilterMode, GraphView, NodeFamily, PredicateFamily, SkillOwnershipFilter } from '@/types/kg';
import { FAMILY_THEME, PREDICATE_THEME, TYPE_LABELS } from './graphModel';

interface GraphToolbarProps {
  view: GraphView;
  onViewChange: (view: GraphView) => void;
  search: string;
  onSearchChange: (value: string) => void;
  onSearchSubmit: () => void;
  showPerson: boolean;
  onShowPersonChange: (value: boolean) => void;
  personName: string;
  hiddenFamilies: NodeFamily[];
  onToggleFamily: (family: NodeFamily) => void;
  hiddenPredicateFamilies: PredicateFamily[];
  onTogglePredicateFamily: (family: PredicateFamily) => void;
  filterMode: FilterMode;
  onFilterModeChange: (mode: FilterMode) => void;
  hops: 1 | 2;
  onHopsChange: (hops: 1 | 2) => void;
  focusLabel: string | null;
  onClearFocus: () => void;
  collapsed: Record<string, number>;
  onExpandType: (type: string) => void;
  skillOwnership: SkillOwnershipFilter;
  onSkillOwnershipChange: (value: SkillOwnershipFilter) => void;
}

const FAMILY_ORDER: NodeFamily[] = ['evidence', 'competency', 'market', 'process', 'identity'];
const PREDICATE_ORDER: PredicateFamily[] = ['evidence', 'market', 'career', 'process'];

export function GraphToolbar({
  view,
  onViewChange,
  search,
  onSearchChange,
  onSearchSubmit,
  showPerson,
  onShowPersonChange,
  personName,
  hiddenFamilies,
  onToggleFamily,
  hiddenPredicateFamilies,
  onTogglePredicateFamily,
  filterMode,
  onFilterModeChange,
  hops,
  onHopsChange,
  focusLabel,
  onClearFocus,
  collapsed,
  onExpandType,
  skillOwnership,
  onSkillOwnershipChange,
}: GraphToolbarProps) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border bg-white p-0.5">
          {(
            [
              ['map', 'Career map'],
              ['focus', 'Focus'],
              ['matrix', 'Evidence matrix'],
            ] as const
          ).map(([id, label]) => (
            <Button
              key={id}
              size="sm"
              variant={view === id ? 'default' : 'ghost'}
              className="h-8"
              onClick={() => onViewChange(id)}
            >
              {label}
            </Button>
          ))}
        </div>

        <form
          className="relative min-w-[200px] flex-1"
          onSubmit={(event) => {
            event.preventDefault();
            onSearchSubmit();
          }}
        >
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search skills, projects, jobs…"
            className="h-9 bg-white pl-8"
          />
        </form>

        <Button
          size="sm"
          variant={showPerson ? 'default' : 'outline'}
          className="h-9"
          onClick={() => onShowPersonChange(!showPerson)}
        >
          <UserRound size={14} className="mr-1.5" />
          {showPerson ? 'Showing you' : 'Show me'}
        </Button>

        {personName && (
          <span className="text-xs text-muted-foreground">Graph for {personName}</span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Families
        </span>
        {FAMILY_ORDER.filter((family) => family !== 'identity').map((family) => {
          const active = !hiddenFamilies.includes(family);
          return (
            <button
              key={family}
              type="button"
              onClick={() => onToggleFamily(family)}
              className="rounded-full border px-2 py-0.5 text-[11px] font-medium"
              style={{
                borderColor: FAMILY_THEME[family].hex,
                background: active ? FAMILY_THEME[family].hex : 'white',
                color: active ? 'white' : FAMILY_THEME[family].hex,
                opacity: active ? 1 : 0.55,
              }}
            >
              {FAMILY_THEME[family].label}
            </button>
          );
        })}

        <span className="ml-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Edges
        </span>
        {PREDICATE_ORDER.map((family) => {
          const active = !hiddenPredicateFamilies.includes(family);
          return (
            <button
              key={family}
              type="button"
              onClick={() => onTogglePredicateFamily(family)}
              className="rounded-full border px-2 py-0.5 text-[11px] font-medium"
              style={{
                borderColor: PREDICATE_THEME[family].hex,
                background: active ? `${PREDICATE_THEME[family].hex}18` : 'white',
                color: PREDICATE_THEME[family].hex,
                opacity: active ? 1 : 0.5,
              }}
            >
              {PREDICATE_THEME[family].label}
            </button>
          );
        })}

        <span className="ml-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Skills
        </span>
        {(
          [
            ['all', 'All'],
            ['owned', 'I have'],
            ['gap', "I don't have yet"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => onSkillOwnershipChange(id)}
            className="rounded-full border px-2 py-0.5 text-[11px] font-medium"
            style={{
              borderColor: FAMILY_THEME.competency.hex,
              background: skillOwnership === id ? FAMILY_THEME.competency.hex : 'white',
              color: skillOwnership === id ? 'white' : FAMILY_THEME.competency.hex,
            }}
          >
            {label}
          </button>
        ))}

        <Button
          size="sm"
          variant="ghost"
          className="h-7 text-xs"
          onClick={() => onFilterModeChange(filterMode === 'dismiss' ? 'dim' : 'dismiss')}
        >
          Search: {filterMode === 'dismiss' ? 'hide others' : 'dim others'}
        </Button>

        {view === 'focus' && (
          <>
            <Button
              size="sm"
              variant={hops === 1 ? 'secondary' : 'ghost'}
              className="h-7 text-xs"
              onClick={() => onHopsChange(1)}
            >
              1 hop
            </Button>
            <Button
              size="sm"
              variant={hops === 2 ? 'secondary' : 'ghost'}
              className="h-7 text-xs"
              onClick={() => onHopsChange(2)}
            >
              2 hops
            </Button>
          </>
        )}

        {focusLabel && (
          <Badge variant="secondary" className="gap-1 font-normal">
            Focus: {focusLabel}
            <button type="button" className="ml-1 text-muted-foreground" onClick={onClearFocus}>
              ×
            </button>
          </Badge>
        )}

        {Object.entries(collapsed).map(([type, count]) => (
          <Button
            key={type}
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => onExpandType(type)}
          >
            Show {count} more {TYPE_LABELS[type] ?? type}
          </Button>
        ))}
      </div>
    </div>
  );
}
