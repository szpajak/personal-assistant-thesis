'use client';

import { FAMILY_THEME, PREDICATE_THEME } from './graphModel';

export function GraphLegend() {
  return (
    <div className="pointer-events-none absolute bottom-4 left-4 z-10 max-w-xs rounded-md border bg-white/95 p-3 text-[11px] shadow-sm">
      <div className="mb-1.5 font-semibold uppercase tracking-wider text-muted-foreground">
        Legend
      </div>
      <div className="mb-2 flex flex-wrap gap-2">
        {(['evidence', 'competency', 'market', 'process'] as const).map((family) => (
          <span key={family} className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: FAMILY_THEME[family].hex }} />
            {FAMILY_THEME[family].label}
          </span>
        ))}
      </div>
      <div className="space-y-0.5 text-muted-foreground">
        <div>Columns: Evidence → Skills → Offers → Organizations</div>
        <div>Past employers sit under Evidence; hiring firms under Organizations</div>
        <div>Dashed skill = not in your skillset · badge = jobs requiring it</div>
        <div className="flex flex-wrap gap-2 pt-1">
          {(['evidence', 'market', 'career', 'process'] as const).map((family) => (
            <span key={family} className="inline-flex items-center gap-1">
              <span className="h-0.5 w-3" style={{ background: PREDICATE_THEME[family].hex }} />
              {PREDICATE_THEME[family].label} edges
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
