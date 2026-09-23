import React, { memo } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import {
  Award,
  BookOpen,
  Briefcase,
  Building2,
  FileText,
  GraduationCap,
  Mail,
  Send,
  Target,
  User,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { NodeFamily } from "@/types/kg";
import { FAMILY_THEME, TYPE_LABELS } from "./graphModel";

const TYPE_ICONS: Record<string, LucideIcon> = {
  Person: User,
  Project: Briefcase,
  Skill: Zap,
  JobOffer: FileText,
  Company: Building2,
  Application: Send,
  Certificate: Award,
  Employment: Briefcase,
  Education: GraduationCap,
  TargetRole: Target,
  Email: Mail,
  LearningResource: BookOpen,
  Document: FileText,
};

export interface KgEntityData {
  label?: string;
  name?: string;
  title?: string;
  kgType?: string;
  family?: NodeFamily;
  level?: string;
  category?: string;
  status?: string;
  company?: string;
  issuer?: string;
  degree?: string;
  demandCount?: number;
  evidenceCount?: number;
  hasDirectSkillLink?: boolean;
  companyRole?: "employer" | "poster" | "both" | "other";
  isOwnedSkill?: boolean;
  focused?: boolean;
  dimmed?: boolean;
  highlighted?: boolean;
  [key: string]: unknown;
}

function titleOf(data: KgEntityData): string {
  return String(data.name || data.title || data.label || "");
}

function subtitleOf(data: KgEntityData): string | null {
  if (data.kgType === "Skill") {
    const parts = [data.level, data.category].filter(Boolean);
    return parts.length ? parts.join(" · ") : null;
  }
  if (data.kgType === "Project" && data.status)
    return String(data.status).replaceAll("_", " ");
  if (data.kgType === "JobOffer" && data.company) return String(data.company);
  if (data.kgType === "Employment" && data.company) return String(data.company);
  if (data.kgType === "Application" && data.status) return String(data.status);
  if (data.kgType === "Certificate")
    return data.issuer ? String(data.issuer) : null;
  if (data.kgType === "Company") {
    if (data.companyRole === "both") return "Worked here · saved offer";
    if (data.companyRole === "employer") return "Worked here";
    if (data.companyRole === "poster") return "Posted a saved offer";
  }
  if (data.kgType === "Education")
    return data.degree ? String(data.degree) : null;
  return null;
}

export const KgEntityNode = memo(
  ({ data, selected }: NodeProps<KgEntityData>) => {
    const family = data.family ?? "identity";
    const theme = FAMILY_THEME[family];
    const Icon = TYPE_ICONS[data.kgType ?? ""] ?? Zap;
    const typeLabel = TYPE_LABELS[data.kgType ?? ""] ?? data.kgType ?? "Node";
    const muted =
      data.kgType === "Project" && data.status && data.status !== "finished";
    const outline =
      data.kgType === "Skill" && data.hasDirectSkillLink === false;
    const level = String(data.level ?? "").toLowerCase();
    const scale =
      data.kgType === "Skill"
        ? level === "expert"
          ? 1.08
          : level === "advanced"
            ? 1.04
            : level === "beginner"
              ? 0.92
              : 1
        : 1;

    return (
      <div
        className={cn(
          "rounded-md bg-white shadow-sm transition-opacity",
          selected || data.focused ? "ring-2 ring-offset-1" : "",
          data.dimmed && "opacity-20",
          data.highlighted && !data.dimmed && "opacity-100",
        )}
        style={{
          borderWidth: 2,
          borderStyle: outline || muted ? "dashed" : "solid",
          borderColor: theme.hex,
          minWidth: 220 * scale,
          maxWidth: 260,
          boxShadow:
            selected || data.focused ? `0 0 0 2px ${theme.hex}` : undefined,
        }}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="!h-2 !w-2"
          style={{ background: theme.hex }}
        />
        <Handle
          type="source"
          position={Position.Right}
          className="!h-2 !w-2"
          style={{ background: theme.hex }}
        />
        <div className="flex items-center gap-2 px-2.5 py-1.5">
          <div
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
            style={{
              background: outline ? "white" : theme.hex,
              border: outline ? `2px solid ${theme.hex}` : undefined,
            }}
          >
            <Icon size={14} style={{ color: outline ? theme.hex : "white" }} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1">
              <span
                className="text-[9px] font-bold uppercase tracking-wider"
                style={{ color: theme.hex }}
              >
                {typeLabel}
              </span>
              {data.kgType === "Skill" && (data.demandCount ?? 0) > 0 && (
                <span className="rounded bg-slate-100 px-1 text-[9px] font-medium text-slate-600">
                  {data.demandCount} jobs
                </span>
              )}
              {data.kgType === "Company" && data.companyRole === "both" && (
                <span className="rounded bg-slate-100 px-1 text-[9px] font-medium text-slate-600">
                  also hiring
                </span>
              )}
            </div>
            <div className="truncate text-sm font-semibold leading-tight">
              {titleOf(data)}
            </div>
            {subtitleOf(data) && (
              <div className="truncate text-[10px] capitalize text-muted-foreground">
                {subtitleOf(data)}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  },
);

KgEntityNode.displayName = "KgEntityNode";

export const KgRegionNode = memo(
  ({ data }: NodeProps<{ label: string; regionId: string }>) => {
    const family: NodeFamily =
      data.regionId === "skills"
        ? "competency"
        : data.regionId === "market" || data.regionId === "orgs"
          ? "market"
          : "evidence";
    const theme = FAMILY_THEME[family];

    return (
      <div
        className="h-full w-full rounded-xl border border-dashed bg-slate-50/80"
        style={{ borderColor: `${theme.hex}66` }}
      >
        <div
          className="px-3 py-2 text-[11px] font-bold uppercase tracking-[0.16em]"
          style={{ color: theme.hex }}
        >
          {data.label}
        </div>
      </div>
    );
  },
);

KgRegionNode.displayName = "KgRegionNode";

export const KgSectionNode = memo(({ data }: NodeProps<{ label: string }>) => (
  <div className="pointer-events-none w-[220px] text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
    {data.label}
  </div>
));

KgSectionNode.displayName = "KgSectionNode";
