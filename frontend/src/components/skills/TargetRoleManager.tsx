"use client";

import React from "react";
import {
  useCreateTargetRole,
  useDeleteTargetRole,
  useRefreshTargetRole,
  useTargetRoles,
} from "@/hooks/useProfile";
import type { TargetRole } from "@/types/profile";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Plus, RefreshCw, Target, Trash2 } from "lucide-react";

const COUNTRIES = [
  "Poland",
  "USA",
  "UK",
  "Germany",
  "France",
  "Netherlands",
  "Spain",
  "Italy",
  "Canada",
  "Australia",
  "Ireland",
  "Sweden",
  "Switzerland",
] as const;

const NO_COUNTRY = "__none__";

function statusLabel(role: TargetRole): string {
  switch (role.sample_status) {
    case "ready":
      return `${role.sample_job_count} offer${role.sample_job_count === 1 ? "" : "s"} sampled`;
    case "scraping":
      return "Scraping market offers…";
    case "ingesting":
      return "Ingesting sampled offers…";
    case "error":
      return "Sample refresh failed";
    default:
      return "Not sampled yet";
  }
}

function statusVariant(role: TargetRole): "default" | "secondary" | "destructive" | "outline" {
  switch (role.sample_status) {
    case "ready":
      return "secondary";
    case "error":
      return "destructive";
    case "scraping":
    case "ingesting":
      return "default";
    default:
      return "outline";
  }
}

interface TargetRoleManagerProps {
  selectedRoleId: string | null;
  onSelectRole: (roleId: string | null) => void;
}

export function TargetRoleManager({ selectedRoleId, onSelectRole }: TargetRoleManagerProps) {
  const { data: roles, isLoading } = useTargetRoles();
  const createRole = useCreateTargetRole();
  const refreshRole = useRefreshTargetRole();
  const deleteRole = useDeleteTargetRole();
  const { toast } = useToast();

  const [title, setTitle] = React.useState("");
  const [location, setLocation] = React.useState("");
  const [country, setCountry] = React.useState<string>(NO_COUNTRY);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    try {
      const role = await createRole.mutateAsync({
        title: trimmed,
        location: location.trim() || undefined,
        country: country === NO_COUNTRY ? undefined : country,
      });
      setTitle("");
      setLocation("");
      setCountry(NO_COUNTRY);
      onSelectRole(role.id);
      toast({
        title: "Target role added",
        description: `Sampling ~50 market offers for "${role.title}"…`,
      });
    } catch (error) {
      toast({
        title: "Could not add role",
        description: error instanceof Error ? error.message : "Please try again.",
        variant: "destructive",
      });
    }
  };

  const handleRefresh = async (role: TargetRole) => {
    try {
      await refreshRole.mutateAsync(role.id);
      toast({ title: "Refreshing market sample", description: `Re-scraping offers for "${role.title}".` });
    } catch (error) {
      toast({
        title: "Could not refresh",
        description: error instanceof Error ? error.message : "Please try again.",
        variant: "destructive",
      });
    }
  };

  const handleDelete = async (role: TargetRole) => {
    try {
      await deleteRole.mutateAsync(role.id);
      if (selectedRoleId === role.id) onSelectRole(null);
    } catch (error) {
      toast({
        title: "Could not delete role",
        description: error instanceof Error ? error.message : "Please try again.",
        variant: "destructive",
      });
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-bold flex items-center gap-2">
          <Target className="h-4 w-4" />
          Target roles
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Sample ~50 real job postings for a role/location to drive Market Demand and skill
          gaps from actual data instead of a typed skill list.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleCreate} className="flex flex-col sm:flex-row gap-2">
          <Input
            placeholder="e.g. Senior DevOps Engineer"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="sm:flex-1"
          />
          <Input
            placeholder="Location (e.g. Warsaw)"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="sm:w-40"
          />
          <Select value={country} onValueChange={setCountry}>
            <SelectTrigger className="sm:w-36">
              <SelectValue placeholder="Country" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_COUNTRY}>Any country</SelectItem>
              {COUNTRIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="submit" disabled={createRole.isPending || !title.trim()} className="gap-1">
            {createRole.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            Add
          </Button>
        </form>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading target roles…</p>
        ) : roles && roles.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {roles.map((role) => {
              const active = selectedRoleId === role.id;
              const sampling = role.sample_status === "scraping" || role.sample_status === "ingesting";
              return (
                <div
                  key={role.id}
                  className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                    active ? "border-primary bg-primary/5" : "bg-muted/30"
                  }`}
                >
                  <button
                    type="button"
                    className="text-left"
                    onClick={() => onSelectRole(active ? null : role.id)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{role.title}</span>
                      {role.location && (
                        <span className="text-xs text-muted-foreground">· {role.location}</span>
                      )}
                    </div>
                    <Badge variant={statusVariant(role)} className="mt-1 text-[10px]">
                      {statusLabel(role)}
                    </Badge>
                  </button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    disabled={sampling}
                    onClick={() => handleRefresh(role)}
                    title="Refresh market sample"
                  >
                    {sampling ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-red-600"
                    onClick={() => handleDelete(role)}
                    title="Delete role"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No target roles yet — add one above to benchmark against real postings.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
