"use client";

import Link from "next/link";
import { ExternalLink, Focus, X } from "lucide-react";
import type { Node } from "reactflow";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { EnrichedNode } from "@/types/kg";
import {
  curatedFields,
  displayName,
  FAMILY_THEME,
  typeHref,
  TYPE_LABELS,
} from "./graphModel";
import type { KgEntityData } from "./Nodes";

interface NodeDetailPanelProps {
  node: Node<KgEntityData>;
  enriched: EnrichedNode | undefined;
  onClose: () => void;
  onFocus: () => void;
}

export function NodeDetailPanel({
  node,
  enriched,
  onClose,
  onFocus,
}: NodeDetailPanelProps) {
  const kgType = node.data.kgType ?? node.type ?? "Node";
  const theme = FAMILY_THEME[node.data.family ?? "identity"];
  const href = typeHref(kgType);
  const fields = enriched
    ? curatedFields(enriched)
    : Object.entries(node.data)
        .filter(
          ([key]) =>
            ![
              "label",
              "kgType",
              "family",
              "embedding",
              "focused",
              "dimmed",
              "highlighted",
            ].includes(key),
        )
        .filter(
          ([, value]) => value !== undefined && value !== null && value !== "",
        )
        .map(([key, value]) => ({ key, label: key, value }));

  const url = typeof node.data.url === "string" ? node.data.url : undefined;
  const website =
    typeof node.data.website === "string" ? node.data.website : undefined;
  const link = url || website;

  return (
    <Card className="absolute right-4 top-4 z-20 w-80 max-h-[calc(100%-2rem)] shadow-lg">
      <CardHeader className="flex flex-row items-start justify-between space-y-0 border-b py-3">
        <div>
          <CardTitle
            className="text-xs font-bold uppercase tracking-widest"
            style={{ color: theme.hex }}
          >
            {TYPE_LABELS[kgType] ?? kgType}
          </CardTitle>
          <div className="mt-1 text-sm font-semibold leading-snug">
            {enriched
              ? displayName(enriched)
              : String(
                  node.data.name || node.data.title || node.data.label || "",
                )}
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onClose}
        >
          <X size={14} />
        </Button>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[min(420px,55vh)]">
          <div className="space-y-3 p-4">
            {fields.map((field) => (
              <div key={field.key} className="space-y-1">
                <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  {field.label}
                </div>
                {Array.isArray(field.value) ? (
                  <div className="flex flex-wrap gap-1">
                    {field.value.map((item, index) => (
                      <Badge
                        key={`${field.key}-${index}`}
                        variant="secondary"
                        className="text-[10px] font-normal"
                      >
                        {String(item)}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <div className="break-words text-sm font-medium">
                    {String(field.value)}
                  </div>
                )}
              </div>
            ))}

            <div className="flex flex-col gap-2 pt-1">
              <Button size="sm" onClick={onFocus}>
                <Focus size={14} className="mr-2" />
                Focus neighborhood
              </Button>
              {href && (
                <Button size="sm" variant="outline" asChild>
                  <Link href={href}>
                    Open {TYPE_LABELS[kgType] ?? kgType} page
                  </Link>
                </Button>
              )}
              {link && (
                <Button size="sm" variant="outline" asChild>
                  <a href={link} target="_blank" rel="noopener noreferrer">
                    Open link <ExternalLink size={14} className="ml-2" />
                  </a>
                </Button>
              )}
            </div>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
