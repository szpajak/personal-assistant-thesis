"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Plus, Sparkles, X, RefreshCw } from "lucide-react";

interface SkillsToLearnPanelProps {
  skills: string[];
  onAdd: (skill: string) => void;
  onRemove: (skill: string) => void;
  onRefreshProjects: () => void;
  isRefreshingProjects?: boolean;
  onGenerateRoadmap: () => void;
  isGeneratingRoadmap?: boolean;
}

export function SkillsToLearnPanel({
  skills,
  onAdd,
  onRemove,
  onRefreshProjects,
  isRefreshingProjects = false,
  onGenerateRoadmap,
  isGeneratingRoadmap = false,
}: SkillsToLearnPanelProps) {
  const [typed, setTyped] = React.useState("");

  const addTyped = () => {
    const name = typed.trim();
    if (!name) return;
    onAdd(name);
    setTyped("");
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-bold flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          Skills to learn
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Combine gaps, Market Demand picks, and typed skills into one set —
          used for both project ideas and the learning roadmap.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex max-h-40 min-h-9 flex-wrap gap-2 overflow-y-auto pr-1">
          {skills.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No skills selected yet — add gaps below, click a Market Demand
              skill, or type one.
            </p>
          ) : (
            skills.map((skill) => (
              <Badge
                key={skill}
                variant="default"
                className="gap-1 py-1 pl-2.5 pr-1.5 text-xs"
              >
                {skill}
                <button
                  type="button"
                  onClick={() => onRemove(skill)}
                  className="ml-0.5 rounded-full hover:bg-primary-foreground/20"
                  aria-label={`Remove ${skill}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))
          )}
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Type another skill…"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTyped();
              }
            }}
          />
          <Button
            type="button"
            variant="outline"
            onClick={addTyped}
            className="gap-1 shrink-0"
          >
            <Plus className="h-4 w-4" />
            Add
          </Button>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            variant="secondary"
            className="flex-1 gap-2"
            disabled={isRefreshingProjects || skills.length < 2}
            onClick={onRefreshProjects}
            title={skills.length < 2 ? "Select at least 2 skills" : undefined}
          >
            {isRefreshingProjects ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh project ideas
          </Button>
          <Button
            type="button"
            className="flex-1 gap-2"
            disabled={isGeneratingRoadmap || skills.length === 0}
            onClick={onGenerateRoadmap}
          >
            {isGeneratingRoadmap ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Generate learning roadmap
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
